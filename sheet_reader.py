"""
Google Sheets reader module.
Reads client data from a Google Sheet and updates email send status.
"""

import time
import logging
import gspread
from google.oauth2.service_account import Credentials
from config import Config

logger = logging.getLogger(__name__)

# Google Sheets API scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_client():
    """Create an authenticated gspread client using service account credentials.
    
    Returns:
        gspread.Client: Authenticated Google Sheets client
        
    Raises:
        ValueError: If credentials are not configured
        gspread.exceptions.APIError: If authentication fails
    """
    creds_dict = Config.get_service_account_credentials()
    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(credentials)


def _get_worksheet():
    """Open the configured Google Sheet and return the first worksheet.
    
    Returns:
        gspread.Worksheet: The first worksheet in the configured spreadsheet
    """
    client = _get_client()
    spreadsheet = client.open_by_url(Config.GOOGLE_SHEET_URL)
    return spreadsheet.sheet1


def get_all_clients():
    """Fetch all rows from the Google Sheet as a list of dictionaries.
    
    Each dictionary maps column headers to cell values.
    
    Returns:
        list[dict]: All rows from the sheet
    """
    worksheet = _get_worksheet()
    records = worksheet.get_all_records()
    logger.info(f"Fetched {len(records)} total rows from Google Sheet")
    return records


def get_pending_clients():
    """Fetch rows where the Status column is 'pending' (case-insensitive).
    
    Returns:
        list[dict]: Rows with pending status, each with an added '_row_number' key
    """
    worksheet = _get_worksheet()
    all_records = worksheet.get_all_records()
    headers = worksheet.row_values(1)
    
    status_col = Config.SHEET_STATUS_COLUMN
    
    pending = []
    for i, record in enumerate(all_records):
        # Row number in sheet (1-indexed, +2 because row 1 is headers, enumerate starts at 0)
        row_number = i + 2
        status = str(record.get(status_col, "")).strip().lower()
        
        if status == "pending":
            record["_row_number"] = row_number
            record["_headers"] = headers
            pending.append(record)
    
    logger.info(f"Found {len(pending)} pending emails out of {len(all_records)} total rows")
    return pending


def update_status(row_number, status, max_retries=3):
    """Update the Status column for a specific row in the Google Sheet.
    
    Implements exponential backoff for API rate limit handling.
    
    Args:
        row_number: The 1-indexed row number in the sheet
        status: New status value ('sent' or 'failed')
        max_retries: Maximum number of retry attempts
        
    Raises:
        gspread.exceptions.APIError: If all retries are exhausted
    """
    worksheet = _get_worksheet()
    headers = worksheet.row_values(1)
    
    from datetime import datetime
    
    status_col_name = Config.SHEET_STATUS_COLUMN
    timestamp_col_name = Config.SHEET_TIMESTAMP_COLUMN
    
    try:
        col_index = headers.index(status_col_name) + 1  # 1-indexed
    except ValueError:
        logger.error(
            f"Status column '{status_col_name}' not found in sheet headers: {headers}"
        )
        raise ValueError(f"Column '{status_col_name}' not found in sheet")
        
    ts_col_index = None
    if timestamp_col_name in headers:
        ts_col_index = headers.index(timestamp_col_name) + 1
    
    for attempt in range(max_retries):
        try:
            worksheet.update_cell(row_number, col_index, status)
            if ts_col_index:
                # Use local time for timestamp or UTC if preferred
                ts_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                worksheet.update_cell(row_number, ts_col_index, ts_value)
            logger.info(f"Updated row {row_number} status to '{status}' and set timestamp")
            return
        except gspread.exceptions.APIError as e:
            if "RATE_LIMIT" in str(e) or "429" in str(e):
                wait_time = (2 ** attempt) + 1
                logger.warning(
                    f"Rate limited on row {row_number}, retrying in {wait_time}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)
            else:
                raise
    
    logger.error(f"Failed to update row {row_number} after {max_retries} retries")
    raise gspread.exceptions.APIError(f"Rate limit exceeded after {max_retries} retries")


def test_connection():
    """Test the Google Sheets connection and return sheet info.
    
    Returns:
        dict: Sheet information including title, row count, and headers
        
    Raises:
        Exception: If connection fails
    """
    try:
        worksheet = _get_worksheet()
        headers = worksheet.row_values(1)
        row_count = worksheet.row_count
        title = worksheet.spreadsheet.title
        
        return {
            "success": True,
            "title": title,
            "worksheet": worksheet.title,
            "headers": headers,
            "row_count": row_count,
        }
    except Exception as e:
        logger.error(f"Google Sheets connection test failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }
