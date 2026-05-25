"""
Agent 8 — ChannelStack IG Error Triage
Called by any other agent on failure via a workflow `if: failure()` step.

Flow:
  1. Classify the error into a known category
  2. Look up auto-fix recipe for that category
  3. Attempt fix (wait + re-trigger the failed workflow)
  4. If fixed → log silently to pending_actions.json for the daily digest
  5. If not fixed / no recipe → send immediate escalation email with
     exact click-path to fix manually

Env vars (set by the calling workflow):
  FAILED_AGENT      — name of the workflow that failed (e.g. "ig-carousel.yml")
  ERROR_MESSAGE     — the error string
  GH_PAT            — GitHub PAT for re-triggering workflows
  GMAIL_APP_PASSWORD
  IG_ACCESS_TOKEN   — used to check token validity if relevant
"""

import json
import os
import sys
import time
import hashlib
import hmac as hmac_mod
import requests
import smtplib
import secrets
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ── Env vars ──────────────────────────────────────────────────────────────────
FAILED_AGENT       = os.environ.get("FAILED_AGENT", "unknown-agent")
ERROR_MESSAGE      = os.environ.get("ERROR_MESSAGE", "No error message provided")
GH_PAT             = os.environ.get("GH_PAT", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
IG_ACCESS_TOKEN    = os.environ.get("IG_ACCESS_TOKEN", "")

GH_REPO      = "midwestmade4u-prog/channelstack-ig"
NOTIFY_EMAIL = "matt@channelstack.net"
SENDER_EMAIL = "wisseinc@gmail.com"
PENDING_FILE = "pending_actions.json"


# ── Error classification ──────────────────────────────────────────────────────

ERROR_CLASSES = {
    "token_expired": [
        "token", "expired", "invalid_token", "oauth", "access_token",
        "authentication", "unauthorized", "OAuthException", "190",
    ],
    "rate_limit": [
        "429", "rate limit", "too many requests", "throttle", "slow down",
        # Meta/Instagram specific rate limit phrases
        "application request limit reached", "2207051", "action is blocked",
    ],
    "api_down": [
        "500", "502", "503", "504", "internal server error", "bad gateway",
        "service unavailable",
    ],
    "ghost_post": [
        "ghost post", "not visible", "post not found", "media not found",
    ],
    "content_rejected": [
        "rejected", "violates", "community standards", "policy", "blocked content",
    ],
    "credits_depleted": [
        "credits", "balance", "insufficient", "quota exceeded", "higgsfield",
    ],
    "sheet_auth": [
        "google", "spreadsheet", "gspread", "sheets", "credentials",
    ],
}

FIX_RECIPES = {
    "rate_limit": {
        "description": "Meta 24h publish block (code 4/2207051) — carousel_publisher exits 0 on this, so this recipe is a fallback only. If reached, wait and let the next scheduled run retry.",
        "auto_fixable": False,
        "manual_steps": (
            "No immediate action needed. Meta's 24h publish rate limit will clear automatically.\n"
            "The next scheduled run of ig-carousel.yml will retry. If failures continue beyond 48h, "
            "check developers.facebook.com for app-level restrictions."
        ),
    },
    "api_down": {
        "description": "Wait 10 minutes (API outage), then re-trigger.",
        "auto_fixable": True,
        "wait_seconds": 600,
    },
    "token_expired": {
        "auto_fixable": False,
        "manual_steps": (
            "1. Go to developers.facebook.com → My Apps → ChannelStack API\n"
            "2. Use Cases → Instagram → API setup with Instagram login → Generate token\n"
            "3. Copy the new token\n"
            "4. Go to github.com/midwestmade4u-prog/channelstack-ig → "
            "Settings → Secrets → Actions → Update IG_ACCESS_TOKEN"
        ),
    },
    "content_rejected": {
        "auto_fixable": False,
        "manual_steps": (
            "1. Check carousel_output.json for the rejected content\n"
            "2. Review the slide copy for any policy-violating language\n"
            "3. Edit the content and re-run ig-carousel.yml manually via workflow_dispatch"
        ),
    },
    "credits_depleted": {
        "auto_fixable": False,
        "manual_steps": (
            "1. Go to your Higgsfield account and top up credits\n"
            "2. Re-run the failed workflow manually via GitHub Actions → workflow_dispatch"
        ),
    },
    "ghost_post": {
        "auto_fixable": False,
        "manual_steps": (
            "1. Check your Instagram profile at instagram.com/channelstack\n"
            "2. If post is missing, check Meta Content Publishing Status in developers.facebook.com\n"
            "3. If confirmed ghost, re-run ig-carousel.yml manually with a fresh topic"
        ),
    },
    "sheet_auth": {
        "auto_fixable": False,
        "manual_steps": (
            "1. Check that GOOGLE_SHEETS_KEY secret in GitHub is valid single-line JSON\n"
            "2. Verify the service account has Editor access to the ChannelStack_IG_Analytics sheet\n"
            "3. Re-run the failed workflow manually"
        ),
    },
    "unknown": {
        "auto_fixable": False,
        "manual_steps": (
            "Review the GitHub Actions log for the failed workflow:\n"
            "github.com/midwestmade4u-prog/channelstack-ig/actions\n"
            "Find the failed run and check the full error output."
        ),
    },
}


def classify_error(message: str) -> str:
    lower = message.lower()
    for error_class, keywords in ERROR_CLASSES.items():
        if any(kw.lower() in lower for kw in keywords):
            return error_class
    return "unknown"


# ── Auto-fix: re-trigger workflow ─────────────────────────────────────────────

def retrigger_workflow(workflow_file: str, wait_seconds: int) -> bool:
    """Wait, then fire workflow_dispatch on the failed workflow."""
    print(f"  Waiting {wait_seconds}s before retry...")
    time.sleep(wait_seconds)

    print(f"  Re-triggering {workflow_file}...")
    resp = requests.post(
        f"https://api.github.com/repos/{GH_REPO}/actions/workflows/{workflow_file}/dispatches",
        headers={
            "Authorization": f"token {GH_PAT}",
            "Accept": "application/vnd.github+json",
        },
        json={"ref": "main"}
    )
    if resp.status_code == 204:
        print(f"  ✓ Workflow re-triggered successfully")
        return True
    else:
        print(f"  ✗ Re-trigger failed: {resp.status_code} {resp.text}")
        return False


# ── Pending actions logging ───────────────────────────────────────────────────

def log_to_digest(error_class: str, fixed: bool):
    """Add a silent note to pending_actions.json for the daily digest."""
    now = datetime.now(timezone.utc)
    try:
        if os.path.exists(PENDING_FILE):
            with open(PENDING_FILE) as f:
                data = json.load(f)
        else:
            data = {"actions": []}

        data.setdefault("triage_log", []).append({
            "timestamp":   now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent":       FAILED_AGENT,
            "error_class": error_class,
            "auto_fixed":  fixed,
            "error":       ERROR_MESSAGE[:200],
        })

        with open(PENDING_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"  ✓ Logged to pending_actions.json")
    except Exception as e:
        print(f"  Warning: could not log to digest: {e}")


# ── Escalation email ──────────────────────────────────────────────────────────

def send_escalation_email(error_class: str, recipe: dict):
    now_str      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    manual_steps = recipe.get("manual_steps", "Check GitHub Actions logs.")
    actions_url  = f"https://github.com/{GH_REPO}/actions"

    subject = f"⚠️ [ChannelStack IG] {FAILED_AGENT} failed — {error_class.replace('_', ' ').title()}"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: -apple-system, Arial, sans-serif; background: #0a0a0a;
           color: #fff; padding: 20px; }}
    .container {{ max-width: 560px; margin: 0 auto; }}
    h2  {{ color: #e74c3c; }}
    .box {{ background: #1a1a1a; border: 1px solid #333; border-radius: 8px;
            padding: 16px; margin: 16px 0; }}
    .label {{ color: #ffc800; font-size: 0.85em; font-weight: bold;
              text-transform: uppercase; margin-bottom: 6px; }}
    pre {{ color: #ff6b6b; font-size: 0.85em; white-space: pre-wrap;
           word-break: break-all; margin: 0; }}
    .steps {{ color: #ccc; line-height: 1.7; white-space: pre-line; }}
    a {{ color: #ffc800; }}
    .footer {{ color: #555; font-size: 0.8em; margin-top: 24px; }}
  </style>
</head>
<body>
  <div class="container">
    <h2>⚠️ Agent failure — action required</h2>

    <div class="box">
      <div class="label">Failed Agent</div>
      <p style="margin:0;color:#fff;">{FAILED_AGENT}</p>
    </div>

    <div class="box">
      <div class="label">Error Class</div>
      <p style="margin:0;color:#fff;">{error_class.replace('_', ' ').title()}</p>
    </div>

    <div class="box">
      <div class="label">Error Message</div>
      <pre>{ERROR_MESSAGE[:500]}</pre>
    </div>

    <div class="box">
      <div class="label">How to Fix</div>
      <div class="steps">{manual_steps}</div>
    </div>

    <p>
      <a href="{actions_url}">→ View GitHub Actions logs</a>
    </p>

    <div class="footer">Detected at {now_str}</div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"  ✓ Escalation email sent to {NOTIFY_EMAIL}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"=== Agent 8: Error Triage ===")
    print(f"Agent  : {FAILED_AGENT}")
    print(f"Error  : {ERROR_MESSAGE[:120]}\n")

    # ── Classify ──────────────────────────────────────────────────────────────
    error_class = classify_error(ERROR_MESSAGE)
    recipe      = FIX_RECIPES.get(error_class, FIX_RECIPES["unknown"])
    print(f"Class  : {error_class}")

    # ── Attempt auto-fix ──────────────────────────────────────────────────────
    auto_fixed = False
    if recipe.get("auto_fixable") and GH_PAT:
        print(f"Auto-fix available: {recipe['description']}")
        wait = recipe.get("wait_seconds", 300)
        auto_fixed = retrigger_workflow(FAILED_AGENT, wait)

    # ── Log to digest ─────────────────────────────────────────────────────────
    log_to_digest(error_class, auto_fixed)

    # ── Escalate if not fixed ─────────────────────────────────────────────────
    if not auto_fixed:
        print("Sending escalation email...")
        try:
            send_escalation_email(error_class, recipe)
        except Exception as e:
            print(f"  ERROR sending escalation email: {e}")
            # Don't exit 1 — triage itself shouldn't fail the pipeline further
    else:
        print(f"Auto-fix succeeded — no email needed. Logged for digest.")

    print("\nAgent 8 complete.")


if __name__ == "__main__":
    main()
