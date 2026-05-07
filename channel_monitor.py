#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  channel_monitor.py — Daily overnight channel health check   ║
╚══════════════════════════════════════════════════════════════╝

Runs nightly at 2 AM CT via GitHub Actions (channel-monitor.yml).

Checks:
  1. Did each channel post the expected number of videos in the last 24h?
  2. Did all GitHub Actions workflows succeed?
  3. Are there any known fixable errors in recent run logs?

Outputs:
  - Appends a status row to Google Sheets "Daily Monitor" tab
  - Sends an email to ALERT_EMAIL only if issues are found
  - Silence = all clear

Required env vars (GitHub Secrets):
  GOOGLE_SHEETS_KEY     — service account JSON
  GITHUB_TOKEN          — auto-provided by GH Actions
  ANTHROPIC_API_KEY     — for error diagnosis
  GMAIL_APP_PASSWORD    — app password for wisseinc@gmail.com
  YT_TOKEN_TMF          — YouTube OAuth token for TMF
  YT_TOKEN_BSG          — YouTube OAuth token for BSG
  YT_TOKEN_MZ           — YouTube OAuth token for MZ
"""

from __future__ import annotations

import json
import os
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import requests

# ─── Config ──────────────────────────────────────────────────────────────────

SPREADSHEET_ID  = "1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI"
SHEETS_TAB      = "Daily Monitor"
ALERT_EMAIL     = "wisseinc@gmail.com"
FROM_EMAIL      = "wisseinc@gmail.com"
GITHUB_REPO     = "midwestmade4u-prog/youtube-autopost"
CT              = ZoneInfo("America/Chicago")

CHANNELS = {
    "tmf": {
        "label":       "The Mind Files",
        "channel_id":  "UC0O6KbbHKW4_a7d9epNo93A",
        "token_env":   "YT_TOKEN_TMF",
        "token_file":  "youtube_token_tmf.json",
        "expected_posts": 3,
        "workflow":    "tmf-autopost.yml",
    },
    "bsg": {
        "label":       "Bible Story Garden",
        "channel_id":  "UCcyBf84Mc-evMSYZlqh3zVA",
        "token_env":   "YT_TOKEN_BSG",
        "token_file":  "youtube_token_bsg.json",
        "expected_posts": 2,
        "workflow":    "youtube-autopost.yml",
    },
    "mz": {
        "label":       "Minute Zero",
        "channel_id":  "UCMVhjR4HetJctXeYkuPgg6w",
        "token_env":   "YT_TOKEN_MZ",
        "token_file":  "youtube_token_mz.json",
        "expected_posts": 2,
        "workflow":    "mz-autopost.yml",
    },
}

# Errors we know how to fix automatically (safe list)
AUTO_FIX_PATTERNS = {
    "insufficient_quota":        "openai_quota",
    "Your credit balance is too low": "anthropic_quota",
    "job not acquired":          "github_infra",   # not fixable, just classify
    "timeout":                   "github_timeout", # not fixable, just classify
}

# ─── YouTube Data API ─────────────────────────────────────────────────────────

def get_yt_service(token_file: str):
    """Build an authenticated YouTube service from a token JSON file."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(json.loads(open(token_file).read()))
    return build("youtube", "v3", credentials=creds)


def videos_posted_last_24h(channel_id: str, token_file: str) -> list[dict]:
    """Return list of videos published to channel_id in the last 24 hours."""
    try:
        svc = get_yt_service(token_file)
        since = (datetime.now(timezone.utc) - timedelta(hours=26)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = svc.search().list(
            part="snippet",
            channelId=channel_id,
            publishedAfter=since,
            type="video",
            maxResults=10,
            order="date",
        ).execute()
        items = resp.get("items", [])
        return [
            {
                "title":      i["snippet"]["title"],
                "video_id":   i["id"]["videoId"],
                "published":  i["snippet"]["publishedAt"],
                "url":        f"https://youtu.be/{i['id']['videoId']}",
            }
            for i in items
        ]
    except Exception as e:
        return [{"error": str(e)[:120]}]


# ─── GitHub Actions API ───────────────────────────────────────────────────────

def get_recent_workflow_runs(workflow_file: str, hours: int = 26) -> list[dict]:
    """Fetch recent runs for a workflow file from the GitHub Actions API."""
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{workflow_file}/runs"
    params = {"per_page": 10}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        runs = r.json().get("workflow_runs", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent = []
        for run in runs:
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            if created >= cutoff:
                recent.append({
                    "id":         run["id"],
                    "status":     run["status"],
                    "conclusion": run["conclusion"],
                    "created_at": run["created_at"],
                    "url":        run["html_url"],
                })
        return recent
    except Exception as e:
        return [{"error": str(e)[:120]}]


def get_run_log_snippet(run_id: int) -> str:
    """Download and return the last 3000 chars of a workflow run log."""
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}/logs"
    try:
        r = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        # Logs come as a zip — just grab raw text for pattern matching
        return r.content.decode("utf-8", errors="ignore")[-3000:]
    except Exception as e:
        return f"(could not fetch log: {e})"


def classify_error(log_snippet: str) -> str:
    """Classify a failed run log into a known error category."""
    for pattern, category in AUTO_FIX_PATTERNS.items():
        if pattern.lower() in log_snippet.lower():
            return category
    return "unknown"


# ─── Claude diagnosis ─────────────────────────────────────────────────────────

def diagnose_with_claude(issues: list[dict]) -> str:
    """Ask Claude to summarize issues and suggest fixes in plain English."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return "(Claude diagnosis unavailable — ANTHROPIC_API_KEY not set)"
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        issue_text = json.dumps(issues, indent=2)
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": (
                    "You are monitoring a YouTube automation system. "
                    "Here are the issues detected in the last 24 hours:\n\n"
                    f"{issue_text}\n\n"
                    "Respond in plain English with:\n"
                    "1. A one-sentence summary of what went wrong\n"
                    "2. Whether this is likely a code bug, API quota, or infrastructure issue\n"
                    "3. The recommended fix (be specific)\n"
                    "Keep it under 150 words. No markdown."
                )
            }]
        )
        return r.content[0].text.strip()
    except Exception as e:
        return f"(Claude diagnosis failed: {e})"


# ─── Google Sheets ────────────────────────────────────────────────────────────

def append_to_sheets(rows: list[list]) -> None:
    """Append rows to the Daily Monitor tab."""
    creds_json = os.environ.get("GOOGLE_SHEETS_KEY", "")
    if not creds_json:
        print("  ⚠️  GOOGLE_SHEETS_KEY not set — skipping Sheets log")
        return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        svc = build("sheets", "v4", credentials=creds)
        svc.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEETS_TAB}!A:Z",
            valueInputOption="USER_ENTERED",
            body={"values": rows}
        ).execute()
        print(f"  📊 Logged {len(rows)} row(s) to Sheets")
    except Exception as e:
        print(f"  ⚠️  Sheets logging failed: {e}")


# ─── Email ────────────────────────────────────────────────────────────────────

def send_alert_email(subject: str, body_text: str, body_html: str) -> None:
    """Send alert email via Gmail SMTP."""
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not password:
        print("  ⚠️  GMAIL_APP_PASSWORD not set — skipping email")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = FROM_EMAIL
        msg["To"]      = ALERT_EMAIL
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(FROM_EMAIL, password)
            server.sendmail(FROM_EMAIL, ALERT_EMAIL, msg.as_string())
        print(f"  📧 Alert email sent to {ALERT_EMAIL}")
    except Exception as e:
        print(f"  ⚠️  Email failed: {e}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    now_ct = datetime.now(CT)
    date_str = now_ct.strftime("%Y-%m-%d")
    print(f"\n{'═'*60}")
    print(f"  📡 Channel Monitor  |  {now_ct.strftime('%Y-%m-%d %H:%M CT')}")
    print(f"{'═'*60}\n")

    issues: list[dict] = []
    sheet_rows: list[list] = []

    for key, ch in CHANNELS.items():
        print(f"Checking {ch['label']} ...")

        # Write token file from env
        token_json = os.environ.get(ch["token_env"], "")
        if token_json:
            open(ch["token_file"], "w").write(token_json)

        # 1. Check YouTube posts
        videos = videos_posted_last_24h(ch["channel_id"], ch["token_file"])
        post_errors = [v for v in videos if "error" in v]
        actual_posts = len([v for v in videos if "error" not in v])
        expected = ch["expected_posts"]

        yt_status = "✅ OK"
        if post_errors:
            yt_status = f"❌ API error: {post_errors[0]['error'][:60]}"
            issues.append({"channel": ch["label"], "type": "yt_api_error", "detail": post_errors[0]["error"]})
        elif actual_posts < expected:
            yt_status = f"⚠️  {actual_posts}/{expected} videos posted"
            issues.append({
                "channel":  ch["label"],
                "type":     "missed_posts",
                "detail":   f"Expected {expected}, found {actual_posts} in last 24h",
                "videos":   videos,
            })
        else:
            yt_status = f"✅ {actual_posts}/{expected} posted"

        print(f"  YouTube: {yt_status}")

        # 2. Check GitHub Actions
        runs = get_recent_workflow_runs(ch["workflow"])
        run_errors = [r for r in runs if "error" in r]
        failed_runs = [r for r in runs if r.get("conclusion") in ("failure", "cancelled")]

        gh_status = "✅ OK"
        if run_errors:
            gh_status = f"❌ API error: {run_errors[0]['error'][:60]}"
        elif not runs:
            gh_status = "⚠️  No runs in last 24h"
            issues.append({"channel": ch["label"], "type": "no_workflow_runs", "detail": "No runs found"})
        elif failed_runs:
            run = failed_runs[0]
            log = get_run_log_snippet(run["id"])
            error_type = classify_error(log)
            gh_status = f"❌ {run['conclusion']} ({error_type}) — {run['url']}"
            if error_type not in ("github_infra", "github_timeout"):
                issues.append({
                    "channel":    ch["label"],
                    "type":       "workflow_failure",
                    "error_type": error_type,
                    "run_url":    run["url"],
                    "log_tail":   log[-500:],
                })
            else:
                print(f"    ℹ️  Infrastructure failure ({error_type}) — not actionable, skipping")
        else:
            gh_status = f"✅ {len(runs)} run(s) succeeded"

        print(f"  GitHub:  {gh_status}")

        # Sheet row: date | channel | yt_status | gh_status
        sheet_rows.append([date_str, ch["label"], yt_status, gh_status])

    # Log to Sheets
    append_to_sheets(sheet_rows)

    # Send alert email only if actionable issues exist
    if issues:
        diagnosis = diagnose_with_claude(issues)
        print(f"\n🚨 {len(issues)} issue(s) found — sending alert email")
        print(f"  Diagnosis: {diagnosis}")

        sheets_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid=0"
        issue_lines = "\n".join(
            f"• {i['channel']}: {i['type']} — {i.get('detail', i.get('run_url', ''))}"
            for i in issues
        )

        body_text = (
            f"YouTube Channel Monitor — {date_str}\n\n"
            f"⚠️  {len(issues)} issue(s) detected:\n{issue_lines}\n\n"
            f"Diagnosis:\n{diagnosis}\n\n"
            f"Full log: {sheets_url}"
        )
        body_html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
          <h2 style="color:#c0392b">⚠️ Channel Monitor Alert — {date_str}</h2>
          <p><strong>{len(issues)} issue(s) detected:</strong></p>
          <ul>{''.join(f"<li><b>{i['channel']}</b>: {i['type']} — {i.get('detail', i.get('run_url', ''))}</li>" for i in issues)}</ul>
          <p><strong>Diagnosis:</strong><br>{diagnosis}</p>
          <p><a href="{sheets_url}" style="background:#2980b9;color:white;padding:10px 20px;text-decoration:none;border-radius:4px">View Full Log in Sheets</a></p>
        </div>
        """
        send_alert_email(
            subject=f"🚨 Channel Alert ({len(issues)} issue{'s' if len(issues) > 1 else ''}) — {date_str}",
            body_text=body_text,
            body_html=body_html,
        )
    else:
        print(f"\n✅ All clear — no issues detected. No email sent.")

    print(f"\n{'═'*60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
