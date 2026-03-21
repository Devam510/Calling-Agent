"""
call_controller.py — WebSocket bridge between the Python backend and the Android gateway.

Responsibilities:
  - Host a WebSocket server (port 8765) for the Android gateway app.
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
from websockets.server import WebSocketServerProtocol
from websockets.connection import State

from backend.config import settings
from backend.models import GatewayMessage, GatewayMessageType

logger = logging.getLogger(__name__)

# Type alias for the audio tap callback
AudioChunkCallback = Callable[[bytes], None]

# Global shared state for the persistent gateway connection
_gateway_ws: Optional[WebSocketServerProtocol] = None
_active_controller: Optional['CallController'] = None


async def _gateway_handler(websocket, *args, **kwargs) -> None:
    """Handle the persistent WebSocket connection from the Android app."""
    global _gateway_ws, _active_controller
    
    if _gateway_ws is not None and _gateway_ws.state == State.OPEN:
        logger.warning("Another gateway tried to connect while one is already active. Closing new connection.")
        return

    _gateway_ws = websocket
    logger.info("Android Gateway connected successfully.")
    
    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
                msg = GatewayMessage(
                    type=GatewayMessageType(data["type"]),
                    payload=data.get("payload", {}),
                )
                if _active_controller:
                    await _active_controller._handle_message(msg)
            except Exception as exc:
                logger.warning("Failed to process gateway message: %s | error: %s", raw, exc)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _gateway_ws = None
        if _active_controller:
            logger.warning("Gateway disconnected during an active call.")
        logger.info("Android Gateway disconnected.")


async def init_gateway_server(host: str = "0.0.0.0", port: int = 8765) -> None:
    """Start the WebSocket server to listen for the Android gateway."""
    logger.info("Starting Gateway WebSocket server on ws://%s:%d ...", host, port)
    await websockets.serve(_gateway_handler, host, port)


class CallController:
    """Manages a single call via the globally connected Android WebSocket gateway."""

    def __init__(self) -> None:
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
        """Attach to the persistent Android gateway WebSocket connection."""
        global _gateway_ws, _active_controller
        
        logger.info("Awaiting Android Gateway connection...")
        while _gateway_ws is None or _gateway_ws.state != State.OPEN:
            await asyncio.sleep(1)

        _active_controller = self
        logger.info("CallController attached to active Gateway connection.")

    async def start_call(self, phone: str) -> bool:
        """
        Send START_CALL and wait for 'connected' state.

        Returns True if the call connected, False on timeout / failure.
        """
        if _active_controller is not self or _gateway_ws is None:
            raise RuntimeError("Not attached to Gateway. Call connect() first.")

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
        if _gateway_ws is not None and _gateway_ws.state == State.OPEN:
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

    async def disconnect(self) -> None:
        """Detach from the Gateway connection (does NOT close the WebSocket)."""
        global _active_controller
        if _active_controller is self:
            _active_controller = None
        self._audio_in_callbacks.clear()
        logger.info("CallController detached from Android Gateway.")

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    async def _send(self, msg: GatewayMessage) -> None:
        global _gateway_ws
        if _gateway_ws is None or _gateway_ws.state != State.OPEN:
            raise RuntimeError("Gateway is not connected.")
        payload = json.dumps({"type": msg.type.value, "payload": msg.payload})
        await _gateway_ws.send(payload)

    async def _handle_message(self, msg: GatewayMessage) -> None:
        """Called defensively by the global WebSocket consumer loop."""
        if msg.type == GatewayMessageType.CALL_STATE:
            state = msg.payload.get("state", "")
            self._call_state = state
            logger.info("Call state changed to: %s", state)
            if state == "connected":
                self._connected_event.set()

        elif msg.type == GatewayMessageType.AUDIO_IN:
            raw_audio = base64.b64decode(msg.payload.get("data", ""))
            for callback in self._audio_in_callbacks:
                callback(raw_audio)
        elif msg.type == GatewayMessageType.ERROR:
            error_msg = msg.payload.get("message", "Unknown error")
            logger.error("Gateway Error: %s", error_msg)
        else:
            logger.debug("Unhandled gateway message type: %s", msg.type)

