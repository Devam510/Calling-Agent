"""
models.py — Domain models for the calling agent.

All business objects in one place. Import these everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Lead — read from Google Sheets
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Lead:
    """Represents one business lead row from the Google Sheet."""
    row_index: int           # 1-based row number in the sheet (for updates)
    id: str
    company_name: str
    owner_name: str
    phone: str
    business_type: str
    city: str
    called: bool = False
    call_status: str = ""
    summary: str = ""
    followup_date: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Call State — persisted in SQLite (session_store.py)
# ─────────────────────────────────────────────────────────────────────────────

class CallState(str, Enum):
    PENDING   = "pending"
    DIALING   = "dialing"
    CONNECTED = "connected"
    ANALYZING = "analyzing"
    DONE      = "done"
    FAILED    = "failed"


@dataclass
class CallSession:
    """Checkpointed state for a single call attempt — survives crashes (L007)."""
    session_id: str
    lead_id: str
    phone: str
    state: CallState = CallState.PENDING
    transcript: str = ""
    recording_path: str = ""
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Recording paths — returned by audio_mixer.py
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RecordingPaths:
    """Paths to the three recording files produced per call."""
    customer_audio: str       # customer-side audio
    agent_audio: str          # Riya's TTS output
    mixed_stereo: str         # L=customer, R=agent interleaved

    def primary_path(self) -> str:
        """Return the most useful single path to log in the sheet."""
        return self.mixed_stereo


# ─────────────────────────────────────────────────────────────────────────────
# Call Result — produced by transcript_analyzer.py
# ─────────────────────────────────────────────────────────────────────────────

class CallStatus(str, Enum):
    INTERESTED    = "interested"
    NOT_INTERESTED = "not_interested"
    FOLLOW_UP     = "follow_up"
    NO_ANSWER     = "no_answer"
    BUSY          = "busy"
    WRONG_NUMBER  = "wrong_number"
    DO_NOT_CALL   = "do_not_call"
    FAILED        = "failed"


@dataclass
class CallResult:
    """Final outcome written back to Google Sheets."""
    status: CallStatus
    summary: str
    followup_date: Optional[str] = None          # ISO date string "YYYY-MM-DD"
    recording_path: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket message types (shared with Android app)
# ─────────────────────────────────────────────────────────────────────────────

class GatewayMessageType(str, Enum):
    # Server → Android
    START_CALL  = "START_CALL"
    SEND_DTMF   = "SEND_DTMF"
    END_CALL    = "END_CALL"
    AUDIO_OUT   = "AUDIO_OUT"    # Base64-encoded PCM chunk → speaker

    # Android → Server
    CALL_STATE  = "CALL_STATE"   # ringing | connected | ended | failed
    AUDIO_IN    = "AUDIO_IN"     # Base64-encoded PCM chunk ← mic
    DTMF_ACK    = "DTMF_ACK"
    ERROR       = "ERROR"


@dataclass
class GatewayMessage:
    """Single WebSocket frame between server and Android gateway."""
    type: GatewayMessageType
    payload: dict = field(default_factory=dict)
