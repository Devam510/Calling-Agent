"""
test_recording.py — Unit tests for RecordingManager and audio_mixer.
"""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
import os

from backend.recording_manager import RecordingManager


def _make_pcm(seconds: float = 0.1, rate: int = 16_000) -> bytes:
    """Generate silent PCM bytes (16-bit, mono)."""
    return b"\x00\x00" * int(rate * seconds)


# ── RecordingManager ──────────────────────────────────────────────────────────

def test_write_and_retrieve_customer():
    r = RecordingManager()
    chunk = _make_pcm(0.5)
    r.write_customer(chunk)
    assert r.get_customer_pcm() == chunk


def test_write_and_retrieve_agent():
    r = RecordingManager()
    chunk = _make_pcm(0.3)
    r.write_agent(chunk)
    assert r.get_agent_pcm() == chunk


def test_is_empty_initially():
    r = RecordingManager()
    assert r.is_empty()


def test_is_not_empty_after_write():
    r = RecordingManager()
    r.write_customer(_make_pcm(0.1))
    assert not r.is_empty()


def test_reset_clears_buffers():
    r = RecordingManager()
    r.write_customer(_make_pcm(0.2))
    r.write_agent(_make_pcm(0.2))
    r.reset()
    assert r.is_empty()


# ── audio_mixer.export_recordings ─────────────────────────────────────────────

@patch("backend.audio_mixer.AudioSegment")
def test_export_creates_three_files(mock_seg_cls, tmp_path):
    """export_recordings should create customer, agent, and stereo files."""
    from backend.audio_mixer import export_recordings
    from backend.config import settings

    # Patch recordings dir to temp dir
    settings.recordings_dir = str(tmp_path)
    settings.recording_format = "mp3"

    r = RecordingManager()
    r.write_customer(_make_pcm(0.5))
    r.write_agent(_make_pcm(0.5))

    # AudioSegment is complex to mock fully — just ensure export is called 3×
    mock_instance = MagicMock()
    mock_seg_cls.return_value = mock_instance
    mock_seg_cls.silent.return_value = mock_instance
    mock_seg_cls.from_mono_audiosegments.return_value = mock_instance
    mock_instance.__add__ = MagicMock(return_value=mock_instance)
    mock_instance.__len__ = MagicMock(return_value=8000)

    paths = export_recordings(r, call_id="test-call-001")

    assert paths.customer_audio.endswith("_customer.mp3")
    assert paths.agent_audio.endswith("_agent.mp3")
    assert paths.mixed_stereo.endswith("_mixed_stereo.mp3")
    assert mock_instance.export.call_count == 3


def test_export_raises_on_empty_recorder(tmp_path):
    """export_recordings should raise ValueError if recorder is empty."""
    from backend.audio_mixer import export_recordings
    from backend.config import settings
    settings.recordings_dir = str(tmp_path)

    r = RecordingManager()  # empty
    with pytest.raises(ValueError, match="empty"):
        export_recordings(r, call_id="empty-call")
