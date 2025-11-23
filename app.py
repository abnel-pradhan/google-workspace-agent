import os
import json
import uuid
import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import pytz
import traceback

# --- CONFIGURATION ---
app = Flask(__name__)
CORS(app)

# Setup logging (console + file, structured JSON)
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format="%(message)s",  # raw JSON string for structured entries
    handlers=[
        logging.FileHandler("chat_agent.log"),
        logging.StreamHandler()
    ]
)

def log_event(event_type, request_id, details):
    """Structured JSON logging for events."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event_type,
        "request_id": request_id,
        "details": details
    }
    logging.info(json.dumps(log_entry))

# --- ENVIRONMENT ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.error(json.dumps({"error": "GEMINI_API_KEY not set in environment"}))
    raise RuntimeError("GEMINI_API_KEY not set in environment")

genai.configure(api_key=GEMINI_API_KEY)

# --- GEMINI TOOLS ---
gemini_tools = [
    {
        "function_declarations": [
            {
                "name": "tool_create_calendar_event",
                "description": "Creates a new event on the user's primary Google Calendar.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": {"type": "STRING"},
                        "start_time": {"type": "STRING", "description": "ISO 8601 format (YYYY-MM-DDTHH:MM:SS)"},
                        "end_time": {"type": "STRING", "description": "ISO 8601 format (YYYY-MM-DDTHH:MM:SS)"},
                        "time_zone": {"type": "STRING", "description": "The IANA timezone string (e.g. 'Asia/Kolkata', 'America/New_York')"},
                    },
                    "required": ["summary", "start_time", "end_time"]
                },
            },
            {
                "name": "tool_search_gmail",
                "description": "Searches the user's Gmail inbox for messages.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"query": {"type": "STRING"}},
                    "required": ["query"]
                },
            },
        ]
    }
]

# --- HELPERS ---
def sanitize_history_for_gemini(history):
    sanitized = []
    for item in history:
        new_parts = []
        for part in item.get('parts', []):
            new_part = {}
            if 'text' in part:
                new_part['text'] = part['text']
            if 'functionCall' in part:
                new_part['function_call'] = part['functionCall']
            elif 'function_call' in part:
                new_part['function_call'] = part['function_call']
            if 'functionResponse' in part:
                new_part['function_response'] = part['functionResponse']
            elif 'function_response' in part:
                new_part['function_response'] = part['function_response']
            if new_part:
                new_parts.append(new_part)
        if new_parts:
            sanitized.append({"role": item.get('role', 'user'), "parts": new_parts})
    return sanitized

def part_to_dict(part):
    # Safe conversion of a Gemini content part
    try:
        if getattr(part, 'text', None):
            return {"text": part.text}
        if getattr(part, 'function_call', None):
            return {
                "functionCall": {
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args)
                }
            }
    except Exception as e:
        return {"error": f"part_to_dict_failed: {str(e)}"}
    return {}

def history_to_dict(history):
    safe = []
    for c in history:
        parts_out = []
        for p in getattr(c, 'parts', []) or []:
            parts_out.append(part_to_dict(p))
        safe.append({"role": getattr(c, 'role', 'model'), "parts": parts_out})
    return safe

def extract_user_text_from_item(item):
    # Robustly pull user text from the last message item
    parts = item.get('parts', [])
    if not parts:
        return ""
    first = parts[0]
    return first.get('text', "")

def safe_first_part_from_response(response):
    # Safely return the first part dict from response, even if empty
    try:
        candidates = getattr(response, 'candidates', None)
        if not candidates:
            return {"text": ""}
        content = getattr(candidates[0], 'content', None)
        if not content:
            return {"text": ""}
        parts = getattr(content, 'parts', None) or []
        if not parts:
            # If the model returned an empty parts list, try content.text or fallback
            text_attr = getattr(content, 'text', "")
            return {"text": text_attr if text_attr else ""}
        return part_to_dict(parts[0])
    except Exception as e:
        return {"error": f"safe_first_part_from_response_failed: {str(e)}"}

# --- API ENDPOINT ---
@app.route('/api/chat', methods=['POST'])
def chat_handler():
    request_id = str(uuid.uuid4())
    try:
        data = request.json or {}
        raw_history = data.get('history', [])
        user_timezone = data.get('timezone', 'UTC')

        log_event("request_received", request_id, {"raw_history_len": len(raw_history), "timezone": user_timezone})

        clean_history = sanitize_history_for_gemini(raw_history)
        log_event("history_sanitized", request_id, {"clean_history_len": len(clean_history)})

        if not clean_history:
            return jsonify({"error": "No chat history received.", "request_id": request_id}), 400

        # Pop the last item (user or tool response), with guard
        last_message_item = clean_history.pop()
        log_event("last_message_item", request_id, {"parts_len": len(last_message_item.get('parts', [])), "role": last_message_item.get('role')})

        # Extract user text safely
        user_text = extract_user_text_from_item(last_message_item)
        log_event("user_text_extracted", request_id, {"user_text_len": len(user_text)})

        # Timezone and current time
        try:
            tz = pytz.timezone(user_timezone)
            now = datetime.now(tz)
            tz_ok = True
        except Exception as tz_err:
            now = datetime.now()
            tz_ok = False
            log_event("timezone_error", request_id, {"error": str(tz_err)})
        log_event("datetime_calculated", request_id, {"datetime": now.isoformat(), "timezone_ok": tz_ok})

        system_prompt = f"""
        You are a helpful assistant connected to Google Workspace.
        
        CRITICAL CONTEXT:
        - User's Timezone: {user_timezone}
        - Current Date: {now.strftime("%Y-%m-%d")} ({now.strftime("%A")})
        - Current Time: {now.strftime("%H:%M:%S")}
        
        INSTRUCTIONS:
        1. When the user asks for relative dates like 'tomorrow', 'next Monday', or 'today', you MUST calculate the exact ISO 8601 date based on the current date provided above.
        2. Always include the '{user_timezone}' in the 'time_zone' parameter when calling the 'tool_create_calendar_event' tool.
        """

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash-preview-09-2025',
            tools=gemini_tools,
            system_instruction=system_prompt,
            safety_settings=safety_settings
        )

        # Start chat with remaining history (no more pops later)
        chat = model.start_chat(history=clean_history)
        log_event("chat_started", request_id, {"history_len": len(clean_history)})

        # Decide what to send:
        # - If we have user_text, send that.
        # - Else, if last_message_item has parts, send those parts.
        # - Else, error.
        if user_text:
            message_payload = user_text
            msg_type = "user_text"
        elif last_message_item.get('parts'):
            message_payload = last_message_item['parts']
            msg_type = "last_item_parts"
        else:
            return jsonify({"error": "No user text or function response available.", "request_id": request_id}), 400

        log_event("message_sending", request_id, {"type": msg_type})
        response = chat.send_message(message_payload)

        # Handle response safely
        if not getattr(response, 'candidates', None):
            log_event("response_blocked", request_id, {"reason": "empty candidates"})
            return jsonify({"error": "The AI model blocked the response. Try rephrasing.", "request_id": request_id}), 400

        # Safely extract first part without indexing errors
        response_part = safe_first_part_from_response(response)
        log_event("response_received", request_id, {"has_text": "text" in response_part, "has_error": "error" in response_part})

        return jsonify({
            "response_part": response_part,
            "updated_history": history_to_dict(chat.history),
            "request_id": request_id
        })

    except Exception as e:
        log_event("error", request_id, {"error": str(e), "traceback": traceback.format_exc()})
        return jsonify({"error": str(e), "request_id": request_id}), 500

# --- SERVE HTML ---
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    log_event("server_start", "system", {"message": "Flask server running"})
    logging.info("Your app will be at: http://localhost:8000")
    try:
        app.run(port=8000, debug=True)
    except KeyboardInterrupt:
        log_event("server_stop", "system", {"message": "Server stopped manually"})
