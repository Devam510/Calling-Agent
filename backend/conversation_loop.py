"""
conversation_loop.py — Real-time Hindi call conversation with barge-in support.

Architecture (per L002):
  - Two concurrent asyncio tasks per turn:
      speak_task: streams TTS chunks → Android gateway
      listen_task: receives + VAD-buffers customer audio → detects speech
  - A `CancellationEvent` is shared between them.
  - When listen_task detects sustained speech (> VAD_SILENCE_MS),
    it sets the event which causes speak_task to cancel playback.
  - Both taps into RecordingManager for passive recording.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from backend.call_controller import CallController
from backend.config import settings
from backend.conversation_engine import ConversationEngine
from backend.models import Lead
from backend.recording_manager import RecordingManager
from backend.speech_to_text import has_speech, transcribe
from backend.text_to_speech import synthesize_streaming

logger = logging.getLogger(__name__)

SILENCE_THRESHOLD_MS = settings.vad_silence_ms   # L003
CHUNK_DURATION_MS = 20                            # WebSocket audio chunk ≈20ms
CHUNKS_FOR_SILENCE = SILENCE_THRESHOLD_MS // CHUNK_DURATION_MS


async def _speak_with_barge_in(
    text: str,
    controller: CallController,
    recorder: RecordingManager,
    barge_in_event: asyncio.Event,
) -> None:
    """
    Stream TTS to the gateway. Stop early if barge_in_event is set.
    Records every chunk to recorder.write_agent().
    """
    async for pcm_chunk in synthesize_streaming(text):
        if barge_in_event.is_set():
            logger.info("Barge-in detected — aborting playback.")
            break
        recorder.write_agent(pcm_chunk)
        await controller.send_audio(pcm_chunk)


async def _listen_for_speech(
    audio_queue: asyncio.Queue,
    barge_in_event: asyncio.Event,
) -> bytes:
    """
    Drain the audio queue, run VAD, accumulate speech, detect silence boundary.

    Returns:
        All PCM bytes that constitute the customer's utterance.

    Sets barge_in_event as soon as initial speech is detected.
    """
    speech_pcm = bytearray()
    silence_chunks = 0
    speaking = False

    while True:
        try:
            chunk: bytes = await asyncio.wait_for(audio_queue.get(), timeout=5.0)
        except asyncio.TimeoutError:
            break   # no more audio — assume end of utterance

        if has_speech(chunk):
            speaking = True
            silence_chunks = 0
            speech_pcm.extend(chunk)
            if not barge_in_event.is_set():
                barge_in_event.set()   # signal playback to stop
        else:
            if speaking:
                silence_chunks += 1
                speech_pcm.extend(chunk)   # include trailing silence
                if silence_chunks >= CHUNKS_FOR_SILENCE:
                    break   # silence boundary reached — utterance complete

    return bytes(speech_pcm)


async def run_conversation(
    lead: Lead,
    controller: CallController,
    recorder: RecordingManager,
) -> str:
    """
    Run the full call conversation loop.

    Yields turns until:
      - Max turns reached
      - The call state goes to "ended" / "failed"
      - The LLM generates an end-of-call signal

    Returns:
        Full transcript string for post-call analysis.
    """
    engine = ConversationEngine(lead)

    # Queue that receives PCM chunks from the CallController's audio tap
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
    controller.register_audio_tap(audio_queue.put_nowait)

    # Opening greeting — no barge-in for first turn
    greeting = (
        f"नमस्ते! मैं Riya बोल रही हूं, WebPro Solutions से। "
        f"क्या मैं {lead.owner_name} जी से बात कर सकती हूं?"
    )
    logger.info("Starting conversation with greeting")
    async for pcm_chunk in synthesize_streaming(greeting):
        recorder.write_agent(pcm_chunk)
        await controller.send_audio(pcm_chunk)

    for turn in range(settings.max_conversation_turns):
        logger.info("Turn %d/%d", turn + 1, settings.max_conversation_turns)
        barge_in_event = asyncio.Event()

        # next agent line will be prepared after we know what customer said
        # but we need to speak the previous reply first (done in prior turn)
        # so here we just listen for customer utterance

        # Listen to customer (with possible barge-in on any ongoing audio)
        customer_pcm = await _listen_for_speech(audio_queue, barge_in_event)
        recorder.write_customer(customer_pcm)

        transcript = transcribe(customer_pcm)
        if not transcript.strip():
            logger.info("Empty transcript — skipping turn")
            continue

        logger.info("Customer said: %r", transcript)
        reply = engine.chat(transcript)
        logger.info("Agent reply: %r", reply)

        # Speak reply with barge-in support
        barge_in_event = asyncio.Event()
        speak_task = asyncio.create_task(
            _speak_with_barge_in(reply, controller, recorder, barge_in_event)
        )
        listen_task = asyncio.create_task(
            _listen_for_speech(audio_queue, barge_in_event)
        )

        # Wait for both — speak may be cut short by listen
        _, customer_pcm = await asyncio.gather(speak_task, listen_task)

        # If barge-in happened, process that audio immediately in next iteration
        if barge_in_event.is_set() and customer_pcm:
            recorder.write_customer(customer_pcm)
            transcript = transcribe(customer_pcm)
            if transcript.strip():
                reply = engine.chat(transcript)
                logger.info("Barge-in reply: %r", reply)
                # Speak the reply in the next turn
                barge_in_event = asyncio.Event()
                async for pcm_chunk in synthesize_streaming(reply):
                    if barge_in_event.is_set():
                        break
                    recorder.write_agent(pcm_chunk)
                    await controller.send_audio(pcm_chunk)

    return engine.get_full_transcript()
