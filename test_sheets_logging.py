"""
Standalone diagnostic for the Google Sheets auto-post logging.
Uses the LOCAL service account JSON (not the GitHub secret) to write one test row.

Run from Terminal:
    cd "/Users/mattwisse/Documents/Claude/Projects/Youtube Channels Project"
    python3 test_sheets_logging.py

The error message it prints (or success) will tell us exactly what's broken.
This script does NOT touch any real workflow — it's pure diagnostic.
"""
import json
import os
import sys
from datetime import datetime

CREDS_FILE = "video-studio-493020-05e03c3a1b8c.json"
SPREADSHEET_ID = "1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI"
TARGET_TAB = "Auto-Post Log"

print("=" * 60)
print("Google Sheets Logging Diagnostic")
print("=" * 60)

# ── Check 1: credentials file exists locally ──────────────────────────────
if not os.path.exists(CREDS_FILE):
    print(f"\n❌ FAIL: can't find {CREDS_FILE} in current folder")
    print("   Make sure you ran `cd` into the project folder first.")
    sys.exit(1)
print(f"✓ Step 1: found {CREDS_FILE}")

# ── Check 2: credentials file is valid JSON ────────────────────────────────
try:
    with open(CREDS_FILE) as f:
        creds_dict = json.load(f)
    client_email = creds_dict.get("client_email", "<missing>")
    print(f"✓ Step 2: credentials JSON valid")
    print(f"         service account = {client_email}")
except Exception as e:
    print(f"\n❌ FAIL at step 2: credentials file is not valid JSON — {e}")
    sys.exit(1)

# ── Check 3: Google libraries installed ────────────────────────────────────
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    print(f"✓ Step 3: google libraries installed")
except ImportError as e:
    print(f"\n❌ FAIL at step 3: {e}")
    print("   Fix: pip3 install google-api-python-client google-auth --break-system-packages")
    sys.exit(1)

# ── Check 4: authenticate and build service ───────────────────────────────
try:
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=creds)
    print(f"✓ Step 4: authenticated to Google")
except Exception as e:
    print(f"\n❌ FAIL at step 4 (auth): {type(e).__name__}: {e}")
    sys.exit(1)

# ── Check 5: can we open the spreadsheet at all? ───────────────────────────
try:
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
    print(f"✓ Step 5: opened spreadsheet — tabs: {tabs}")
except HttpError as e:
    status = e.resp.status if hasattr(e, "resp") else "?"
    print(f"\n❌ FAIL at step 5: HTTP {status}")
    print(f"   Raw error: {e}")
    if status == 403:
        print(f"\n   👉 FIX: share the sheet with {client_email} as Editor")
    elif status == 404:
        print(f"\n   👉 FIX: sheet ID is wrong, or Sheets API not enabled in GCP project")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ FAIL at step 5: {type(e).__name__}: {e}")
    sys.exit(1)

# ── Check 6: does the target tab exist? ────────────────────────────────────
if TARGET_TAB not in tabs:
    print(f"\n❌ FAIL at step 6: tab '{TARGET_TAB}' does NOT exist")
    print(f"   Tabs that DO exist: {tabs}")
    print(f"\n   👉 FIX: either rename a tab to '{TARGET_TAB}' in the sheet,")
    print(f"       OR update the code to match one of these tab names.")
    sys.exit(1)
print(f"✓ Step 6: target tab '{TARGET_TAB}' exists")

# ── Check 7: attempt to write a test row ──────────────────────────────────
try:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_row = [timestamp, "DIAGNOSTIC", "TEST — safe to delete this row", "Success", "n/a", "from test_sheets_logging.py"]
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{TARGET_TAB}!A:F",
        valueInputOption="USER_ENTERED",
        body={"values": [test_row]},
    ).execute()
    updated = result.get("updates", {}).get("updatedRange", "?")
    print(f"✓ Step 7: test row written to {updated}")
    print("\n" + "=" * 60)
    print("🎉 SUCCESS — logging works with local credentials.")
    print("=" * 60)
    print(f"\nCheck the sheet — you should see a new row starting with 'DIAGNOSTIC'.")
    print(f"You can delete that row after.")
    print(f"\nSince it works locally, the issue is that the GitHub secret")
    print(f"GOOGLE_SHEETS_KEY is empty, malformed, or out of date.")
    print(f"Fix: re-paste the contents of {CREDS_FILE} into that secret.")
except HttpError as e:
    status = e.resp.status if hasattr(e, "resp") else "?"
    print(f"\n❌ FAIL at step 7 (write): HTTP {status}")
    print(f"   Raw error: {e}")
    if status == 403:
        print(f"\n   👉 FIX: service account can READ but not WRITE.")
        print(f"       Share sheet with {client_email} as EDITOR, not Viewer.")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ FAIL at step 7: {type(e).__name__}: {e}")
    sys.exit(1)
