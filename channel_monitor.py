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

# schedule_days uses Python's datetime.weekday() convention: Mon=0 ... Sun=6.
# Cadence cut Jul 5 2026: TMF/MZ/BSG all reduced from 14-21/wk down per analytics
# review. Monitor now only expects/flags posts on each channel's actual posting
# days -- checking every single day against a channel that posts 4x/wk would
# false-alarm "missed_posts" on the 3 off days every week.
CHANNELS = {
    "tmf": {
        "label":          "The Mind Files",
        "channel_id":     "UC0O6KbbHKW4_a7d9epNo93A",
        "token_env":      "YT_TOKEN_TMF",
        "token_file":     "youtube_token_tmf.json",
        "expected_posts": 1,
        "schedule_days":  (0, 1, 2, 3, 4, 5, 6),  # every day, 7/wk (Matt wants a daily floor)
        "workflow":       "tmf-autopost.yml",
        "fb_token_env":   "FB_PAGE_ACCESS_TOKEN_TMF",
        "fb_page_id_env": "FB_PAGE_ID_TMF",
    },
    "bsg": {
        "label":          "Bible Story Garden",
        "channel_id":     "UCcyBf84Mc-evMSYZlqh3zVA",
        "token_env":      "YT_TOKEN_BSG",
        "token_file":     "youtube_token_bsg.json",
        "expected_posts": 1,
        "schedule_days":  (0, 1, 2, 3, 4, 5, 6),  # every day, 7/wk
        "workflow":       "bsg-autopost.yml",
        "fb_token_env":   "FB_PAGE_ACCESS_TOKEN_BSG",
        "fb_page_id_env": "FB_PAGE_ID_BSG",
    },
    "mz": {
        "label":          "Minute Zero",
        "channel_id":     "UCMVhjR4HetJctXeYkuPgg6w",
        "token_env":      "YT_TOKEN_MZ",
        "token_file":     "youtube_token_mz.json",
        "expected_posts": 1,
        "schedule_days":  (0, 1, 2, 3, 4, 5, 6),  # every day, 7/wk (Matt wants a daily floor)
        "workflow":       "mz-autopost.yml",
        "fb_token_env":   "FB_PAGE_ACCESS_TOKEN_MZ",
        "fb_page_id_env": "FB_PAGE_ID_MZ",
    },
}
# --- BSG RETIRED 2026-08-30 ------------------------------------------
# 38 videos in 28 days -> 499 views, median 3/video, 0 subscribers gained.
# See project doc youtube_28day_MEASURED_and_ypp_correction_aug30.
# The config above is left intact on purpose. To bring BSG back, delete
# the single .pop() line below.
CHANNELS.pop("bsg", None)

# Issue types that warrant an email alert.
# fb_missed_post and workflow_failure (when YT still posted) are logged to Sheets only.
CRITICAL_ISSUE_TYPES = {
    "missed_posts",           # YouTube video count below expected
    "yt_api_error",           # Can't reach YouTube API at all
    "no_workflow_runs",       # Workflow never fired
    "silent_upload_failure",  # Workflow said success but 0 YT posts
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


def videos_posted_last_24h(channel_id: str, token_file: str, retries: int = 3) -> list[dict]:
    """Return list of videos published to channel_id in the last 24 hours.
    Retries up to `retries` times with exponential backoff on transient errors."""
    last_err = None
    for attempt in range(retries):
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
            last_err = e
            wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
            print(f"  ⚠️  YT API attempt {attempt + 1}/{retries} failed: {e} — retrying in {wait}s")
            time.sleep(wait)
    return [{"error": str(last_err)[:120]}]


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
    import zipfile, io
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}/logs"
    try:
        r = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        # Logs are returned as a ZIP — extract all text files and concatenate
        try:
            zf = zipfile.ZipFile(io.BytesIO(r.content))
            lines = []
            for name in zf.namelist():
                if name.endswith(".txt"):
                    lines.append(zf.read(name).decode("utf-8", errors="ignore"))
            return "\n".join(lines)[-3000:]
        except zipfile.BadZipFile:
            # Fallback: treat as plain text (e.g. redirect or error response)
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


# ─── Duplicate Detection ──────────────────────────────────────────────────────

def detect_duplicate_videos(channel_id: str, token_file: str, label: str,
                             lookback_days: int = 30) -> list[dict]:
    """Scan a channel's recent videos for duplicate titles or company repeats.

    Flags:
      - Exact or near-exact title duplicates (normalised lowercase)
      - MZ-specific: same company name appearing in >1 video title within window

    Returns a list of dicts:
      {"type": "duplicate_title"|"duplicate_company", "videos": [...titles], "label": channel_label}
    """
    import re
    flags: list[dict] = []

    try:
        svc = get_yt_service(token_file)
        since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        resp = svc.search().list(
            part="snippet",
            channelId=channel_id,
            publishedAfter=since,
            type="video",
            order="date",
            maxResults=50,
        ).execute()
    except Exception as e:
        print(f"  ⚠️  [{label}] duplicate check API error: {e}")
        return []

    titles = [
        item["snippet"]["title"]
        for item in resp.get("items", [])
        if "snippet" in item
    ]

    if not titles:
        return []

    # 1. Exact / near-exact title duplicates (lowercased, stripped)
    def _norm(t: str) -> str:
        return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()

    seen: dict[str, list[str]] = {}
    for t in titles:
        key = _norm(t)
        seen.setdefault(key, []).append(t)

    for key, dupes in seen.items():
        if len(dupes) > 1:
            flags.append({
                "type": "duplicate_title",
                "label": label,
                "videos": dupes,
                "detail": f"Exact title posted {len(dupes)}×: \"{dupes[0]}\"",
            })

    # 2. MZ company-level duplicates (first significant word in title)
    if "Minute Zero" in label or label.lower() == "mz":
        _skip = {"the", "how", "one", "that", "this", "from", "into", "with", "its",
                 "was", "and", "for", "why", "what", "when", "who",
                 "billion", "million", "nearly", "almost",
                 "saved", "killed", "exposed", "destroyed", "crashed", "collapsed",
                 "survived", "failed", "went", "built", "lost", "bet", "deal"}

        company_map: dict[str, list[str]] = {}
        for t in titles:
            words = re.findall(r"[A-Za-z]{3,}", t)
            sig = [w.lower() for w in words if w.lower() not in _skip]
            if sig:
                anchor = sig[0]
                company_map.setdefault(anchor, []).append(t)

        for company, vids in company_map.items():
            if len(vids) > 1:
                flags.append({
                    "type": "duplicate_company",
                    "label": label,
                    "videos": vids,
                    "detail": f"Company '{company}' appears in {len(vids)} videos: {vids}",
                })

    if flags:
        print(f"  🔴 [{label}] {len(flags)} duplicate flag(s) found")
    else:
        print(f"  ✅ [{label}] no duplicates detected")

    return flags


# ─── Facebook Page Check ─────────────────────────────────────────────────────

def check_fb_page_posts(page_token: str, page_id: str, hours: int = 25) -> dict:
    """Check if at least one video was posted to the FB page in the last `hours` hours.

    Returns:
      {"ok": True,  "count": N, "posts": [...]}  — N posts found
      {"ok": False, "error": "..."}               — API error or token issue
    """
    try:
        since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
        resp = requests.get(
            f"https://graph.facebook.com/v25.0/{page_id}/videos",
            params={
                "fields": "title,created_time",
                "since":  since,
                "limit":  10,
                "access_token": page_token,
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            return {"ok": False, "error": data["error"].get("message", "unknown FB error")[:100]}
        posts = data.get("data", [])
        return {"ok": True, "count": len(posts), "posts": posts}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


# ─── Auto-Fix Actions ────────────────────────────────────────────────────────
#
# Safety principle: every auto-fix re-verifies before acting.
# We never dispatch a rerun or post a fallback based solely on the initial check —
# we always confirm the problem still exists right before pulling the trigger.
# This prevents duplicate posts caused by API lag or timing races.

def auto_rerun_failed_jobs(run_id: int, label: str) -> bool:
    """Re-run only the failed jobs in a workflow run via GitHub API.

    Returns True if the rerun was successfully triggered.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}/rerun-failed-jobs"
    try:
        r = requests.post(url, headers=headers, timeout=15)
        if r.status_code in (201, 204):
            print(f"    🔧 [{label}] Auto-rerun triggered for run {run_id}")
            return True
        print(f"    ⚠️  [{label}] Auto-rerun failed: {r.status_code} {r.text[:80]}")
        return False
    except Exception as e:
        print(f"    ⚠️  [{label}] Auto-rerun error: {e}")
        return False


def auto_dispatch_workflow(workflow_file: str, label: str) -> bool:
    """Dispatch a workflow_dispatch event to re-trigger a missed workflow run.

    Only safe to call when we've already confirmed 0 YT posts AND 0 workflow runs.
    Returns True if the dispatch was accepted.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{workflow_file}/dispatches"
    try:
        r = requests.post(url, headers=headers, json={"ref": "main"}, timeout=15)
        if r.status_code == 204:
            print(f"    🔧 [{label}] Auto-dispatched {workflow_file}")
            return True
        print(f"    ⚠️  [{label}] Auto-dispatch failed: {r.status_code} {r.text[:80]}")
        return False
    except Exception as e:
        print(f"    ⚠️  [{label}] Auto-dispatch error: {e}")
        return False


def fb_post_yt_link(page_token: str, page_id: str, yt_url: str,
                    title: str, label: str) -> bool:
    """Post a YouTube link to a Facebook page as a fallback when native video upload failed.

    Safety: re-checks the FB page one more time right before posting to guard against
    API lag (the native video might have just appeared). Returns True only if a new
    link post was successfully published.
    """
    # Re-verify: did the native video show up since the initial check?
    recheck = check_fb_page_posts(page_token, page_id, hours=25)
    if recheck.get("ok") and recheck.get("count", 0) > 0:
        print(f"    ✅ [{label}] FB re-check found {recheck['count']} post(s) — native video appeared, skipping fallback")
        return False  # Not a failure — already posted

    try:
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{page_id}/feed",
            data={
                "message":      title,
                "link":         yt_url,
                "access_token": page_token,
            },
            timeout=20,
        )
        data = resp.json()
        if "id" in data:
            print(f"    🔧 [{label}] FB link-post fallback published: {yt_url}")
            return True
        print(f"    ⚠️  [{label}] FB link-post failed: {data}")
        return False
    except Exception as e:
        print(f"    ⚠️  [{label}] FB link-post error: {e}")
        return False


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


# ─── Longform Queue Feeding ───────────────────────────────────────────────────

LONGFORM_QUEUES = {
    "tmf": {"file": "tmf_longform_queue.json", "threshold": 150},
    "mz":  {"file": "mz_longform_queue.json",  "threshold": 300},
    "bsg": {"file": "bsg_longform_queue.json",  "threshold": 50},
}
# --- BSG RETIRED 2026-08-30 ------------------------------------------
# 38 videos in 28 days -> 499 views, median 3/video, 0 subscribers gained.
# See project doc youtube_28day_MEASURED_and_ypp_correction_aug30.
# The config above is left intact on purpose. To bring BSG back, delete
# the single .pop() line below.
LONGFORM_QUEUES.pop("bsg", None)


def update_longform_queue(channel_key: str, channel_id: str, token_file: str) -> int:
    """
    Check channel's shorts for breakout views. Any short crossing the threshold
    that isn't already in the queue gets added as a pending longform seed topic.
    Returns number of new items added.
    """
    cfg = LONGFORM_QUEUES.get(channel_key)
    if not cfg:
        return 0

    queue_file = cfg["file"]
    threshold  = cfg["threshold"]

    # Load existing queue
    from pathlib import Path
    queue = []
    if Path(queue_file).exists():
        try:
            queue = json.loads(Path(queue_file).read_text())
        except Exception:
            pass
    existing_ids = {item.get("video_id") for item in queue}

    try:
        svc = get_yt_service(token_file)

        # Fetch up to 50 most-viewed videos from this channel
        search_resp = svc.search().list(
            part="id,snippet",
            channelId=channel_id,
            type="video",
            maxResults=50,
            order="viewCount",
        ).execute()

        video_ids = [
            i["id"]["videoId"]
            for i in search_resp.get("items", [])
            if i.get("id", {}).get("videoId")
        ]
        if not video_ids:
            return 0

        # Get view counts + duration to filter shorts only
        stats_resp = svc.videos().list(
            part="statistics,contentDetails,snippet",
            id=",".join(video_ids[:50]),
        ).execute()

        added = 0
        for video in stats_resp.get("items", []):
            vid_id   = video["id"]
            title    = video["snippet"]["title"]
            views    = int(video.get("statistics", {}).get("viewCount", 0))
            duration = video.get("contentDetails", {}).get("duration", "PT99M")

            # Parse ISO 8601 duration — keep only shorts (< 3 min)
            import re
            m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
            hours   = int(m.group(1) or 0) if m else 0
            minutes = int(m.group(2) or 0) if m else 99
            seconds = int(m.group(3) or 0) if m else 0
            total_sec = hours * 3600 + minutes * 60 + seconds
            if total_sec > 180:
                continue  # skip long-form videos already on channel

            if views >= threshold and vid_id not in existing_ids:
                queue.append({
                    "video_id":  vid_id,
                    "title":     title,
                    "topic":     title,   # longform scripts use title as seed
                    "views":     views,
                    "status":    "pending",
                    "queued_at": datetime.now(CT).strftime("%Y-%m-%d"),
                    "channel":   channel_key,
                    "short_url": f"https://youtu.be/{vid_id}",
                })
                existing_ids.add(vid_id)
                added += 1
                print(f"    🚀 Queued for longform: {title[:55]} ({views:,} views)")

        if added > 0:
            Path(queue_file).write_text(json.dumps(queue, indent=2))
            print(f"  ✅ {added} new topic(s) added to {queue_file}")
        else:
            print(f"  ℹ️  No new breakouts above {threshold:,} views for {channel_key.upper()}")

        return added

    except Exception as e:
        print(f"  ⚠️  Longform queue update failed ({channel_key}): {e}")
        return 0


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    now_ct = datetime.now(CT)
    # The 26h lookback window means we're really validating "yesterday's" posting
    # day (monitor runs at 2 AM CT, workflows fire earlier the previous day).
    yesterday_ct = now_ct - timedelta(days=1)
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

        # Is yesterday one of this channel's scheduled posting days?
        # (defaults to every day if schedule_days isn't set, for safety)
        is_scheduled_day = yesterday_ct.weekday() in ch.get("schedule_days", range(7))

        # 1. Check YouTube posts
        videos = videos_posted_last_24h(ch["channel_id"], ch["token_file"])
        post_errors = [v for v in videos if "error" in v]
        actual_posts = len([v for v in videos if "error" not in v])
        expected = ch["expected_posts"] if is_scheduled_day else 0

        yt_status = "✅ OK"
        if post_errors:
            yt_status = f"❌ API error: {post_errors[0]['error'][:60]}"
            issues.append({"channel": ch["label"], "type": "yt_api_error", "detail": post_errors[0]["error"]})
        elif not is_scheduled_day and actual_posts == 0:
            yt_status = "⏭️  off day (not scheduled)"
        elif actual_posts < expected:
            yt_status = f"⚠️  Expected {expected} / Published {actual_posts}"
            issues.append({
                "channel":  ch["label"],
                "type":     "missed_posts",
                "detail":   f"Expected {expected} / Published {actual_posts} (last 24h)",
                "videos":   videos,
            })
        else:
            yt_status = f"✅ Expected {expected} / Published {actual_posts}"

        print(f"  YouTube: {yt_status}")

        # 2. Check GitHub Actions
        runs = get_recent_workflow_runs(ch["workflow"])
        run_errors = [r for r in runs if "error" in r]
        failed_runs = [r for r in runs if r.get("conclusion") in ("failure", "cancelled")]
        error_type = "unknown"  # Set below if a failed run is found

        gh_status = "✅ OK"
        if run_errors:
            gh_status = f"❌ API error: {run_errors[0]['error'][:60]}"
        elif not runs and not is_scheduled_day:
            gh_status = "⏭️  no runs (off day, not scheduled)"
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

        # 3. Check Facebook posting
        fb_token   = os.environ.get(ch.get("fb_token_env", ""), "").strip()
        fb_page_id = os.environ.get(ch.get("fb_page_id_env", ""), "").strip()
        fb_status  = "⏭️ skipped (no token)"
        if fb_token and fb_page_id:
            fb_result = check_fb_page_posts(fb_token, fb_page_id)
            if not fb_result["ok"]:
                fb_status = f"❌ {fb_result['error']}"
                issues.append({
                    "channel": ch["label"],
                    "type":    "fb_api_error",
                    "detail":  fb_result["error"],
                })
            elif fb_result["count"] == 0:
                fb_status = "⚠️  0 FB posts in last 25h"
                issues.append({
                    "channel": ch["label"],
                    "type":    "fb_missed_post",
                    "detail":  "No FB video found on page in last 25h — cross-post may have failed",
                })
            else:
                fb_status = f"✅ {fb_result['count']} FB post(s)"
        print(f"  Facebook: {fb_status}")

        # ── Auto-fix ─────────────────────────────────────────────────────────
        # Each rule re-verifies the problem before acting to prevent false triggers.

        # Rule 1: Workflow failed + YT also missed → rerun (non-quota errors only)
        # Guard: only act if actual_posts == 0, confirming the run truly produced nothing.
        if failed_runs and actual_posts == 0 and error_type not in ("openai_quota", "anthropic_quota"):
            print(f"  🔧 Auto-fix: workflow failed + 0 YT posts — rerunning failed jobs...")
            if auto_rerun_failed_jobs(failed_runs[0]["id"], ch["label"]):
                issues = [i for i in issues if not (
                    i["channel"] == ch["label"] and i["type"] == "workflow_failure"
                )]
                issues.append({
                    "channel": ch["label"],
                    "type":    "auto_fixed",
                    "detail":  f"Workflow rerun triggered (error was: {error_type})",
                })

        # Rule 2: No workflow runs found + 0 YT posts → dispatch fresh run
        # Guard: both conditions must be true — if posts exist, don't dispatch.
        # Guard: only on scheduled posting days — an off day is expected to have 0 runs.
        if not runs and not run_errors and actual_posts == 0 and is_scheduled_day:
            print(f"  🔧 Auto-fix: no workflow runs + 0 YT posts — dispatching {ch['workflow']}...")
            auto_dispatch_workflow(ch["workflow"], ch["label"])

        # Rule 3: FB missed post but YT posted fine → re-verify FB then post link fallback
        # Guard: fb_post_yt_link() re-checks FB page before posting to catch API lag.
        # Only fires when YT succeeded (actual_posts >= expected) — we know a video exists.
        if fb_status.startswith("⚠️") and actual_posts >= expected and fb_token and fb_page_id:
            good_videos = [v for v in videos if "error" not in v]
            if good_videos:
                yt_url   = good_videos[0]["url"]
                yt_title = good_videos[0]["title"]
                print(f"  🔧 Auto-fix: FB missed — re-verifying then posting link fallback...")
                if fb_post_yt_link(fb_token, fb_page_id, yt_url, yt_title, ch["label"]):
                    issues = [i for i in issues if not (
                        i["channel"] == ch["label"] and i["type"] == "fb_missed_post"
                    )]
                    issues.append({
                        "channel": ch["label"],
                        "type":    "auto_fixed",
                        "detail":  f"FB link-post fallback published: {yt_url}",
                    })


        # Rule 4: Workflow "succeeded" (continue-on-error) but 0 YT posts → silent failure alert
        # This catches the case where the auto-post step exits 1 but continue-on-error:true
        # makes the workflow report "success". The monitor sees 0 posts but no failed_runs,
        # so Rules 1 and 2 never fire. Rule 4 fills that gap by alerting immediately.
        # Guard: must have at least one run (not zero runs — that's Rule 2's job), no failed
        # runs (that's Rule 1), and zero actual posts despite expecting some.
        if runs and not failed_runs and not run_errors and actual_posts == 0 and expected > 0:
            print(f"  🚨 Rule 4: workflow reported success but 0 YT posts — silent upload failure!")
            # Do NOT blame the YouTube token here. Reaching this branch requires
            # videos_posted_last_24h() to have returned cleanly, and that call
            # authenticates with this very token file -- an expired or invalid
            # token raises and yields an "error" entry, which run_errors /
            # actual_posts would have caught above. In other words, by the time
            # Rule 4 fires we have just PROVED the token works.
            #
            # The old text said "Likely cause: YouTube token expired/invalid
            # (re-OAuth needed)". On Aug 4 2026 that sent Matt to re-OAuth BSG
            # two days after he already had, on a token that published fine the
            # same day. Point at the causes that are actually still open.
            issues.append({
                "channel": ch["label"],
                "type":    "silent_upload_failure",
                "detail":  (
                    f"Workflow ran and reported ✅ success (continue-on-error) but "
                    f"Expected {expected} / Published 0 on YouTube. "
                    f"NOTE: the YouTube token is NOT the cause — this monitor "
                    f"authenticated with it moments ago to read the channel, so it is "
                    f"valid. Do not re-OAuth on the strength of this alert. "
                    f"Check instead, in order: (1) script generation returning empty or "
                    f"malformed JSON, (2) the render step producing no video file, "
                    f"(3) the upload call failing under continue-on-error. "
                    f"Last run: {runs[0].get('url', 'unknown')}"
                ),
            })

        # 4. Duplicate title / company detection
        if token_json:
            print(f"  Checking for duplicate videos...")
            dup_flags = detect_duplicate_videos(
                ch["channel_id"], ch["token_file"], ch["label"], lookback_days=30
            )
            for flag in dup_flags:
                issues.append({
                    "channel":  ch["label"],
                    "type":     flag["type"],
                    "detail":   flag["detail"],
                    "videos":   flag.get("videos", []),
                })

        # 5. Feed longform queue from top-performing shorts
        if token_json:
            print(f"  Checking longform queue...")
            update_longform_queue(key, ch["channel_id"], ch["token_file"])

        # Sheet row: date | channel | yt_status | gh_status | fb_status
        sheet_rows.append([date_str, ch["label"], yt_status, gh_status, fb_status])

    # Log to Sheets
    append_to_sheets(sheet_rows)

    # Split issues into critical (email) vs non-critical (Sheets only)
    critical_issues = [i for i in issues if i["type"] in CRITICAL_ISSUE_TYPES]
    noise_issues    = [i for i in issues if i["type"] not in CRITICAL_ISSUE_TYPES]

    if noise_issues:
        print(f"\nℹ️  {len(noise_issues)} non-critical issue(s) logged to Sheets (no email):")
        for i in noise_issues:
            print(f"   • {i['channel']}: {i['type']} — {i.get('detail', i.get('run_url', ''))[:80]}")

    # Send alert email only for critical issues (missed YT posts / API failures)
    if critical_issues:
        diagnosis = diagnose_with_claude(critical_issues)
        print(f"\n🚨 {len(critical_issues)} CRITICAL issue(s) — sending alert email")
        print(f"  Diagnosis: {diagnosis}")

        sheets_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid=0"
        issue_lines = "\n".join(
            f"• {i['channel']}: {i['type']} — {i.get('detail', i.get('run_url', ''))}"
            + (f"\n  Videos: {i['videos']}" if i.get('videos') else "")
            for i in critical_issues
        )

        body_text = (
            f"YouTube Channel Monitor — {date_str}\n\n"
            f"⚠️  {len(critical_issues)} issue(s) detected:\n{issue_lines}\n\n"
            f"Diagnosis:\n{diagnosis}\n\n"
            f"Full log: {sheets_url}"
        )
        body_html = f"""
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
          <h2 style="color:#c0392b">⚠️ Channel Monitor Alert — {date_str}</h2>
          <p><strong>{len(critical_issues)} issue(s) detected:</strong></p>
          <ul>{''.join(f"<li><b>{i['channel']}</b>: {i['type']} — {i.get('detail', i.get('run_url', ''))}</li>" for i in critical_issues)}</ul>
          <p><strong>Diagnosis:</strong><br>{diagnosis}</p>
          <p><a href="{sheets_url}" style="background:#2980b9;color:white;padding:10px 20px;text-decoration:none;border-radius:4px">View Full Log in Sheets</a></p>
        </div>
        """
        send_alert_email(
            subject=f"🚨 Channel Alert ({len(critical_issues)} issue{'s' if len(critical_issues) > 1 else ''}) — {date_str}",
            body_text=body_text,
            body_html=body_html,
        )
    else:
        print(f"\n✅ All clear — no critical issues. No email sent.")

    print(f"\n{'═'*60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
