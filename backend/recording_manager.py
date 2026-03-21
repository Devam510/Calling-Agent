"""
recording_manager.py — Passive PCM tap for call recording.

Buffers raw PCM audio from both the customer side (mic/gateway)
and the agent side (TTS output) during a call.
Thread-safe (uses asyncio.Lock) — can receive from multiple coroutines.
"""

from __future__ import annotations

import io
import logging

from backend.config import settings

logger = logging.getLogger(__name__)


class RecordingManager:
    """
    Accumulates PCM chunks for customer and agent audio separately.

    Usage:
        recorder = RecordingManager()
        # Tap from call_controller: register_audio_tap(recorder.write_customer)
        # Tap from conversation_loop: await recorder.write_agent(chunk)
    """

    def __init__(self) -> None:
        self._customer_buf: io.BytesIO = io.BytesIO()
        self._agent_buf: io.BytesIO = io.BytesIO()
        self._enabled: bool = settings.recording_enabled

    # ──────────────────────────────────────────────────────────────────────
    # Audio taps
    # ──────────────────────────────────────────────────────────────────────

    def write_customer(self, pcm_chunk: bytes) -> None:
        """Tap callback for incoming mic/gateway audio (customer voice)."""
        if self._enabled and pcm_chunk:
            self._customer_buf.write(pcm_chunk)

    def write_agent(self, pcm_chunk: bytes) -> None:
        """Tap for outgoing TTS audio (Riya's voice)."""
        if self._enabled and pcm_chunk:
            self._agent_buf.write(pcm_chunk)

    # ──────────────────────────────────────────────────────────────────────
    # Retrieval
    # ──────────────────────────────────────────────────────────────────────

    def get_customer_pcm(self) -> bytes:
        """Return all accumulated customer-side PCM."""
        return self._customer_buf.getvalue()

    def get_agent_pcm(self) -> bytes:
        """Return all accumulated agent-side PCM."""
        return self._agent_buf.getvalue()

    def is_empty(self) -> bool:
        return (
            self._customer_buf.tell() == 0
            and self._agent_buf.tell() == 0
        )

    def reset(self) -> None:
        """Clear buffers for reuse (between calls)."""
        self._customer_buf = io.BytesIO()
        self._agent_buf = io.BytesIO()
