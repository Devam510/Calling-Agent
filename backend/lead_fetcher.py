"""
lead_fetcher.py — Read the next uncalled lead from Google Sheets.

Design notes:
  - L005/L006: Uses gspread.oauth() for OAuth2 user auth and open_by_url().
    No service account needed.  First run opens a browser for login,
    subsequent runs use the cached token (~/.config/gspread/authorized_user.json).
  - Returns None if no uncalled lead exists.
"""

from __future__ import annotations

import logging
from typing import Optional

import gspread
from gspread.exceptions import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config import settings
from backend.models import Lead

logger = logging.getLogger(__name__)

# Column names — must match the Google Sheet header row exactly
COLUMN_NAMES = [
    "id",
    "company_name",
    "owner_name",
    "phone",
    "business_type",
    "city",
    "called",
    "call_status",
    "summary",
    "followup_date",
]


def _get_sheet() -> gspread.Worksheet:
    """Authenticate via OAuth2 and return the target worksheet."""
    # L005: gspread.oauth() handles browser login + token caching transparently
    client = gspread.oauth()
    spreadsheet = client.open_by_url(settings.google_sheet_url)  # L006
    return spreadsheet.worksheet(settings.google_sheet_worksheet)


@retry(
    retry=retry_if_exception_type(APIError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def fetch_next_lead() -> Optional[Lead]:
    """
    Fetch the first row where `called` column is blank / FALSE.

    Returns:
        Lead dataclass, or None if all leads have been called.

    Raises:
        gspread.exceptions.APIError: if the API call fails after retries.
    """
    sheet = _get_sheet()
    records = sheet.get_all_records(expected_headers=COLUMN_NAMES)

    for row_number, record in enumerate(records, start=2):  # row 1 = header
        called_value = str(record.get("called", "")).strip().upper()
        if called_value in ("", "FALSE", "NO", "0"):
            logger.info(
                "Found uncalled lead: id=%s company=%s phone=%s",
                record["id"],
                record["company_name"],
                record["phone"],
            )
            return Lead(
                row_index=row_number,
                id=str(record["id"]),
                company_name=str(record["company_name"]),
                owner_name=str(record["owner_name"]),
                phone=str(record["phone"]),
                business_type=str(record["business_type"]),
                city=str(record["city"]),
                called=False,
                call_status=str(record.get("call_status", "")),
                summary=str(record.get("summary", "")),
                followup_date=str(record.get("followup_date", "")),
            )

    logger.info("No uncalled leads found.")
    return None
