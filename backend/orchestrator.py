"""
orchestrator.py — Main entry point for the calling loop.

Workflow per lead (L007 crash safety):
  1. Fetch next uncalled lead from Google Sheets.
  2. Create SQLite session (PENDING → DIALING).
  3. Mark lead as called in sheet immediately (pre-dial guard).
  4. Connect to Android gateway and START_CALL.
  5. If connection fails → FAILED, update sheet.
  6. Run conversation loop (CONNECTED).
  7. Export recordings (if enabled).
  8. Analyze transcript (ANALYZING).
  9. Update sheet with result (DONE).
  10. Randomized inter-call delay.
  11. Repeat.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from typing import Optional

from backend.audio_mixer import export_recordings
from backend.call_controller import CallController
from backend.config import settings
from backend.conversation_loop import run_conversation
from backend.lead_fetcher import fetch_next_lead
from backend.models import CallResult, CallState, CallStatus, Lead
from backend.recording_manager import RecordingManager
from backend.session_store import SessionStore
from backend.sheet_updater import mark_lead_called, update_lead_result
from backend.transcript_analyzer import analyze_transcript

logger = logging.getLogger(__name__)


async def _run_single_call(
    lead: Lead,
    session_store: SessionStore,
) -> None:
    """Execute one complete call cycle for a single lead."""
    session_id = str(uuid.uuid4())
    recorder = RecordingManager()
    controller = CallController()

    # ── 1. Create session ────────────────────────────────────────────────
    from backend.models import CallSession
    session = CallSession(
        session_id=session_id,
        lead_id=lead.id,
        phone=lead.phone,
        state=CallState.DIALING,
    )
    await session_store.create(session)

    # ── 2. Pre-dial guard — mark as called before dialing ─────────────────
    try:
        mark_lead_called(lead)
    except Exception as exc:
        logger.error("Could not mark lead %s as called: %s", lead.id, exc)

    # ── 3. Connect + dial ────────────────────────────────────────────────
    try:
        await controller.connect()
        # Register recording tap for customer audio
        controller.register_audio_tap(recorder.write_customer)

        connected = await controller.start_call(lead.phone)
        if not connected:
            logger.warning("Call to %s did not connect — no_answer", lead.phone)
            result = CallResult(
                status=CallStatus.NO_ANSWER,
                summary="Call rang but was not answered.",
            )
            update_lead_result(lead, result)
            await session_store.update_state(session_id, CallState.DONE)
            return
    except Exception as exc:
        logger.error("Gateway error calling %s: %s", lead.phone, exc)
        await session_store.update_state(session_id, CallState.FAILED, error=str(exc))
        return
    finally:
        pass  # controller.disconnect() called in finally below

    # ── 4. Conversation ──────────────────────────────────────────────────
    transcript = ""
    try:
        await session_store.update_state(session_id, CallState.CONNECTED)
        transcript = await run_conversation(lead, controller, recorder)
        await session_store.update_state(session_id, CallState.ANALYZING, transcript=transcript)
    except Exception as exc:
        logger.error("Conversation error: %s", exc)
        await session_store.update_state(session_id, CallState.FAILED, error=str(exc))
        transcript = "Conversation failed."
    finally:
        await controller.end_call()
        await controller.disconnect()

    # ── 5. Export recordings ────────────────────────────────────────────
    recording_path = ""
    if settings.recording_enabled and not recorder.is_empty():
        try:
            paths = export_recordings(recorder, call_id=session_id)
            recording_path = paths.primary_path()
            await session_store.update_state(
                session_id, CallState.ANALYZING, recording_path=recording_path
            )
        except Exception as exc:
            logger.warning("Recording export failed: %s", exc)

    # ── 6. Analyze + update sheet ────────────────────────────────────────
    result = analyze_transcript(transcript)
    result.recording_path = recording_path
    try:
        update_lead_result(lead, result)
    except Exception as exc:
        logger.error("Sheet update failed for lead %s: %s", lead.id, exc)

    await session_store.update_state(session_id, CallState.DONE)
    logger.info(
        "Call complete — lead=%s status=%s session=%s",
        lead.id, result.status.value, session_id,
    )


async def run_batch(max_calls: Optional[int] = None) -> None:
    """
    Fetch and call leads until exhausted or max_calls reached.

    Args:
        max_calls: If set, stop after this many calls. None = run forever.
    """
    session_store = SessionStore()
    await session_store.initialize()

    calls_made = 0
    while True:
        if max_calls is not None and calls_made >= max_calls:
            logger.info("Reached max_calls=%d — stopping.", max_calls)
            break

        lead = fetch_next_lead()
        if lead is None:
            logger.info("No more uncalled leads. Batch complete.")
            break

        logger.info("Processing lead %s (%s, %s)", lead.id, lead.company_name, lead.phone)
        await _run_single_call(lead, session_store)
        calls_made += 1

        # Inter-call delay to avoid SIM flagging
        delay = random.uniform(
            settings.inter_call_delay_min_sec,
            settings.inter_call_delay_max_sec,
        )
        logger.info("Waiting %.0fs before next call…", delay)
        await asyncio.sleep(delay)
