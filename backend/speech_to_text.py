"""
speech_to_text.py — Hindi speech recognition using faster-whisper + Silero VAD.

Design notes:
  - L003: VAD silence threshold configured at 900ms for Hindi.
  - Audio arrives as PCM bytes (16kHz, 16-bit, mono) from the Android gateway.
  - Returns a transcript string, empty if no speech detected.
"""

from __future__ import annotations

import io
import logging
import wave
from typing import Optional

import numpy as np
import torch

from backend.config import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lazy model loaders — load once at first use
# ─────────────────────────────────────────────────────────────────────────────

_whisper_model = None
_vad_model = None
_vad_utils = None


def _load_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper model: %s on %s", settings.whisper_model, settings.whisper_device)
        _whisper_model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type="int8",
        )
    return _whisper_model


def _load_vad():
    global _vad_model, _vad_utils
    if _vad_model is None:
        logger.info("Loading Silero VAD model")
        _vad_model, _vad_utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=True,
        )
    return _vad_model, _vad_utils


# ─────────────────────────────────────────────────────────────────────────────
# Audio buffer management
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2  # 16-bit PCM


def pcm_to_wav_bytes(pcm: bytes) -> bytes:
    """Wrap raw PCM bytes in a WAV container (in-memory)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


def has_speech(pcm_chunk: bytes, threshold: float = 0.5) -> bool:
    """
    Quick VAD check on a small PCM chunk.

    L003: silence window of VAD_SILENCE_MS / 1000 seconds is handled by the
    caller (conversation_loop.py) which accumulates chunks until this returns
    False for long enough before triggering transcription.
    """
    model, _ = _load_vad()
    audio_np = np.frombuffer(pcm_chunk, dtype=np.int16).astype(np.float32) / 32768.0
    audio_tensor = torch.from_numpy(audio_np)
    speech_prob = model(audio_tensor, SAMPLE_RATE).item()
    return speech_prob >= threshold


def transcribe(pcm: bytes, language: str = "hi") -> str:
    """
    Transcribe PCM audio bytes to text using faster-whisper.

    Args:
        pcm:      Raw PCM audio (16kHz, 16-bit, mono).
        language: ISO-639-1 language code. 'hi' for Hindi.

    Returns:
        Transcript text. Empty string if nothing was recognized.
    """
    if not pcm:
        return ""

    model = _load_whisper()
    wav_bytes = pcm_to_wav_bytes(pcm)
    audio_io = io.BytesIO(wav_bytes)

    segments, info = model.transcribe(
        audio_io,
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={
            "min_silence_duration_ms": settings.vad_silence_ms,  # L003
        },
    )

    transcript = " ".join(seg.text.strip() for seg in segments).strip()
    logger.debug("Transcribed [%s]: %r", info.language, transcript)
    return transcript
