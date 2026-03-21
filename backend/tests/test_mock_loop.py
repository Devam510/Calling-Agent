import pytest
import asyncio
from backend.conversation_engine import ConversationEngine
from backend.config import settings

@pytest.mark.asyncio
async def test_conversation_engine_responses():
    """Mock the Groq API call to test the engine's streaming logic locally."""
    # This requires an actual GROQ_API_KEY set in .env or the OS env to not fail on client init.
    if not settings.groq_api_key:
        pytest.skip("No GROQ_API_KEY set, skipping LLM test.")
    
    from backend.models import Lead
    dummy_lead = Lead(id="L001", company_name="Test Corp", owner_name="Ravi", phone="+919876543210", business_type="Retail", city="Delhi", row_index=2)
    engine = ConversationEngine(dummy_lead)
    
    first_response = await engine.get_response("[CALL_STARTED]")
    transcript_events = [{"role": "user", "content": "Hello, is this the calling agent?"}]
    
    response = await engine.get_response(transcript_events[0]["content"])
    assert len(response) > 0

    print("Generated mock response:", response)
