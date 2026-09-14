"""
Configuration module for EMailAutomation.
Loads settings from environment variables with validation.
"""

import os
import json
from dotenv import load_dotenv

# Load .env file if present (local development)
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # --- Gmail SMTP ---
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
    EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "")

    # --- Google Sheets ---
    GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL", "")
    GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    # Column name in your sheet that tracks email status (pending/sent/failed)
    SHEET_STATUS_COLUMN = os.getenv("SHEET_STATUS_COLUMN", "Status")
    SHEET_TIMESTAMP_COLUMN = os.getenv("SHEET_TIMESTAMP_COLUMN", "Timestamp")

    # --- Webhook Security ---
    TRIGGER_API_KEY = os.getenv("TRIGGER_API_KEY", "")

    # --- Database ---
    DATABASE_PATH = os.getenv("DATABASE_PATH", "email_logs.db")

    # --- Email Defaults ---
    DEFAULT_EMAIL_SUBJECT = os.getenv("DEFAULT_EMAIL_SUBJECT", "Hello from {{name}}")
    DEFAULT_TEMPLATE = os.getenv("DEFAULT_TEMPLATE", "default.html")

    # --- Attachments ---
    ATTACHMENTS_DRIVE_FOLDER_ID = os.getenv("ATTACHMENTS_DRIVE_FOLDER_ID", "")

    @classmethod
    def validate(cls):
        """Validate that all required configuration values are set.
        
        Returns:
            tuple: (is_valid: bool, errors: list[str])
        """
        errors = []

        if not cls.GMAIL_ADDRESS:
            errors.append("GMAIL_ADDRESS is required")
        if not cls.GMAIL_APP_PASSWORD:
            errors.append("GMAIL_APP_PASSWORD is required")
        if not cls.GOOGLE_SHEET_URL:
            errors.append("GOOGLE_SHEET_URL is required")
        if not cls.GOOGLE_SERVICE_ACCOUNT_JSON and not cls.GOOGLE_SERVICE_ACCOUNT_FILE:
            errors.append(
                "Either GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE is required"
            )
        if not cls.TRIGGER_API_KEY:
            errors.append("TRIGGER_API_KEY is required for webhook security")

        return (len(errors) == 0, errors)

    @classmethod
    def get_service_account_credentials(cls):
        """Get Google Service Account credentials as a dictionary.
        
        Priority: GOOGLE_SERVICE_ACCOUNT_JSON env var > GOOGLE_SERVICE_ACCOUNT_FILE path.
        
        Returns:
            dict: Service account credentials
            
        Raises:
            ValueError: If no credentials are configured
        """
        # First try inline JSON (useful for Render environment variables)
        if cls.GOOGLE_SERVICE_ACCOUNT_JSON:
            try:
                return json.loads(cls.GOOGLE_SERVICE_ACCOUNT_JSON)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"GOOGLE_SERVICE_ACCOUNT_JSON contains invalid JSON: {e}"
                )

        # Fall back to file path (useful for local development)
        if cls.GOOGLE_SERVICE_ACCOUNT_FILE:
            file_path = cls.GOOGLE_SERVICE_ACCOUNT_FILE
            if not os.path.exists(file_path):
                raise ValueError(
                    f"Service account file not found: {file_path}"
                )
            with open(file_path, "r") as f:
                return json.load(f)

        raise ValueError(
            "No Google Service Account credentials configured. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE."
        )

    @classmethod
    def get_masked_value(cls, value, visible_chars=4):
        """Mask a sensitive value for display, showing only the last N chars."""
        if not value:
            return "(not set)"
        if len(value) <= visible_chars:
            return "*" * len(value)
        return "*" * (len(value) - visible_chars) + value[-visible_chars:]
