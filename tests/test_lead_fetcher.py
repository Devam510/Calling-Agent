"""
test_lead_fetcher.py — Unit tests for lead_fetcher.py

Uses pytest-mock to avoid real Google Sheets API calls.
"""

import pytest
from unittest.mock import MagicMock, patch

from backend.models import Lead


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_record(
    id: str = "1",
    company_name: str = "Test Shop",
    owner_name: str = "Ramesh",
    phone: str = "9999900000",
    business_type: str = "retail",
    city: str = "Delhi",
    called: str = "FALSE",
    call_status: str = "",
    summary: str = "",
    followup_date: str = "",
) -> dict:
    return {
        "id": id,
        "company_name": company_name,
        "owner_name": owner_name,
        "phone": phone,
        "business_type": business_type,
        "city": city,
        "called": called,
        "call_status": call_status,
        "summary": summary,
        "followup_date": followup_date,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

@patch("backend.lead_fetcher.gspread.oauth")
def test_returns_first_uncalled_lead(mock_oauth):
    """fetch_next_lead should return the first row where called is FALSE."""
    records = [
        _make_record(id="1", called="TRUE"),   # already called
        _make_record(id="2", called="FALSE"),  # should be returned
        _make_record(id="3", called="FALSE"),
    ]
    mock_sheet = MagicMock()
    mock_sheet.get_all_records.return_value = records
    mock_oauth.return_value.open_by_url.return_value.worksheet.return_value = mock_sheet

    from backend.lead_fetcher import fetch_next_lead
    lead = fetch_next_lead()

    assert lead is not None
    assert lead.id == "2"
    assert lead.row_index == 3  # row 1 = header, row 2 = record[0], row 3 = record[1]


@patch("backend.lead_fetcher.gspread.oauth")
def test_returns_none_when_all_called(mock_oauth):
    """fetch_next_lead should return None when every lead has been called."""
    records = [
        _make_record(id="1", called="TRUE"),
        _make_record(id="2", called="TRUE"),
    ]
    mock_sheet = MagicMock()
    mock_sheet.get_all_records.return_value = records
    mock_oauth.return_value.open_by_url.return_value.worksheet.return_value = mock_sheet

    from backend.lead_fetcher import fetch_next_lead
    lead = fetch_next_lead()

    assert lead is None


@patch("backend.lead_fetcher.gspread.oauth")
def test_treats_empty_called_as_uncalled(mock_oauth):
    """An empty 'called' cell should be treated as not called."""
    records = [_make_record(id="1", called="")]
    mock_sheet = MagicMock()
    mock_sheet.get_all_records.return_value = records
    mock_oauth.return_value.open_by_url.return_value.worksheet.return_value = mock_sheet

    from backend.lead_fetcher import fetch_next_lead
    lead = fetch_next_lead()

    assert lead is not None


@patch("backend.lead_fetcher.gspread.oauth")
def test_returns_none_on_empty_sheet(mock_oauth):
    """fetch_next_lead should return None on an empty sheet."""
    mock_sheet = MagicMock()
    mock_sheet.get_all_records.return_value = []
    mock_oauth.return_value.open_by_url.return_value.worksheet.return_value = mock_sheet

    from backend.lead_fetcher import fetch_next_lead
    lead = fetch_next_lead()

    assert lead is None
