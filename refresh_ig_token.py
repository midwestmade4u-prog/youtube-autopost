"""
Agent 4 — ChannelStack IG Token Monitor
Validates the IG access token is still working via a /me API call.
Emails a warning if the token is invalid.

NOTE: debug_token requires an app access token (APP_ID|APP_SECRET) as the
access_token param — using the IG user token itself doesn't work for
Instagram long-lived tokens and returns "Cannot parse access token".
Using /me instead avoids this and correctly validates posting capability.

Token expiry: IG long-lived tokens last 60 days. Refresh ~14 days before
expiry by going to:
1. developers.facebook.com → My Apps → ChannelStack API
2. Use Cases → Instagram → API setup with Instagram login → Generate token
3. Update GH secret IG_ACCESS_TOKEN with the new token
"""

import os
import sys
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ── Env vars ──────────────────────────────────────────────────────────────────
IG_ACCESS_TOKEN    = os.environ["IG_ACCESS_TOKEN"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

NOTIFY_EMAIL = "matt@channelstack.net"
SENDER_EMAIL = "wisseinc@gmail.com"

# ── Check token validity ──────────────────────────────────────────────────────
def check_token():
    """Validate the token works by calling /me. Raises on failure."""
    print("Checking token via /me...")
    resp = requests.get(
        "https://graph.facebook.com/v18.0/me",
        params={"access_token": IG_ACCESS_TOKEN, "fields": "id,name"}
    )
    data = resp.json()

    if "error" in data:
        raise Exception(f"Token invalid: {data['error']['message']}")

    user_id   = data.get("id", "unknown")
    user_name = data.get("name", "unknown")
    print(f"  ✓ Token valid — user: {user_name} (id: {user_id})")
    print(f"  Note: token expires ~60 days from issue date. Refresh manually if posts start failing.")

# ── Send email notification ───────────────────────────────────────────────────
def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = NOTIFY_EMAIL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"✓ Email sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"Email failed (non-fatal): {e}")

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=== Agent 4: IG Token Monitor ===\n")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    try:
        check_token()
        print("\n✓ Token check passed. No action needed.")

    except Exception as e:
        error_msg = str(e)
        print(f"\nERROR: {error_msg}")
        send_email(
            subject="⚠️ ChannelStack IG token check FAILED",
            body=(
                f"Token monitor failed at {now_str}.\n\n"
                f"Error: {error_msg}\n\n"
                f"HOW TO REFRESH (manual — takes ~2 minutes):\n"
                f"1. Go to developers.facebook.com → My Apps → ChannelStack API\n"
                f"2. Use Cases → Instagram → API setup with Instagram login → Generate token\n"
                f"3. Copy the new token\n"
                f"4. Go to github.com/midwestmade4u-prog/channelstack-ig → Settings → Secrets → Actions\n"
                f"5. Update IG_ACCESS_TOKEN with the new token\n\n"
                f"Do NOT use the API to auto-refresh — it strips publishing permissions."
            )
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
