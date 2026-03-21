import pytest
from unittest.mock import AsyncMock, patch
from backend.models import Lead
from backend.conversation_engine import ConversationEngine, _load_system_prompt

@pytest.fixture
def sample_lead():
    return Lead(
        row_index=1,
        id="test-1",
        company_name="Acme Corp",
        owner_name="Rahul",
        phone="123",
        business_type="Retail",
        city="Mumbai"
    )

def test_load_system_prompt(sample_lead):
    prompt = _load_system_prompt(sample_lead)
    assert "Acme Corp" in prompt
    assert "Rahul" in prompt

@pytest.mark.asyncio
async def test_get_response(sample_lead):
    mock_client = AsyncMock()
    # Setup mock response
    mock_choice = AsyncMock()
    mock_choice.message.content = "Namaste Rahul! Kaise hain aap?"
    mock_response = AsyncMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    engine = ConversationEngine(lead=sample_lead, client=mock_client)
    
    # Test [CALL_STARTED] behavior
    resp = await engine.get_response("[CALL_STARTED]")
    assert resp == "Namaste Rahul! Kaise hain aap?"
    assert len(engine.history) == 2 # 1 system prompt + 1 assistant reply
    assert engine.history[-1]["role"] == "assistant"
    
    # Test user text behavior
    resp2 = await engine.get_response("Main theek hoon, aap batao.")
    assert resp2 == "Namaste Rahul! Kaise hain aap?"
    assert len(engine.history) == 4 # added user and assistant
    assert engine.history[-2]["role"] == "user"
    assert engine.history[-2]["content"] == "Main theek hoon, aap batao."

@pytest.mark.asyncio
async def test_fallback_on_error(sample_lead):
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = Exception("API down")
    
    engine = ConversationEngine(lead=sample_lead, client=mock_client)
    resp = await engine.get_response("Hello")
    assert "Maaf kijiyega" in resp
    assert len(engine.history) == 2 # 1 system + 1 user prompt
