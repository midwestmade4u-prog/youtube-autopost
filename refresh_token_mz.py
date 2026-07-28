#!/usr/bin/env python3
"""
Re-authenticates the Minute Zero YouTube account and saves a fresh token.
IMPORTANT: Sign in with the account that OWNS the Minute Zero channel.
           Channel ID: UCMVhjR4HetJctXeYkuPgg6w  (@theminutezero)

Usage:
    python3 refresh_token_mz.py

After it finishes, run:
    pbcopy < youtube_token_mz.json
Then paste into GitHub Secret: YT_TOKEN_MZ
"""

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",  # added Jul 5 2026
    "https://www.googleapis.com/auth/youtube.force-ssl",       # added Jul 28 2026 -- required for commentThreads().insert() (funnel/affiliate comments)
]

CLIENT_SECRETS = Path(__file__).parent / "youtube_client_secrets.json"
TOKEN_FILE     = Path(__file__).parent / "youtube_token_mz.json"

MZ_CHANNEL_ID = "UCMVhjR4HetJctXeYkuPgg6w"

def main():
    if not CLIENT_SECRETS.exists():
        print(f"❌  {CLIENT_SECRETS} not found — make sure youtube_client_secrets.json is in the project folder.")
        return

    # Delete any existing token so there's no cached state
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        print("🗑️  Deleted old token file\n")

    print("Opening browser for Minute Zero OAuth…")
    print("→ IMPORTANT: Sign in with the account that owns the Minute Zero channel")
    print(f"→ Expected channel ID after login: {MZ_CHANNEL_ID}\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
    creds = flow.run_local_server(
        port=0,
        open_browser=False,
        prompt="consent",
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

    # Verify it's the right channel
    try:
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        creds_obj = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        yt = build("youtube", "v3", credentials=creds_obj)
        me = yt.channels().list(mine=True, part="id,snippet").execute()
        if me.get("items"):
            ch = me["items"][0]
            got_id = ch["id"]
            got_name = ch["snippet"]["title"]
            if got_id == MZ_CHANNEL_ID:
                print(f"✅  Verified: token is for '{got_name}' ({got_id}) — correct!")
            else:
                print(f"⚠️  WARNING: token is for '{got_name}' ({got_id})")
                print(f"   Expected: {MZ_CHANNEL_ID}")
                print("   If this is wrong, re-run with the correct account.")
        else:
            print("⚠️  Could not verify channel — no channels returned")
    except Exception as e:
        print(f"⚠️  Verification failed (non-fatal): {e}")

    print("\nNext steps:")
    print("  1. pbcopy < youtube_token_mz.json")
    print("  2. GitHub → youtube-autopost repo → Settings → Secrets → YT_TOKEN_MZ → Update")
    print("  3. Paste and save")
    print("  4. Go to GH Actions → YouTube Auto-Post - Minute Zero → Run workflow")
    print("     to confirm it posts immediately\n")
    print("Token preview (first 80 chars):")
    print(TOKEN_FILE.read_text()[:80], "…")

if __name__ == "__main__":
    main()
