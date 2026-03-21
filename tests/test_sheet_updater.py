"""
test_sheet_updater.py — Unit tests for sheet_updater.py
"""

import pytest
from unittest.mock import MagicMock, call, patch

from backend.models import CallResult, CallStatus, Lead


def _make_lead(row_index: int = 5, id: str = "3") -> Lead:
    return Lead(
        row_index=row_index,
        id=id,
        company_name="Test Co",
        owner_name="Priya",
        phone="9000011111",
        business_type="restaurant",
        city="Mumbai",
    )


def _make_result(
    status: CallStatus = CallStatus.INTERESTED,
    summary: str = "Owner was interested.",
    followup_date: str = "2026-04-01",
    recording_path: str = "recordings/test_stereo.mp3",
) -> CallResult:
    return CallResult(
        status=status,
        summary=summary,
        followup_date=followup_date,
        recording_path=recording_path,
    )


@patch("backend.sheet_updater.gspread.oauth")
def test_updates_all_columns(mock_oauth):
    """update_lead_result should batch-update all expected columns."""
    mock_sheet = MagicMock()
    mock_sheet.row_values.return_value = [
        "id", "company_name", "owner_name", "phone",
        "business_type", "city", "called", "call_status",
        "summary", "followup_date", "recording_path",
    ]
    mock_oauth.return_value.open_by_url.return_value.worksheet.return_value = mock_sheet

    from backend.sheet_updater import update_lead_result
    lead = _make_lead()
    result = _make_result()
    update_lead_result(lead, result)

    mock_sheet.batch_update.assert_called_once()
    updates = mock_sheet.batch_update.call_args[0][0]

    # Verify called=TRUE is in the batch
    called_update = next(u for u in updates if u["values"] == [["TRUE"]])
    assert called_update is not None

    # Verify recording_path is in the batch
    rec_update = next(u for u in updates if u["values"] == [["recordings/test_stereo.mp3"]])
    assert rec_update is not None


@patch("backend.sheet_updater.gspread.oauth")
def test_skips_recording_path_if_column_missing(mock_oauth):
    """Should not crash if recording_path column doesn't exist in sheet."""
    mock_sheet = MagicMock()
    mock_sheet.row_values.return_value = [
        "id", "company_name", "owner_name", "phone",
        "business_type", "city", "called", "call_status",
        "summary", "followup_date",
        # no recording_path column
    ]
    mock_oauth.return_value.open_by_url.return_value.worksheet.return_value = mock_sheet

    from backend.sheet_updater import update_lead_result
    update_lead_result(_make_lead(), _make_result())  # should not raise

    mock_sheet.batch_update.assert_called_once()
    updates = mock_sheet.batch_update.call_args[0][0]
    rec_updates = [u for u in updates if "recordings" in str(u["values"])]
    assert len(rec_updates) == 0


@patch("backend.sheet_updater.gspread.oauth")
def test_mark_lead_called(mock_oauth):
    """mark_lead_called should set called=TRUE via update_cell."""
    mock_sheet = MagicMock()
    mock_sheet.row_values.return_value = [
        "id", "company_name", "owner_name", "phone",
        "business_type", "city", "called", "call_status",
        "summary", "followup_date",
    ]
    mock_oauth.return_value.open_by_url.return_value.worksheet.return_value = mock_sheet

    from backend.sheet_updater import mark_lead_called
    lead = _make_lead(row_index=5)
    mark_lead_called(lead)

    mock_sheet.update_cell.assert_called_once_with(5, 7, "TRUE")  # col 7 = called
