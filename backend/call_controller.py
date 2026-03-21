"""
call_controller.py — WebSocket bridge between the Python backend and the Android gateway.

Responsibilities:
  - Open a WebSocket connection to the Android gateway app.
  - Send START_CALL, END_CALL, SEND_DTMF, AUDIO_OUT messages.
  - Receive CALL_STATE and AUDIO_IN messages.
  - Apply ringing timeout (L003 / config: CALL_RING_TIMEOUT_SEC).
  - Tap incoming audio into the RecordingManager for passive recording.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncGenerator, Callable, Optional

import websockets
from websockets.connection import State

from backend.config import settings
from backend.models import GatewayMessage, GatewayMessageType

logger = logging.getLogger(__name__)

# Type alias for the audio tap callback
AudioChunkCallback = Callable[[bytes], None]


class CallController:
    """Manages a single call via the Android WebSocket gateway."""

    def __init__(self) -> None:
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._call_state: str = "idle"
        self._audio_in_callbacks: list[AudioChunkCallback] = []
        self._connected_event = asyncio.Event()

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def register_audio_tap(self, callback: AudioChunkCallback) -> None:
        """Register a callback that receives every incoming PCM audio chunk."""
        self._audio_in_callbacks.append(callback)

    async def connect(self) -> None:
        """Connect to the Android gateway WebSocket server."""
        url = settings.android_gateway_ws_url
        logger.info("Connecting to Android gateway: %s", url)
        self._ws = await websockets.connect(url)
        logger.info("Connected to Android gateway.")

    async def start_call(self, phone: str) -> bool:
        """
        Send START_CALL and wait for 'connected' state.

        Returns True if the call connected, False on timeout / failure.
        """
        if self._ws is None:
            raise RuntimeError("Not connected. Call connect() first.")

        self._connected_event.clear()
        self._call_state = "dialing"

        msg = GatewayMessage(
            type=GatewayMessageType.START_CALL,
            payload={"phone": phone},
        )
        await self._send(msg)
        logger.info("Sent START_CALL to %s", phone)

        try:
            await asyncio.wait_for(
                self._connected_event.wait(),
                timeout=settings.call_ring_timeout_sec,
            )
            return True
        except asyncio.TimeoutError:
            logger.warning("Ringing timeout after %ds — hanging up.", settings.call_ring_timeout_sec)
            await self.end_call()
            return False

    async def end_call(self) -> None:
        """Send END_CALL to the Android gateway."""
        await self._send(GatewayMessage(type=GatewayMessageType.END_CALL))
        self._call_state = "ending"
        logger.info("Sent END_CALL.")

    async def send_dtmf(self, digits: str) -> None:
        """Send DTMF tones (for IVR navigation)."""
        await self._send(GatewayMessage(
            type=GatewayMessageType.SEND_DTMF,
            payload={"digits": digits},
        ))
        logger.debug("Sent DTMF: %s", digits)

    async def send_audio(self, pcm_chunk: bytes) -> None:
        """Stream a PCM audio chunk to the Android speaker (agent TTS output)."""
        encoded = base64.b64encode(pcm_chunk).decode()
        await self._send(GatewayMessage(
            type=GatewayMessageType.AUDIO_OUT,
            payload={"data": encoded},
        ))

    async def receive_loop(self) -> None:
        """
        Continuously receive messages from the Android gateway.
        Should be run as a background asyncio task.
        """
        if self._ws is None:
            raise RuntimeError("Not connected.")

        async for raw in self._ws:
            try:
                data = json.loads(raw)
                msg = GatewayMessage(
                    type=GatewayMessageType(data["type"]),
                    payload=data.get("payload", {}),
                )
                await self._handle_message(msg)
            except Exception as exc:
                logger.warning("Malformed gateway message: %s | error: %s", raw, exc)

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._ws and self._ws.state == State.OPEN:
            await self._ws.close()
            logger.info("Disconnected from Android gateway.")

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    async def _send(self, msg: GatewayMessage) -> None:
        if self._ws is None:
            raise RuntimeError("Not connected.")
        payload = json.dumps({"type": msg.type.value, "payload": msg.payload})
        await self._ws.send(payload)

    async def _handle_message(self, msg: GatewayMessage) -> None:
        if msg.type == GatewayMessageType.CALL_STATE:
            state = msg.payload.get("state", "")
            self._call_state = state
            logger.info("Call state: %s", state)
            if state == "connected":
                self._connected_event.set()

        elif msg.type == GatewayMessageType.AUDIO_IN:
            raw_audio = base64.b64decode(msg.payload.get("data", ""))
            for callback in self._audio_in_callbacks:
                callback(raw_audio)
