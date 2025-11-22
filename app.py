import os
import json
import google.generativeai as genai
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import pytz # You might need to install this: pip install pytz

# --- CONFIGURATION ---
app = Flask(__name__)
CORS(app)

# Get API key from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not set in environment.")

def configure_genai():
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)

configure_genai()

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
    for i, item in enumerate(history):
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
            sanitized.append({
                "role": item['role'],
                "parts": new_parts
            })
    return sanitized

def part_to_dict(part):
    if part.text:
        return {"text": part.text}
    elif part.function_call:
        return {
            "functionCall": {
                "name": part.function_call.name,
                "args": dict(part.function_call.args)
            }
        }
    return {}

def history_to_dict(history):
    serialized_history = []
    for content in history:
        parts = []
        for part in content.parts:
            parts.append(part_to_dict(part))
        serialized_history.append({
            "role": content.role,
            "parts": parts
        })
    return serialized_history

# --- API ENDPOINT ---
@app.route('/api/chat', methods=['POST'])
def chat_handler():
    if not GEMINI_API_KEY:
         return jsonify({"error": "Server is missing GEMINI_API_KEY."}), 500

    try:
        data = request.json
        raw_history = data.get('history', [])
        # Get timezone from client, default to UTC if missing
        user_timezone = data.get('timezone', 'UTC') 
        
        clean_history = sanitize_history_for_gemini(raw_history)
        
        if not clean_history:
             return jsonify({"error": "No chat history received."}), 400
             
        last_message_item = clean_history.pop()
        
        user_text = ""
        if 'parts' in last_message_item and len(last_message_item['parts']) > 0:
             first_part = last_message_item['parts'][0]
             if 'text' in first_part:
                 user_text = first_part['text']
        
        if not user_text:
             if 'parts' in last_message_item and len(last_message_item['parts']) > 0:
                 if 'function_response' in last_message_item['parts'][0]:
                     pass 
                 else:
                     print(f"ERROR DATA: {last_message_item}")
                     return jsonify({"error": f"Could not find text. Item: {last_message_item}"}), 400

        print(f"User asked: {user_text} (Timezone: {user_timezone})")
        
        # --- CALCULATE LIVE DATE AND TIME ---
        # We use the user's timezone for the system prompt
        try:
            tz = pytz.timezone(user_timezone)
            now = datetime.now(tz)
        except:
            now = datetime.now() # Fallback to server time
            
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")
        weekday = now.strftime("%A")
        
        system_prompt = f"""
        You are a helpful assistant connected to Google Workspace.
        
        CRITICAL CONTEXT:
        - User's Timezone: {user_timezone}
        - Current Date: {current_date} ({weekday})
        - Current Time: {current_time}
        
        INSTRUCTIONS:
        1. When the user asks to create an event (e.g., "tomorrow at 2pm"), calculate the ISO 8601 date/time relative to the User's Current Date/Time.
        2. Always include the '{user_timezone}' in the 'time_zone' parameter when calling the 'tool_create_calendar_event' tool.
        """
        
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash-preview-09-2025',
            tools=gemini_tools,
            system_instruction=system_prompt
        )
        
        chat = model.start_chat(history=clean_history)
        
        if user_text:
            response = chat.send_message(user_text)
        else:
            last_item = clean_history.pop() 
            response = chat.send_message(last_item['parts'])

        response_part = response.candidates[0].content.parts[0]
        
        return jsonify({
            "response_part": part_to_dict(response_part),
            "updated_history": history_to_dict(chat.history)
        })

    except Exception as e:
        print(f"Error in /api/chat: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# --- SERVE HTML ---
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

if __name__ == '__main__':
    print("Flask server running...")
    print("Your app will be at: http://localhost:8000")
    app.run(port=8000, debug=True)