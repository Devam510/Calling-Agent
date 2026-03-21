"""
sheet_updater.py — Write call results back to Google Sheets.

Writes: called=TRUE, call_status, summary, followup_date, recording_path.
Retries on transient API errors with exponential backoff.
"""

from __future__ import annotations

import logging
from typing import Optional

import gspread
from gspread.exceptions import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config import settings
from backend.models import CallResult, Lead

logger = logging.getLogger(__name__)


def _get_sheet() -> gspread.Worksheet:
    client = gspread.oauth()
    spreadsheet = client.open_by_url(settings.google_sheet_url)
    return spreadsheet.worksheet(settings.google_sheet_worksheet)


def _col_letter(header: str, headers: list[str]) -> int:
    """Return 1-based column index for a given header name."""
    return headers.index(header) + 1


@retry(
    retry=retry_if_exception_type(APIError),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,
)
def update_lead_result(lead: Lead, result: CallResult) -> None:
    """
    Update the lead's row in the sheet with call results.

    Args:
        lead:   The lead whose row needs updating.
        result: The outcome produced by transcript_analyzer.

    Writes columns: called, call_status, summary, followup_date, recording_path
    """
    sheet = _get_sheet()
    headers: list[str] = sheet.row_values(1)  # read header row for column positions

    updates: list[dict] = []

    def _cell(header: str, value: str) -> dict:
        """Build a batch update cell dict."""
        col = _col_letter(header, headers)
        return {
            "range": gspread.utils.rowcol_to_a1(lead.row_index, col),
            "values": [[value]],
        }

    updates.append(_cell("called", "TRUE"))
    updates.append(_cell("call_status", result.status.value))
    updates.append(_cell("summary", result.summary))
    updates.append(_cell("followup_date", result.followup_date or ""))

    # Write recording_path if the column exists
    if "recording_path" in headers:
        updates.append(_cell("recording_path", result.recording_path))

    sheet.batch_update(updates, value_input_option="RAW")

    logger.info(
        "Updated row %d — status=%s recording=%s",
        lead.row_index,
        result.status.value,
        result.recording_path,
    )


@retry(
    retry=retry_if_exception_type(APIError),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,
)
def mark_lead_called(lead: Lead) -> None:
    """
    Set called=TRUE immediately when dialing, before the call connects.
    Prevents duplicate calls if the orchestrator crashes mid-call.
    """
    sheet = _get_sheet()
    headers: list[str] = sheet.row_values(1)
    col = _col_letter("called", headers)
    sheet.update_cell(lead.row_index, col, "TRUE")
    logger.info("Marked lead %s as called (pre-dial guard)", lead.id)
