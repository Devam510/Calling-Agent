# Lessons Learned

> Updated after every correction per `claude.md` Section 3 (Self-Improvement Loop).
> Review this file at the start of each session.

---

## L001 — Android 10+ Call Audio Capture is Blocked
**Mistake pattern:** Assumed `RECORD_AUDIO` could capture in-call audio on Android 10+.
**Reality:** Google locked this down. Apps cannot capture phone call audio without root.
**Rule:** Always verify Android audio permission restrictions before designing the audio pipeline.
**Correct approach:** Speakerphone + mic capture, or physical loopback cable.

---

## L002 — Barge-in Requires Concurrent Tasks, Not Sequential Code
**Mistake pattern:** Wrote sequential `await play_audio()` → `await listen()` which blocks interruption.
**Reality:** Barge-in requires two asyncio tasks running concurrently — one playing, one listening.
**Rule:** Any "interrupt while doing X" pattern needs a `CancellationEvent` + concurrent coroutines.
**Correct approach:** `asyncio.Event` shared between listener task and playback task.

---

## L003 — Silero VAD Silence Threshold Needs Tuning for Hindi
**Mistake pattern:** Assumed default VAD silence thresholds would work.
**Reality:** Hindi conversational speech needs 800–1200ms silence before triggering Whisper, otherwise mid-sentence cuts occur.
**Rule:** Always expose VAD silence duration as a configurable env var. Default Hindi = 900ms.

---

## L004 — Regex Fallback on Mixed Hindi/English Transcripts is Unreliable
**Mistake pattern:** Planned regex as fallback for malformed LLM JSON output.
**Reality:** Regex on mixed-language transcripts is fragile and unpredictable.
**Rule:** Use a second LLM call with a stricter prompt as fallback. Never regex on LLM output.

---

## L005 — Google Sheet "Public Editor Link" Doesn't Bypass API Auth
**Mistake pattern:** Assumed setting a sheet to "Anyone with link can edit" would allow unauthenticated API writes.
**Reality:** The Sheets API always requires an OAuth token, regardless of share settings.
**Rule:** Use `gspread.oauth()` for user-based auth (one-time browser login, cached token). Simpler than a service account.

---

## L006 — Sheet ID vs Sheet URL
**Mistake pattern:** Used `GOOGLE_SHEET_ID` env var requiring manual ID extraction from URL.
**Reality:** `gspread.client.open_by_url(url)` accepts the full URL directly; no ID parsing needed.
**Rule:** Always prefer `open_by_url()` for user-facing config — it's more intuitive and less error-prone.

---

## L007 — Missing State Persistence Causes Sheet Corruption on Crash
**Mistake pattern:** Orchestrator had no checkpointing — a crash mid-call could leave a sheet row partially updated.
**Reality:** Need SQLite session state so the orchestrator knows what state each call was in when it crashed.
**Rule:** Any multi-step async process that writes to external state (DB, sheet, API) needs a local checkpoint store.

---

*(Add new lessons here as they are discovered)*
