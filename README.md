# Google Workspace Agent 🤖📅📧

An AI-powered personal assistant that helps you manage your Google Calendar and Gmail using natural language. Built with Google Gemini 2.0 Flash, Flask, and the Google Workspace APIs.

## 🚀 Features

### 🧠 Smart Scheduling

Ask: "Schedule a meeting for tomorrow at 2 PM"
The agent automatically calculates the date and creates the event.

### 🔍 Email Search

Ask: "Do I have any emails from Google?"
Instantly searches your Gmail inbox and summarizes results.

### ⏰ Live Time Awareness

Understands natural language dates like tomorrow, next Friday, or this afternoon.

### 💬 Contextual Memory

Can continue conversations based on previous prompts.

### ✨ Modern UI

Clean and responsive interface built with Tailwind CSS and supports Markdown responses.

---

## 📦 Prerequisites

Before running this project, make sure you have:

* Python **3.8+**
* A **Google Cloud Project** with Gmail & Calendar APIs enabled
* A **Gemini API Key** from Google AI Studio

---

## ⚙️ Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/google-workspace-agent.git
cd google-workspace-agent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

If requirements.txt is missing:

```bash
pip install flask flask-cors google-generativeai google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client pytz
```

---

### 3. Google Cloud Setup

* Go to Google Cloud Console
* Create a new project
* Enable the following APIs:

  * Gmail API
  * Google Calendar API
* Configure OAuth Consent Screen

  * User Type: External
  * Add your email as Test User
* Create OAuth Client ID

  * Application type: Web application
  * Authorized JavaScript origins:

    * [http://localhost:8000](http://localhost:8000)
    * [http://localhost](http://localhost)
  * Copy your Client ID

---

## 🚀 How to Run

### 1. Set your Gemini API Key

**Windows (PowerShell):**

```powershell
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"
```

**Mac / Linux:**

```bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
```

---

### 2. Start the Server

```bash
python app.py
```

You should see:

```
Flask server running...
```

App URL:
👉 [http://localhost:8000](http://localhost:8000)

---

### 3. Open the App

* Open your browser and go to [http://localhost:8000](http://localhost:8000)
* A Settings modal will appear
* Paste your Google Client ID
* Click Save
* Click Sign in with Google
* Allow the permissions

---

## 💡 Example Commands to Try

* "Do I have any emails about Project X?"
* "Schedule a meeting with the design team for next Tuesday at 10 AM."
* "What is on my calendar for today?"
* "Find the email from HR sent yesterday."

---

## 📸 Screenshots

(Add your screenshot links here)

---

## 🛠️ Tech Stack

* Frontend: HTML, JavaScript, Tailwind CSS
* Backend: Python (Flask)
* AI Model: Google Gemini 2.0 Flash
* APIs: Google Calendar API, Gmail API
* Auth: Google Identity Services (OAuth 2.0)

---

