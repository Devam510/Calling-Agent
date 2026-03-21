# Calling Agent — Task Tracker

> Managed per `claude.md` workflow conventions.
> Mark items `[x]` when complete; add a **Review** section at the end of each session.

---

## Phase 1: Project Scaffolding & Configuration
- [x] Initialize Python project with `uv` / `pyproject.toml`
- [x] Set up `backend/` package with `__init__.py`
- [x] Create `config.py` with Pydantic `BaseSettings`
- [x] Create `.env.example` with all required variables
- [x] Create `models.py` (Lead, CallResult, RecordingPaths, CallSession)
- [x] Create `tasks/` directory and seed `lessons.md`

## Phase 2: Google Sheets Integration
- [x] Implement `lead_fetcher.py` — OAuth2 login, `open_by_url`, fetch next uncalled lead
- [x] Implement `sheet_updater.py` — update row by id, retry with backoff
- [x] Add `recording_path` column note to README
- [x] Unit test: `test_lead_fetcher.py` (mock gspread)
- [x] Unit test: `test_sheet_updater.py` (mock gspread)

## Phase 3: Android Gateway
- [x] Define WebSocket protocol (START_CALL, END_CALL, CALL_CONNECTED, AUDIO_IN/OUT, events)
- [x] Build Android companion app (Kotlin + OkHttp)
  - [x] `MainActivity.kt` + runtime permissions
  - [x] `GatewayService.kt` — foreground service, telephony control
  - [x] `AudioStreamer.kt` — speakerphone mic capture + TTS playback
  - [x] `WebSocketBridge.kt` — OkHttp WS, JSON protocol
  - [x] `Models.kt` — GatewayCommand / GatewayEvent sealed classes
- [x] Implement `call_controller.py` — WS bridge, start_call, end_call, ringing timeout

## Phase 4: Speech-to-Text
- [x] Implement `speech_to_text.py` — faster-whisper + Silero VAD (900ms silence, L003)

## Phase 5: Text-to-Speech
- [x] Implement `text_to_speech.py` — Piper TTS, blocking + streaming (barge-in ready, L002)

## Phase 5b: Call Recording
- [x] Implement `recording_manager.py` — passive PCM tap (agent + customer tracks)
- [x] Implement `audio_mixer.py` — pydub stereo merge, MP3 export
- [x] Unit test: `test_recording.py`

## Phase 6: LLM Conversation Engine
- [x] Write `prompts/sales_system_prompt.txt` (Hindi Riya persona)
- [x] Write `prompts/analysis_prompt.txt` (post-call JSON extraction)
- [x] Implement `conversation_engine.py` — Groq SDK, stateful history, lead-personalized prompt

## Phase 7: Real-Time Conversation Loop
- [x] Implement `conversation_loop.py` — concurrent barge-in with asyncio CancelledError (L002)

## Phase 8: Session Persistence
- [x] Implement `session_store.py` — JSON-backed crash recovery
- [x] Unit test: `test_session_store.py`

## Phase 9: Post-Call Analysis
- [x] Implement `transcript_analyzer.py` — 2-attempt Groq retry, safe default
- [x] Unit test: `test_transcript_analyzer.py` (malformed JSON → retry)

## Phase 10: Orchestration & Server
- [x] Implement `orchestrator.py` — lead→call→analyze→update loop, inter-call delay
- [x] Implement `server.py` — FastAPI endpoints (/health, /start, /stop, /status)

## Phase 11: Documentation
- [x] Write `README.md` — architecture diagram, quick start, project structure

---

## Bug Fixes & Operational Issues
- [x] Fix Google Sheets column headers (GSpreadException: expected_headers mismatch)
- [/] Fix Piper TTS streaming error: 'Piper' object has no attribute 'synthesize_stream_raw'

---

## Review Log

### Session 1 — 2026-03-21
**Built:** All 11 phases fully implemented.

**Python backend (16 files):**
- `config.py`, `models.py` — foundation
- `lead_fetcher.py`, `sheet_updater.py` — Google Sheets (OAuth2, open_by_url per L005/L006)
- `call_controller.py` — WebSocket bridge to Android
- `speech_to_text.py` — Whisper + Silero VAD, 900ms Hindi silence (L003)
- `text_to_speech.py` — Piper streaming for barge-in (L002)
- `recording_manager.py`, `audio_mixer.py` — dual-track recording
- `conversation_engine.py` — Groq LLM with stateful history
- `conversation_loop.py` — real-time barge-in via concurrent asyncio tasks (L002)
- `session_store.py` — JSON crash recovery
- `transcript_analyzer.py` — post-call analysis
- `orchestrator.py`, `server.py` — FastAPI server + calling loop

**Android companion app (Kotlin):**
- `GatewayService.kt`, `AudioStreamer.kt`, `WebSocketBridge.kt`, `Models.kt`, `MainActivity.kt`
- Speakerphone mic approach — only viable method on Android 10+ without root (L001)

**Tests (5 files):** `test_lead_fetcher`, `test_sheet_updater`, `test_recording`, `test_session_store`, `test_transcript_analyzer`

**Next steps (manual):**
- Install `uv`, run `uv venv && uv pip install -e .`
- Copy `.env.example` → `.env`, fill in `GROQ_API_KEY` and `SHEET_URL`
- Run `uv run python -m backend.lead_fetcher` once for Google OAuth login
- Build & install Android app, set server URL, tap Connect
- Run `uv run python main.py`

### Session 2 — Bug Fixes
- Added a script to proactively write the correct exact headers (`id`, `company_name`, `owner_name`, `phone`, `business_type`, `city`, `called`, `call_status`, `summary`, `followup_date`, `recording_path`) to the user's Google Sheet, resolving the `GSpreadException: expected_headers mismatch`.
