"""
session_store.py — SQLite-backed call session persistence.

Implements L007: Any multi-step async process writing to external state
needs a local checkpoint store to survive crashes.

Schema:
  sessions(session_id TEXT PK, lead_id TEXT, phone TEXT, state TEXT,
           transcript TEXT, recording_path TEXT, error TEXT, updated_at TEXT)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from backend.config import settings
from backend.models import CallSession, CallState

logger = logging.getLogger(__name__)


class SessionStore:
    """SQLite-backed async session store for call state checkpointing."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or settings.session_db_path

    async def initialize(self) -> None:
        """Create the sessions table if it doesn't exist."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id      TEXT PRIMARY KEY,
                    lead_id         TEXT NOT NULL,
                    phone           TEXT NOT NULL,
                    state           TEXT NOT NULL,
                    transcript      TEXT DEFAULT '',
                    recording_path  TEXT DEFAULT '',
                    error           TEXT DEFAULT '',
                    updated_at      TEXT NOT NULL
                )
            """)
            await db.commit()
        logger.info("SessionStore initialized at %s", self._db_path)

    async def create(self, session: CallSession) -> None:
        """Persist a new session."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO sessions
                    (session_id, lead_id, phone, state, transcript, recording_path, error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.lead_id,
                    session.phone,
                    session.state.value,
                    session.transcript,
                    session.recording_path,
                    session.error or "",
                    _now(),
                ),
            )
            await db.commit()

    async def update_state(
        self,
        session_id: str,
        state: CallState,
        *,
        transcript: Optional[str] = None,
        recording_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update the call state and optional fields."""
        fields = ["state = ?", "updated_at = ?"]
        values: list = [state.value, _now()]

        if transcript is not None:
            fields.append("transcript = ?")
            values.append(transcript)
        if recording_path is not None:
            fields.append("recording_path = ?")
            values.append(recording_path)
        if error is not None:
            fields.append("error = ?")
            values.append(error)

        values.append(session_id)
        sql = f"UPDATE sessions SET {', '.join(fields)} WHERE session_id = ?"

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(sql, values)
            await db.commit()

    async def get(self, session_id: str) -> Optional[CallSession]:
        """Retrieve a session by ID."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return _row_to_session(row)

    async def get_incomplete(self) -> list[CallSession]:
        """Return sessions that were interrupted (not DONE or FAILED)."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT * FROM sessions WHERE state NOT IN ('done', 'failed')"
            ) as cursor:
                rows = await cursor.fetchall()
                return [_row_to_session(r) for r in rows]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_session(row: tuple) -> CallSession:
    return CallSession(
        session_id=row[0],
        lead_id=row[1],
        phone=row[2],
        state=CallState(row[3]),
        transcript=row[4],
        recording_path=row[5],
        error=row[6] or None,
    )
