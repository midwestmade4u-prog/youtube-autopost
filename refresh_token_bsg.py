#!/usr/bin/env python3
"""
Re-authenticates the BSG YouTube account and saves a fresh token.
IMPORTANT: Sign in with midwestmade4u@gmail.com, then select 'Bible Story Garden'.
Do NOT sign in as bsgchannel99@gmail.com — it is a manager only, not the owner.

Usage:
    python3 refresh_token_bsg.py

After it finishes, run:
    pbcopy < youtube_token_bsg.json
Then paste into GitHub Secret: YT_TOKEN_BSG
"""

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]

CLIENT_SECRETS = Path(__file__).parent / "youtube_client_secrets.json"
TOKEN_FILE     = Path(__file__).parent / "youtube_token_bsg.json"

def main():
    if not CLIENT_SECRETS.exists():
        print(f"❌  {CLIENT_SECRETS} not found — make sure it's in the project folder.")
        return

    # Delete any existing token so there's no cached state
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        print("🗑️  Deleted old token file\n")

    print("Opening browser for BSG OAuth…")
    print("→ IMPORTANT: Sign in with midwestmade4u@gmail.com, then select 'Bible Story Garden'\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
    # open_browser=False forces it to print the URL so we can control which account signs in
    creds = flow.run_local_server(
        port=0,
        open_browser=False,
        prompt="consent",
        login_hint="midwestmade4u@gmail.com",
    )

    token_data = {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes),
        "expiry":        creds.expiry.strftime("%Y-%m-%dT%H:%M:%SZ") if creds.expiry else None,
    }

    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    print(f"✅  Token saved to {TOKEN_FILE.name}")
    print("\nNext step:")
    print("  1. Copy the contents of youtube_token_bsg.json")
    print("  2. Go to GitHub → repo → Settings → Secrets → YT_TOKEN_BSG → Update")
    print("  3. Paste and save\n")
    print("Token preview (first 80 chars of file):")
    print(TOKEN_FILE.read_text()[:80], "…")

if __name__ == "__main__":
    main()
