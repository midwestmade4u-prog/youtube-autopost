#!/usr/bin/env python3
"""
Quick BSG token diagnostic — run this to see exactly why _load_yt_credentials fails.
Usage: python3 check_bsg_token.py
"""
import json
from pathlib import Path

BASE_DIR   = Path(__file__).parent
TOKEN_FILE = BASE_DIR / "youtube_token_bsg.json"
YT_SCOPES  = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

print("=" * 60)
print("BSG TOKEN DIAGNOSTIC")
print("=" * 60)

# Step 1: Does the file exist?
print(f"\n1. Token file: {TOKEN_FILE}")
if not TOKEN_FILE.exists():
    print("   ❌ FILE NOT FOUND — this is the problem!")
    print("   Fix: run python3 refresh_token_bsg.py and re-paste to GH secret")
    exit(1)
print("   ✅ File exists")

# Step 2: Is it valid JSON with the right keys?
try:
    raw = json.loads(TOKEN_FILE.read_text())
    print(f"\n2. JSON keys: {list(raw.keys())}")
    for key in ["token", "refresh_token", "client_id", "client_secret", "scopes"]:
        val = raw.get(key)
        if key == "refresh_token":
            print(f"   {key}: {'✅ present' if val else '❌ MISSING'}")
        elif key == "scopes":
            print(f"   {key}: {val}")
        elif key == "token":
            print(f"   {key}: {str(val)[:30]}..." if val else f"   {key}: ❌ MISSING")
        else:
            print(f"   {key}: {'✅' if val else '❌ MISSING'}")
except Exception as e:
    print(f"   ❌ JSON parse error: {e}")
    exit(1)

# Step 3: Try loading credentials
print("\n3. Loading credentials...")
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), YT_SCOPES)
    print(f"   valid:   {creds.valid}")
    print(f"   expired: {creds.expired}")
    print(f"   has refresh_token: {bool(creds.refresh_token)}")
    print(f"   scopes:  {creds.scopes}")

    if creds.expired and creds.refresh_token:
        print("\n4. Token expired — attempting refresh...")
        try:
            creds.refresh(Request())
            print(f"   ✅ Refresh succeeded! valid={creds.valid}")
            # Save refreshed token
            TOKEN_FILE.write_text(creds.to_json())
            print("   ✅ Saved refreshed token to file")
        except Exception as e:
            print(f"   ❌ Refresh FAILED: {e}")
            print("\n   → This is the root cause of the 401.")
            print("   → Fix: run python3 refresh_token_bsg.py to re-authorize")
    elif not creds.valid:
        print("\n   ❌ Credentials invalid and cannot be refreshed")
        print("   → Fix: run python3 refresh_token_bsg.py to re-authorize")
    else:
        print("\n4. ✅ Credentials are valid — no refresh needed")
        print("   → Token is fine. The problem must be elsewhere.")

except Exception as e:
    print(f"   ❌ Exception loading credentials: {e}")
    print("\n   → This is the root cause of the 401.")
