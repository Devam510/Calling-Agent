# Autonomous Hindi Voice Calling Agent

A fully automated AI calling agent that reads leads from Google Sheets, places calls through an Android phone gateway, speaks natural Hindi to pitch website development services, and logs outcomes back to the sheet.

---

## Architecture Overview

```
Google Sheet (leads)
       │ read/write
       ▼
  backend/lead_fetcher.py ──► orchestrator.py ──► sheet_updater.py
                                    │
                          ┌─────────┼─────────┐
                          ▼         ▼         ▼
               call_controller.py  →  Android Gateway App
               (WebSocket bridge)        (GatewayService.kt)
                          │                   │
                    audio stream         speakerphone mic
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
       speech_to_text  conversation  text_to_speech
       (Whisper+VAD)    _engine.py   (Piper TTS)
              │           │               │
              └───── conversation_loop.py ─┘
                          │
                 recording_manager.py → audio_mixer.py → MP3
                          │
                 transcript_analyzer.py → sheet_updater.py
                          │
                    session_store.py (crash recovery)
```

---

## Prerequisites

| Component | Requirement |
|---|---|
| Python | ≥ 3.12 |
| [uv](https://github.com/astral-sh/uv) | Package manager |
| Groq API key | Free tier sufficient |
| Android phone | Android 10+, unlimited calling SIM |
| Piper TTS | Hindi voice model (`hi-IN`) |
| faster-whisper | CPU-compatible mode |
| ffmpeg | For audio mixing |

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd "Calling Agent"
uv venv && uv pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set GROQ_API_KEY, SHEET_URL, GATEWAY_WS_URL
```

### 3. Authenticate with Google Sheets (first run only)

```bash
uv run python -m backend.lead_fetcher
# A browser window will open — log in and grant access
# Credentials are cached in ~/.config/gspread/
```

### 4. Install & run the Android gateway app

1. Open `android/` in Android Studio.
2. Build and install on your phone.
3. Enter your PC's local IP in the URL field (e.g. `ws://192.168.1.100:8765`).
4. Tap **Connect** — the gateway is now ready.

> **Speakerphone note:** The app uses the phone's microphone in speakerphone mode to capture both sides of the conversation. This is the only approach that works on modern Android without root.

### 5. Start the backend server

```bash
uv run python main.py
```

The server starts at `http://0.0.0.0:8000`. The orchestrator will:
1. Fetch the next uncalled lead from Google Sheets.
2. Send a `START_CALL` command to the Android gateway.
3. Run the Hindi sales conversation (Riya persona).
4. Save the recording and analyze the transcript.
5. Update the sheet with `called=TRUE`, status, and summary.
6. Loop to the next lead.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/start` | Start the calling loop |
| `POST` | `/stop` | Stop after current call |
| `GET` | `/status` | Current session status |

---

## Project Structure

```
Calling Agent/
├── backend/
│   ├── config.py              # Pydantic settings — all env vars
│   ├── models.py              # Domain models (Lead, CallSession, CallResult…)
│   ├── lead_fetcher.py        # Read next uncalled lead from Google Sheets
│   ├── sheet_updater.py       # Write call results back to sheet
│   ├── call_controller.py     # WebSocket bridge to Android gateway
│   ├── speech_to_text.py      # Whisper + Silero VAD (Hindi, 16kHz)
│   ├── text_to_speech.py      # Piper TTS streaming for barge-in support
│   ├── recording_manager.py   # Dual-track PCM buffer tap
│   ├── audio_mixer.py         # Mix PCM → stereo MP3
│   ├── conversation_engine.py # Groq LLM with stateful history
│   ├── conversation_loop.py   # Real-time barge-in loop (concurrent VAD + TTS)
│   ├── session_store.py       # JSON crash-recovery store
│   ├── orchestrator.py        # Outer call loop + state machine
│   ├── transcript_analyzer.py # Post-call JSON analysis via Groq
│   └── server.py              # FastAPI server + WebSocket endpoint
├── android/                   # Kotlin companion app
│   └── app/src/main/java/com/callingagent/gateway/
│       ├── GatewayService.kt  # Foreground service (owns WS + audio)
│       ├── AudioStreamer.kt   # Speakerphone mic capture + TTS playback
│       ├── WebSocketBridge.kt # OkHttp WebSocket protocol
│       ├── Models.kt          # Command/event sealed classes
│       └── MainActivity.kt    # Simple configuration UI
├── prompts/
│   ├── sales_system_prompt.txt  # Hindi Riya persona
│   └── analysis_prompt.txt      # Post-call JSON analyzer
├── tests/                     # pytest unit tests (all mocked)
├── main.py                    # Entrypoint
├── pyproject.toml
├── .env.example
└── tasks/
    ├── todo.md                # Implementation checklist
    └── lessons.md             # Design decisions & pitfalls
```

---

## Running Tests

```bash
uv run pytest tests/ -v
```

---

## Google Sheet Format

| Column | Description |
|---|---|
| `id` | Unique lead ID |
| `company_name` | Business name |
| `owner_name` | Owner/contact name |
| `phone` | Phone number (E.164 format) |
| `business_type` | e.g. restaurant, shop |
| `city` | City name |
| `called` | `FALSE` → to call, `TRUE` → done |
| `call_status` | interested / not_interested / callback / no_answer |
| `summary` | AI-generated Hindi call summary |
| `followup_date` | Suggested follow-up date (ISO 8601) |

---

## Known Limitations & Design Decisions

- **Android audio capture:** Modern Android 10+ blocks direct call audio capture. The gateway uses speakerphone mode so the mic picks up both sides. A physical audio loopback cable (AUX splitter) gives cleaner audio but is optional.
- **Barge-in:** Implemented via concurrent asyncio tasks — a VAD listener task cancels the TTS speak task when speech is detected.
- **VAD silence threshold:** Tuned to 900ms for Hindi speech patterns (longer pauses than English).
- **Session store:** JSON-backed — survives Python crashes and server restarts.
- **Zero service account:** Uses `gspread.oauth()` which caches OAuth2 user tokens. No service account JSON needed.

---

## License

MIT
