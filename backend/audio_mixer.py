"""
audio_mixer.py — Mix PCM buffers into customer/agent/stereo audio files.

Dependencies: pydub (wraps ffmpeg).
Output format is configurable (default: mp3).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.models import RecordingPaths
from backend.recording_manager import RecordingManager

logger = logging.getLogger(__name__)

# pydub uses the `audioop` module which was removed in Python 3.13.
# The `pyaudioop` shim is not always available either.
# We import at module level so that:
#   (a) the name `AudioSegment` exists for @patch() in tests, and
#   (b) import failures don't crash the whole backend on startup.
try:
    from pydub import AudioSegment  # type: ignore[import]
except (ImportError, ModuleNotFoundError):
    AudioSegment = None  # type: ignore[assignment,misc]
    logger.warning(
        "pydub.AudioSegment could not be imported (audioop/pyaudioop missing). "
        "Call recording export will not work until pydub is installed with a "
        "Python-3.13-compatible build."
    )

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2   # 16-bit
CHANNELS = 1


def _pcm_to_segment(pcm: bytes) -> Any:
    """Convert raw PCM bytes to a pydub AudioSegment."""
    if AudioSegment is None:
        raise RuntimeError("AudioSegment is not available (pydub missing audioop).")
    return AudioSegment(
        data=pcm,
        sample_width=SAMPLE_WIDTH,
        frame_rate=SAMPLE_RATE,
        channels=CHANNELS,
    )


def _pad_to_equal(seg_a: Any, seg_b: Any) -> tuple[Any, Any]:
    """Pad the shorter segment with silence so both have the same duration."""
    if AudioSegment is None:
        raise RuntimeError("AudioSegment is not available (pydub missing audioop).")
    diff = len(seg_a) - len(seg_b)
    if diff > 0:
        seg_b = seg_b + AudioSegment.silent(duration=diff, frame_rate=SAMPLE_RATE)
    elif diff < 0:
        seg_a = seg_a + AudioSegment.silent(duration=-diff, frame_rate=SAMPLE_RATE)
    return seg_a, seg_b


def export_recordings(recorder: RecordingManager, call_id: str) -> RecordingPaths:
    """
    Export buffered PCM from the recorder into audio files.

    Files created:
        <recordings_dir>/<call_id>_customer.<fmt>
        <recordings_dir>/<call_id>_agent.<fmt>
        <recordings_dir>/<call_id>_mixed_stereo.<fmt>

    Returns:
        RecordingPaths with paths to all three files.

    Raises:
        ValueError: if the recorder has no audio at all.
    """
    fmt = settings.recording_format
    out_dir = Path(settings.recordings_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    customer_pcm = recorder.get_customer_pcm()
    agent_pcm = recorder.get_agent_pcm()

    if not customer_pcm and not agent_pcm:
        raise ValueError("RecordingManager is empty — nothing to export.")

    if AudioSegment is None:
        logger.error("Cannot export recordings: pydub is missing.")
        raise RuntimeError("AudioSegment is not available (pydub missing audioop).")

    # Pad with silence if one side is empty
    if not customer_pcm:
        customer_pcm = bytes(len(agent_pcm)) * SAMPLE_WIDTH
    if not agent_pcm:
        agent_pcm = bytes(len(customer_pcm)) * SAMPLE_WIDTH

    customer_seg = _pcm_to_segment(customer_pcm)
    agent_seg = _pcm_to_segment(agent_pcm)

    # Export individual tracks
    customer_path = str(out_dir / f"{call_id}_customer.{fmt}")
    agent_path = str(out_dir / f"{call_id}_agent.{fmt}")
    customer_seg.export(customer_path, format=fmt)
    agent_seg.export(agent_path, format=fmt)

    # Build stereo (L=customer, R=agent) and export
    customer_seg, agent_seg = _pad_to_equal(customer_seg, agent_seg)
    stereo = AudioSegment.from_mono_audiosegments(customer_seg, agent_seg)
    stereo_path = str(out_dir / f"{call_id}_mixed_stereo.{fmt}")
    stereo.export(stereo_path, format=fmt)

    logger.info(
        "Recordings saved: customer=%s agent=%s stereo=%s",
        customer_path, agent_path, stereo_path,
    )

    return RecordingPaths(
        customer_audio=customer_path,
        agent_audio=agent_path,
        mixed_stereo=stereo_path,
    )
