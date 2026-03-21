"""
text_to_speech.py — Hindi TTS using Piper.

Supports both full-utterance synthesis and streaming for barge-in support.
All output is raw PCM (16kHz, 16-bit, mono) — the same format the Android
gateway expects for AUDIO_OUT messages.
"""

from __future__ import annotations

import asyncio
import io
import logging
import subprocess
from pathlib import Path
from typing import AsyncGenerator

from backend.config import settings

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2       # 16-bit
CHANNELS = 1
CHUNK_SIZE = 4096      # bytes per streaming chunk


def _piper_cmd() -> list[str]:
    """Build the Piper subprocess command."""
    return [
        "piper",
        "--model", settings.piper_model_path,
        "--output-raw",
        "--sample-rate", str(SAMPLE_RATE),
    ]


def synthesize(text: str) -> bytes:
    """
    Synthesize text to PCM audio (blocking).

    Returns raw PCM bytes (16kHz, 16-bit, mono).
    Raises subprocess.CalledProcessError on Piper failure.
    """
    if not text.strip():
        return b""

    cmd = _piper_cmd()
    result = subprocess.run(
        cmd,
        input=text.encode("utf-8"),
        capture_output=True,
        check=True,
        timeout=30,
    )
    logger.debug("Synthesized %d bytes for text: %.60r", len(result.stdout), text)
    return result.stdout


async def synthesize_streaming(
    text: str,
    chunk_size: int = CHUNK_SIZE,
) -> AsyncGenerator[bytes, None]:
    """
    Async generator that yields PCM chunks as Piper produces them.
    Enables barge-in: the caller can cancel iteration when speech is detected.

    Usage:
        async for chunk in synthesize_streaming("नमस्ते"):
            await call_controller.send_audio(chunk)
    """
    if not text.strip():
        return

    cmd = _piper_cmd()
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Write text to stdin and close
    process.stdin.write(text.encode("utf-8"))
    await process.stdin.drain()
    process.stdin.close()

    # Stream stdout in chunks
    try:
        while True:
            chunk = await process.stdout.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        # Ensure the process is cleaned up even if the generator is cancelled (barge-in)
        if process.returncode is None:
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass  # already died
