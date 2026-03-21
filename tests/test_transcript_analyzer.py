"""
test_transcript_analyzer.py — Unit tests for transcript_analyzer.py

Tests the two-attempt retry strategy (L004) using mocked Groq responses.
"""

import pytest
from unittest.mock import MagicMock, patch

from backend.models import CallResult, CallStatus


def _mock_groq_response(content: str):
    """Build a fake Groq API response."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


@patch("backend.transcript_analyzer.Groq")
def test_normal_json_response(mock_groq_cls):
    """Valid JSON on first attempt → should return CallResult correctly."""
    mock_client = MagicMock()
    mock_groq_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_groq_response(
        '{"status":"interested","summary":"Owner was interested.","followup_date":null}'
    )

    from backend.transcript_analyzer import analyze_transcript
    result = analyze_transcript("Customer: हाँ, website चाहिए।")

    assert result.status == CallStatus.INTERESTED
    assert "interested" in result.summary.lower()


@patch("backend.transcript_analyzer.Groq")
def test_retries_on_malformed_json(mock_groq_cls):
    """Malformed JSON on attempt 1 → second attempt → success. (L004)"""
    mock_client = MagicMock()
    mock_groq_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = [
        _mock_groq_response("Sure! Here's the analysis: interesting call!"),  # malformed
        _mock_groq_response(
            '{"status":"not_interested","summary":"Not interested.","followup_date":null}'
        ),
    ]

    from backend.transcript_analyzer import analyze_transcript
    result = analyze_transcript("Customer: मुझे नहीं चाहिए।")

    assert result.status == CallStatus.NOT_INTERESTED
    assert mock_client.chat.completions.create.call_count == 2


@patch("backend.transcript_analyzer.Groq")
def test_both_attempts_fail_returns_default(mock_groq_cls):
    """Both attempts fail → return FAILED default safely. (L004)"""
    mock_client = MagicMock()
    mock_groq_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API down")

    from backend.transcript_analyzer import analyze_transcript
    result = analyze_transcript("Some transcript")

    assert result.status == CallStatus.FAILED


@patch("backend.transcript_analyzer.Groq")
def test_empty_transcript_returns_failed(mock_groq_cls):
    """Empty transcript → return FAILED without calling Groq."""
    from backend.transcript_analyzer import analyze_transcript
    result = analyze_transcript("")

    assert result.status == CallStatus.FAILED
    mock_groq_cls.assert_not_called()
