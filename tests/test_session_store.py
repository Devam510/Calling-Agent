"""
test_session_store.py — Unit tests for session_store.py
"""

import asyncio
import pytest
import tempfile
import os

from backend.models import CallSession, CallState
from backend.session_store import SessionStore


@pytest.fixture
async def store(tmp_path):
    db = str(tmp_path / "sessions.db")
    s = SessionStore(db_path=db)
    await s.initialize()
    return s


@pytest.mark.asyncio
async def test_create_and_get(store):
    session = CallSession(
        session_id="abc-123",
        lead_id="lead-1",
        phone="9999900000",
        state=CallState.PENDING,
    )
    await store.create(session)
    retrieved = await store.get("abc-123")
    assert retrieved is not None
    assert retrieved.session_id == "abc-123"
    assert retrieved.state == CallState.PENDING


@pytest.mark.asyncio
async def test_update_state(store):
    session = CallSession(
        session_id="xyz-456",
        lead_id="lead-2",
        phone="8888800000",
        state=CallState.PENDING,
    )
    await store.create(session)
    await store.update_state("xyz-456", CallState.CONNECTED, transcript="Hello")
    retrieved = await store.get("xyz-456")
    assert retrieved.state == CallState.CONNECTED
    assert retrieved.transcript == "Hello"


@pytest.mark.asyncio
async def test_get_incomplete_excludes_done(store):
    for i, state in enumerate([CallState.DONE, CallState.FAILED, CallState.CONNECTED]):
        session = CallSession(
            session_id=f"s-{i}",
            lead_id=f"lead-{i}",
            phone=f"9000000{i:03d}",
            state=state,
        )
        await store.create(session)

    incomplete = await store.get_incomplete()
    assert len(incomplete) == 1
    assert incomplete[0].state == CallState.CONNECTED


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(store):
    result = await store.get("does-not-exist")
    assert result is None
