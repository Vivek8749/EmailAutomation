import os
import json
import logging
import io
import shutil
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from config import Config

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
ATTACHMENTS_DIR = os.path.join(os.path.dirname(__file__), "attachments")
SYNC_STATE_FILE = os.path.join(os.path.dirname(__file__), "drive_sync_state.json")

def sync_attachments():
    """
    Checks the Drive folder for changes. If attachments changed (added/removed/modified),
    clears the local attachments folder and redownloads them.
    """
    folder_id = Config.ATTACHMENTS_DRIVE_FOLDER_ID
    if not folder_id:
        logger.info("ATTACHMENTS_DRIVE_FOLDER_ID not set. Skipping Drive sync.")
        return

    logger.info(f"Checking for updates in Drive folder: {folder_id}")

    try:
        creds_dict = Config.get_service_account_credentials()
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)

        # Get all files in the folder
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType, md5Checksum, modifiedTime, shortcutDetails)",
            pageSize=100
        ).execute()
        
        items = results.get('files', [])
        
        # Build current state from Drive
        current_state = {}
        for item in items:
            # Resolve shortcuts if any
            if item.get('mimeType') == 'application/vnd.google-apps.shortcut':
                target_id = item.get('shortcutDetails', {}).get('targetId')
                if target_id:
                    # We use the shortcut's ID or target ID for state tracking
                    current_state[item['id']] = {
                        "name": item['name'],
                        "target_id": target_id,
                        "type": "shortcut",
                        "modified": item.get('modifiedTime', '')
                    }
            else:
                current_state[item['id']] = {
                    "name": item['name'],
                    "md5": item.get('md5Checksum', ''),
                    "modified": item.get('modifiedTime', '')
                }

        # Load previous state
        previous_state = {}
        if os.path.exists(SYNC_STATE_FILE):
            try:
                with open(SYNC_STATE_FILE, "r") as f:
                    previous_state = json.load(f)
            except Exception as e:
                logger.warning(f"Could not read sync state file: {e}")

        # Compare states
        if current_state == previous_state and os.path.exists(ATTACHMENTS_DIR):
            logger.info("Attachments are up-to-date. No download needed.")
            return

        logger.info("Drive attachments changed. Redownloading all files...")
        
        # Clear existing attachments
        if os.path.exists(ATTACHMENTS_DIR):
            shutil.rmtree(ATTACHMENTS_DIR)
        os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
        
        # Download files
        for item in items:
            file_name = item['name']
            file_id = item['id']
            
            if item.get('mimeType') == 'application/vnd.google-apps.shortcut':
                file_id = item.get('shortcutDetails', {}).get('targetId', file_id)
            
            logger.info(f"Downloading {file_name}...")
            request = service.files().get_media(fileId=file_id)
            file_path = os.path.join(ATTACHMENTS_DIR, file_name)
            
            with io.FileIO(file_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
        
        # Save new state
        with open(SYNC_STATE_FILE, "w") as f:
            json.dump(current_state, f, indent=4)
            
        logger.info("Successfully synced attachments from Drive.")

    except Exception as e:
        logger.error(f"Failed to sync attachments from Drive: {e}")
