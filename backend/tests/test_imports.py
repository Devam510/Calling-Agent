import pytest
from backend.config import settings, Settings
from backend.session_store import SessionStore
from backend.lead_fetcher import fetch_next_lead
from backend.orchestrator import run_batch
from backend.speech_to_text import SpeechToText
from backend.text_to_speech import TextToSpeech
from backend.audio_mixer import export_recordings
from backend.call_controller import CallController

def test_imports():
    """Verify that all major components can be imported successfully."""
    assert settings is not None
    assert Settings is not None
    assert SessionStore is not None
    assert fetch_next_lead is not None
    assert run_batch is not None
    assert SpeechToText is not None
    assert TextToSpeech is not None
    assert export_recordings is not None
    assert CallController is not None

@pytest.mark.asyncio
async def test_session_store_creation():
    store = SessionStore()
    await store.initialize()
    import uuid
    from backend.models import Lead, CallSession
    dummy_lead = Lead(id="L001", company_name="Test Corp", owner_name="Ravi", phone="+919876543210", business_type="Retail", city="Delhi", row_index=2)
    session_id = f"S_TEST_{uuid.uuid4().hex}"
    session = CallSession(session_id=session_id, lead_id=dummy_lead.id, phone=dummy_lead.phone)
    await store.create(session)
    session_id = session.session_id
    assert session_id is not None
    session_data = await store.get(session_id)
    assert session_data is not None
    assert session_data.phone == "+919876543210"
    assert session_data.state.value == "pending"
