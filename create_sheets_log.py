#!/usr/bin/env python3
"""Create Auto-Post Log sheet in Google Sheets (one-time setup)"""

import json
import os
import sys

def create_log_sheet():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("❌ Install required: pip install google-auth google-api-python-client")
        return False

    # Load service account key from environment or file
    creds_json = os.getenv("GOOGLE_SHEETS_KEY")

    if creds_json:
        # Use environment variable (from GitHub secrets)
        creds_dict = json.loads(creds_json)
    else:
        # Try to load from local file
        try:
            with open("video-studio-493020-05e03c3a1b8c.json") as f:
                creds_dict = json.load(f)
        except FileNotFoundError:
            print("❌ Please either:")
            print("   1. Save the JSON key file to this folder, OR")
            print("   2. Set environment: export GOOGLE_SHEETS_KEY='<paste JSON here>'")
            return False

    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )

    service = build("sheets", "v4", credentials=creds)
    spreadsheet_id = "1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI"

    try:
        # Create new sheet
        request = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [{
                    "addSheet": {
                        "properties": {"title": "Auto-Post Log"}
                    }
                }]
            }
        )
        request.execute()
        print("✅ Auto-Post Log sheet created")

        # Add headers
        headers = ["Timestamp", "Channel", "Video Title", "Status", "Video URL", "Notes"]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Auto-Post Log!A1:F1",
            valueInputOption="USER_ENTERED",
            body={"values": [headers]}
        ).execute()

        # Format header row
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [{
                    "repeatCell": {
                        "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 6},
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 0.12, "green": 0.31, "blue": 0.47},
                                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
                            }
                        },
                        "fields": "userEnteredFormat"
                    }
                }]
            }
        ).execute()

        print("✅ Headers formatted")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = create_log_sheet()
    sys.exit(0 if success else 1)
