# Autonomous Hindi Voice Calling Agent

An intelligent, low-latency conversational voice agent designed to autonomously dial leads from a Google Sheet, converse in natural Hindi/Hinglish, negotiate sales, and record the results.

## Features
- **Local SQLite State:** Crash-resilient calling queue using `aiosqlite`.
- **Google Sheets Sync:** Pulls leads and updates statuses/summaries/transcripts directly to Google Sheets.
- **Fast <1.5s Latency:** Streams microphone and speaker audio via WebSockets to/from an Android gateway app.
- **Hindi Speech-to-Text:** Uses `faster-whisper` optimized for Hindi/Hinglish.
- **LLM Conversation:** Powered by Groq (Llama-3-70b/8b or similar) for blazing fast inference, instructed with a strict Hindi salesperson persona.
- **Hindi Text-to-Speech:** Uses locally run `piper-tts` with an Indian voice model for quick syntheses.
- **Full Call Recording:** Merges customer and agent audio into an MP3 file saved locally and links it in Google Sheets.
- **Real-Time Interruption Handling:** Detects when the user speaks over the agent using VAD and halts TTS.

## Prerequisites
- Python 3.12+
- `uv` package manager
- **FFmpeg**: Must be installed and available in `$PATH` for Piper TTS and Pydub to process audio.
- [Piper TTS Hindi Voice Model](https://github.com/rhasspy/piper/releases/): Download `hi_IN-swara-medium.onnx` and place it in the project root.

## Setup

1. **Install Dependencies**
   ```bash
   uv venv
   # On Windows: .venv\Scripts\activate
   # On Linux/macOS: source .venv/bin/activate
   uv pip install -r pyproject.toml
   ```

2. **Google Service Account Credentials**
   Create a Google Cloud Project with Google Sheets API enabled. Create a Service Account and download the JSON key. Save it to `credentials.json` in the project root.
   Share your target Google Sheet with the Service Account email.

3. **Environment Setup**
   Copy `.env.example` to `.env` (or setup manually) and define your values:
   ```env
   GROQ_API_KEY=your_groq_api_key
   GOOGLE_CREDENTIALS_PATH=credentials.json
   SPREADSHEET_ID=your_google_sheet_id
   ANDROID_GATEWAY_WS_URL=ws://192.168.x.x:8080/call
   ```

## Running the Agent

You can run the agent in different modes using `main.py`:

**Start the Continuous Calling Loop**
```bash
uv run python main.py
```

**Call a Specific Number of Leads**
```bash
uv run python main.py --batch 5
```

**Call Just One Lead**
```bash
uv run python main.py --once
```

**Start the API Server Only** (For remote control and status checks)
```bash
uv run python main.py --serve
```

## Architecture

1. **Orchestrator (`backend/orchestrator.py`)**: Fetches leads, updates SQLite session state, drives the call lifecycle.
2. **Conversation Loop (`backend/conversation_loop.py`)**: The tight async loop that manages STT queue, LLM generation, and TTS streaming, including barge-ins.
3. **Android Gateway (`backend/call_controller.py`)**: Exposes methods to dial numbers, bridge audio, and hang up.
4. **Google Sheets (`backend/lead_fetcher.py`, `backend/sheet_updater.py`)**: Two-way sync with the lead database.
5. **Speech (`backend/speech_to_text.py`, `backend/text_to_speech.py`)**: Audio I/O using local ML models.
6. **LLM (`backend/conversation_engine.py`, `backend/transcript_analyzer.py`)**: The brains of the agent using Groq's low-latency endpoints.

## License
Proprietary. All rights reserved.
