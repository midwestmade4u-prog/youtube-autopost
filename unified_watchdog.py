#!/usr/bin/env python3
"""
Unified Channel Watchdog
========================
Checks YouTube DIRECTLY (not log files) to verify posts happened.
Auto-retries via GitHub Actions workflow_dispatch.
Sends specific diagnostic alerts when human action is needed.

Usage (called from GH Actions watchdog workflows):
  python3 unified_watchdog.py --channel mz --slot-utc 14 --post-type shorts --check-type retry
  python3 unified_watchdog.py --channel mz --slot-utc 14 --post-type shorts --check-type alert
  python3 unified_watchdog.py --channel tmf --slot-utc 15 --post-type longform --check-type retry --slot-day 0
"""

import argparse, json, os, re, smtplib, sys, urllib.request as ureq
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Channel config ──────────────────────────────────────────────────────────
CHANNELS = {
    "tmf": {
        "label":            "The Mind Files",
        "channel_id":       "UC0O6KbbHKW4_a7d9epNo93A",
        "token_file":       "youtube_token_tmf.json",
        "workflow_shorts":  "tmf-autopost.yml",
        "workflow_longform":"tmf-longform.yml",
        "color":            "#6b3fa0",
        "token_name":       "YT_TOKEN_TMF",
        "refresh_script":   "refresh_token_tmf.py",
    },
    "mz": {
        "label":            "Minute Zero",
        "channel_id":       "UCMVhjR4HetJctXeYkuPgg6w",
        "token_file":       "youtube_token_mz.json",
        "workflow_shorts":  "mz-autopost.yml",
        "workflow_longform":"mz-longform.yml",
        "color":            "#cc0000",
        "token_name":       "YT_TOKEN_MZ",
        "refresh_script":   "refresh_token_mz.py",
    },
    "bsg": {
        "label":            "Bible Story Garden",
        "channel_id":       "UCcyBf84Mc-evMSYZlqh3zVA",
        "token_file":       "youtube_token_bsg.json",
        "workflow_shorts":  "bsg-autopost.yml",
        "workflow_longform":"bsg-longform.yml",
        "color":            "#8b6914",
        "token_name":       "YT_TOKEN_BSG",
        "refresh_script":   "refresh_token_bsg.py",
    },
}
# --- BSG RETIRED 2026-08-30 ------------------------------------------
# 38 videos in 28 days -> 499 views, median 3/video, 0 subscribers gained.
# See project doc youtube_28day_MEASURED_and_ypp_correction_aug30.
# The config above is left intact on purpose. To bring BSG back, delete
# the single .pop() line below.
CHANNELS.pop("bsg", None)

# Per-channel post-log filenames (repo root), used by _channel_posted_today()
# to tell a benign burst-guard skip apart from a real token/upload failure.
POST_LOG_FILES = {
    "tmf": "tmf_post_log.json",
    "mz":  "mz_post_log.json",
    "bsg": "bsg_post_log.json",
}
# --- BSG RETIRED 2026-08-30 ------------------------------------------
# 38 videos in 28 days -> 499 views, median 3/video, 0 subscribers gained.
# See project doc youtube_28day_MEASURED_and_ypp_correction_aug30.
# The config above is left intact on purpose. To bring BSG back, delete
# the single .pop() line below.
POST_LOG_FILES.pop("bsg", None)


# ── YouTube API check ─────────────────────────────────────────────────────────
def _duration_seconds(duration_iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_iso or "")
    h  = int(m.group(1) or 0) if m else 0
    mi = int(m.group(2) or 0) if m else 0
    s  = int(m.group(3) or 0) if m else 0
    return h * 3600 + mi * 60 + s


def check_youtube_for_recent_video(channel_id: str, token_file: str, since: datetime, post_type: str = "shorts") -> tuple[bool, str | None]:
    """
    Ground-truth check: did this channel publish a video of the EXPECTED TYPE since `since`?
    post_type: "shorts" (<=180s) or "longform" (>180s) -- prevents mistaking a same-day
    longform upload for a Shorts confirmation (or vice versa).
    Returns (found: bool, url: str | None)
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(token_file)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)

        # Get uploads playlist ID
        ch = youtube.channels().list(part="contentDetails", id=channel_id).execute()
        uploads_id = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Check recent uploads
        pl = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_id,
            maxResults=10,
        ).execute()

        since_utc = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since

        candidates = []
        for item in pl.get("items", []):
            pub_raw = item["snippet"]["publishedAt"]
            pub_dt  = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
            if pub_dt >= since_utc:
                candidates.append(item)

        if not candidates:
            print(f"  ❌ No video found on channel since {since_utc.strftime('%Y-%m-%d %H:%M UTC')}")
            return False, None

        # Fetch durations for all candidates in one call and filter by expected type
        vid_ids = [c["contentDetails"]["videoId"] for c in candidates]
        vresp = youtube.videos().list(part="contentDetails", id=",".join(vid_ids)).execute()
        durations = {v["id"]: _duration_seconds(v["contentDetails"].get("duration", "")) for v in vresp.get("items", [])}

        for item in candidates:
            vid_id = item["contentDetails"]["videoId"]
            title  = item["snippet"].get("title", "")
            secs   = durations.get(vid_id, 0)
            is_short = secs <= 180
            wanted_short = post_type == "shorts"
            if is_short == wanted_short:
                print(f"  ✅ Found {post_type} video ({secs}s) since {since_utc.strftime('%H:%M UTC')}: '{title}' → https://youtu.be/{vid_id}")
                return True, f"https://youtu.be/{vid_id}"
            else:
                print(f"  ⏭️  Skipping '{title}' ({secs}s) — wrong type for {post_type} check")

        print(f"  ❌ No {post_type} video found on channel since {since_utc.strftime('%Y-%m-%d %H:%M UTC')} (found {len(candidates)} video(s) of the wrong type)")
        return False, None

    except Exception as e:
        print(f"  ⚠️  YouTube API error: {e}")
        # On API error, don't false-alert — return True to suppress
        return True, None


# ── Burst-guard detection ──────────────────────────────────────────────────────
def _channel_posted_today(ch_key: str) -> bool:
    """
    Check whether this channel's post_log already has an entry for today's
    US/Central calendar date.

    Why this exists: a GH Actions run can report conclusion == "success" with
    no new video showing up in the watchdog's slot window for a completely
    benign reason -- auto_post.py's burst_guard_or_exit() intentionally exits 0
    (success, no-op) when today's per-channel posting cap is already met. This
    commonly happens when an earlier run's cron fires a few minutes late and
    lands just after local midnight (cron jitter) -- that post still counts as
    "today" for the cap check, but the watchdog's slot-window check (which only
    looks for a NEW video after the current slot's start time) doesn't see it
    and would otherwise misdiagnose this as a token/upload failure.

    Root-caused 2026-07-05 on Bible Story Garden: a 3:01 AM post satisfied the
    day's cap, and the evening watchdog check found no new video since its own
    slot start and nearly fired a false "token expired" alert. See
    project_bsg_false_token_alert_jul5 memory for the full chain.

    Returns True if a same-day post exists (i.e. the "no new video" result is
    very likely burst-guard, not a real failure). Fails safe: any fetch/parse
    error returns False, so we fall back to treating it as a real token issue
    rather than silently swallowing a genuine outage.
    """
    log_file = POST_LOG_FILES.get(ch_key)
    if not log_file:
        return False
    try:
        url = f"https://raw.githubusercontent.com/midwestmade4u-prog/youtube-autopost/main/{log_file}"
        with ureq.urlopen(url, timeout=10) as resp:
            log = json.loads(resp.read())
        posts = log.get("posts", []) if isinstance(log, dict) else log
        today_ct = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
        for post in posts:
            if post.get("channel") == ch_key and str(post.get("posted_at", "")).startswith(today_ct):
                return True
        return False
    except Exception as e:
        print(f"  ⚠️  Could not check post log for burst-guard skip: {e}")
        return False


# ── Content-skip detection ──────────────────────────────────────────────────
def _run_had_no_video_produced(run_id: int, gh_token: str) -> bool:
    """
    Distinguishes a content-generation skip from a real token/upload
    failure. When a channel's script generator can't pass its length
    validator (the primary AND fallback topic both fail after 3 retries
    each), auto_post_*.py exits 0 without ever rendering a video -- that
    "success with no video" looks identical to a real token failure
    unless we check further. See project_mz_false_token_alert_jul14
    memory for the Jul 14 2026 MZ incident this fix addresses.

    Looks at the run's job steps for "Post Facebook video (<channel>)",
    which only runs when a video file actually exists. A content-skip
    never renders a file, so that step shows conclusion "skipped". A
    real token failure DOES render the video locally (only the YouTube
    upload call itself fails), so that step still runs -- making
    "skipped" here a reliable, channel-agnostic content-skip signal.

    Fails safe: any API error or unexpected step layout returns False,
    so we never accidentally suppress a genuine token alert.
    """
    try:
        url = (f"https://api.github.com/repos/midwestmade4u-prog/youtube-autopost"
               f"/actions/runs/{run_id}/jobs")
        r = ureq.Request(url, headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
        })
        with ureq.urlopen(r, timeout=10) as resp:
            jobs = json.loads(resp.read())["jobs"]
        for job in jobs:
            for step in job.get("steps", []):
                name = (step.get("name") or "").lower()
                if "post facebook video" in name:
                    return step.get("conclusion") == "skipped"
        return False
    except Exception as e:
        print(f"  ⚠️  Could not inspect run steps for content-skip check: {e}")
        return False


# ── Real-slot derivation ─────────────────────────────────────────────────────
def _scheduled_slot_hours(workflow_file: str) -> set:
    """UTC hours the channel's autopost workflow is actually scheduled to run.

    Added Aug 2026 after the Aug 10 TMF false alarm. On Jul 5 2026 cadence was
    cut to 1x/day and the second daily cron was deleted from the autopost
    workflows, but the watchdog schedules still monitored the removed slot:

        channel  real slot   phantom slot
        TMF      13:00 UTC   23:00 UTC
        MZ       14:00 UTC   00:00 UTC
        BSG      17:00 UTC   00:00 UTC

    No autopost run can exist after a slot that isn't scheduled, so every night
    diagnose_failure() returned "no_runs_found" and emailed "the cron job may
    not have fired." That path returns before the burst-guard suppression, so
    the existing false-alarm guard couldn't catch it.

    Rather than hardcode the correct slots (which is what drifted in the first
    place), read them from the autopost workflow itself. Cadence changes now
    propagate automatically.

    Returns an empty set when the schedule can't be parsed confidently --
    an unreadable file, or an hour field using * , - or / . The caller treats
    empty as "don't suppress", so a parsing gap can never mask a real outage.
    """
    try:
        path = Path(__file__).resolve().parent / ".github" / "workflows" / workflow_file
        text = path.read_text()
    except Exception as e:
        print(f"  ⚠️  Could not read {workflow_file} to validate the slot: {e}")
        return set()

    hours = set()
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        m = re.match(r"""-\s*cron:\s*['"]([^'"]+)['"]""", stripped)
        if not m:
            continue
        fields = m.group(1).split()
        if len(fields) < 2:
            continue
        hour_field = fields[1]
        if hour_field.isdigit():
            hours.add(int(hour_field))
        else:
            # */4, 1-5, 0,12 -- don't guess, fall back to no suppression.
            return set()
    return hours


# ── In-progress detection ────────────────────────────────────────────────────
def _run_still_in_progress(workflow_id: str, slot_start: datetime, gh_token: str):
    """Return (True, html_url) if a run for this slot is still queued/running.

    Scheduled Actions runs are frequently delayed under runner load, and these
    jobs then render a video and upload it -- so finishing well after the cron
    time is normal. Measured publish windows:
        TMF cron 13:00 UTC -> posts land 13:38-14:15 (T+38 to T+75 min)
        MZ  cron 14:00 UTC -> posts land 15:09-18:05 (T+69 to T+245 min)
        BSG cron 17:00 UTC -> posts land 18:08-21:38 (T+68 to T+278 min)

    Treating in-flight as failure caused a false "action needed" email AND a
    duplicate workflow dispatch racing the original run.

    Fails safe: on any API error return False, so real outages still alert.
    """
    try:
        url = (f"https://api.github.com/repos/midwestmade4u-prog/youtube-autopost"
               f"/actions/workflows/{workflow_id}/runs?per_page=5")
        r = ureq.Request(url, headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
        })
        with ureq.urlopen(r, timeout=10) as resp:
            runs = json.loads(resp.read())["workflow_runs"]

        slot_aware = slot_start.replace(tzinfo=timezone.utc) if slot_start.tzinfo is None else slot_start
        for run in runs:
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            if created < slot_aware:
                continue
            if run.get("status") in ("queued", "in_progress") or run.get("conclusion") is None:
                return True, run.get("html_url", "")
        return False, ""
    except Exception as e:
        print(f"  ⚠️  Could not check for in-progress runs: {e}")
        return False, ""


# ── Diagnosis ─────────────────────────────────────────────────────────────
def diagnose_failure(workflow_id: str, slot_start: datetime, gh_token: str, ch_key: str) -> str:
    """
    Inspects recent GH Actions runs to identify the failure type.
    Returns a human-readable diagnosis.

    A "success" conclusion with no matching video is NOT automatically a token
    issue -- it's first checked against the channel's own post log to rule out
    a benign burst-guard skip (today's posting cap already met earlier in the
    day). Only if that check comes back negative do we report token_issue.
    See _channel_posted_today() for the full rationale.
    """
    try:
        url = (f"https://api.github.com/repos/midwestmade4u-prog/youtube-autopost"
               f"/actions/workflows/{workflow_id}/runs?per_page=5")
        r = ureq.Request(url, headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
        })
        with ureq.urlopen(r, timeout=10) as resp:
            runs = json.loads(resp.read())["workflow_runs"]

        # Find runs after slot_start
        slot_utc = slot_start.replace(tzinfo=timezone.utc) if slot_start.tzinfo is None else slot_start
        recent = [
            run for run in runs
            if datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")) >= slot_utc
        ]

        if not recent:
            return "no_runs_found"

        last = recent[0]
        # The API returns "conclusion": null -- key present, value null -- while
        # a run is still going, so dict.get()'s default never fired and this
        # produced the bogus "unknown:None" diagnosis. Check status instead.
        status     = last.get("status")
        conclusion = last.get("conclusion")
        logs_url   = last.get("html_url", "https://github.com/midwestmade4u-prog/youtube-autopost/actions")

        if status in ("queued", "in_progress") or conclusion is None:
            return f"still_running|{logs_url}"

        if conclusion == "failure":
            return f"workflow_failed|{logs_url}"
        elif conclusion == "success":
            # Success but no YT video in the slot window -- could be the
            # classic continue-on-error token failure, OR a benign burst-guard
            # skip (channel already met today's post cap earlier in the day).
            # Check the post log before concluding it's a real token issue.
            if _channel_posted_today(ch_key):
                return f"burst_guard_skip|{logs_url}"
            if _run_had_no_video_produced(last["id"], gh_token):
                return f"content_skip|{logs_url}"
            return f"token_issue|{logs_url}"
        else:
            return f"unknown:{conclusion}|{logs_url}"

    except Exception as e:
        return f"diagnosis_error:{e}"


# ── Retry trigger ─────────────────────────────────────────────────────────────
def trigger_retry(workflow_id: str, gh_token: str) -> bool:
    try:
        data = json.dumps({"ref": "main"}).encode()
        url  = (f"https://api.github.com/repos/midwestmade4u-prog/youtube-autopost"
                f"/actions/workflows/{workflow_id}/dispatches")
        r = ureq.Request(url, data=data, headers={
            "Authorization":  f"Bearer {gh_token}",
            "Accept":         "application/vnd.github+json",
            "Content-Type":   "application/json",
        }, method="POST")
        with ureq.urlopen(r, timeout=10) as resp:
            ok = resp.status == 204
            print(f"  {'✅' if ok else '❌'} Retry trigger: HTTP {resp.status}")
            return ok
    except Exception as e:
        print(f"  ❌ Retry trigger failed: {e}")
        return False


# ── Alert email ───────────────────────────────────────────────────────────────
def send_alert(ch_key: str, cfg: dict, diagnosis: str, post_type: str, gmail_pwd: str) -> None:
    label     = cfg["label"]
    color     = cfg["color"]
    token_nm  = cfg["token_name"]
    refresh   = cfg["refresh_script"]
    workflow  = cfg[f"workflow_{post_type}"]
    ts        = datetime.now(ZoneInfo("America/Chicago")).strftime("%b %d, %Y at %I:%M %p CT")

    diag_type = diagnosis.split("|")[0]
    logs_url  = diagnosis.split("|")[1] if "|" in diagnosis else \
                "https://github.com/midwestmade4u-prog/youtube-autopost/actions"

    if diag_type == "token_issue":
        action_html = f"""
        <div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px;margin:12px 0;">
          <strong>🔑 Likely cause: YouTube token expired</strong>
          <p>The workflow reported success but no video appeared — this is the classic
          <code>continue-on-error</code> token failure pattern.</p>
          <p><strong>Run these commands in Terminal:</strong></p>
          <pre style="background:#f8f9fa;padding:8px;border-radius:4px;">
cd "/Users/mattwisse/Documents/Claude/Projects/Youtube Channels Project"
python3 {refresh}
# Complete browser auth → wait for ✅
pbcopy &lt; {cfg['token_file']}</pre>
          <p>Then: <a href="https://github.com/midwestmade4u-prog/youtube-autopost/settings/secrets/actions">
          GitHub Secrets</a> → <strong>{token_nm}</strong> → Update → paste full JSON → Save</p>
          <p>Then: <a href="https://github.com/midwestmade4u-prog/youtube-autopost/actions/workflows/{workflow}">
          Re-trigger {label} {post_type} workflow</a></p>
        </div>"""
    elif diag_type == "burst_guard_skip":
        action_html = f"""
        <div style="background:#d4edda;border-left:4px solid #28a745;padding:12px;margin:12px 0;">
          <strong>✅ Not a failure — burst guard skip</strong>
          <p>{label} already posted earlier today; today's posting cap was already met, so
          this slot's run intentionally skipped. No action needed.</p>
        </div>"""
    elif diag_type == "content_skip":
        action_html = f"""
<div style="background:#d4edda;border-left:4px solid #28a745;padding:12px;margin:12px 0;">
<strong>✅ Not a token issue — content generation skip</strong>
<p>{label}'s script generator couldn't produce a script that passed the length
validator for this slot (the primary AND fallback topic both failed word-count
validation after 3 retries each), so the run correctly skipped without ever
rendering a video. No video file was created, so this has nothing to do with
the YouTube token.</p>
<p>This should self-resolve on the channel's next scheduled slot with a fresh
topic. No action needed unless it repeats for several slots in a row.</p>
</div>"""
    elif diag_type == "workflow_failed":
        action_html = f"""
        <div style="background:#f8d7da;border-left:4px solid #dc3545;padding:12px;margin:12px 0;">
          <strong>❌ Workflow failed outright (not a token issue)</strong>
          <p>Check the logs to see what went wrong:</p>
          <p><a href="{logs_url}">View failed run logs</a></p>
        </div>"""
    elif diag_type == "no_runs_found":
        action_html = f"""
        <div style="background:#f8d7da;border-left:4px solid #dc3545;padding:12px;margin:12px 0;">
          <strong>❌ No workflow runs found after the posting slot</strong>
          <p>The cron job may not have fired. Check
          <a href="https://github.com/midwestmade4u-prog/youtube-autopost/actions">Actions tab</a>
          and manually trigger the workflow.</p>
        </div>"""
    else:
        action_html = f"""
        <div style="background:#f8d7da;border-left:4px solid #dc3545;padding:12px;margin:12px 0;">
          <strong>⚠️  Unknown failure — {diag_type}</strong>
          <p><a href="{logs_url}">Check Actions logs</a></p>
        </div>"""

    subject = f"🚨 [{label}] {post_type.title()} missed — action needed ({ts})"
    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;color:#333;">
  <h2 style="color:{color};margin-bottom:4px;">🚨 {label} — {post_type.title()} Post Missed</h2>
  <p style="color:#666;margin-top:0;">{ts}</p>
  <hr>
  <p>The watchdog confirmed via YouTube API that <strong>no video posted</strong>
  in the expected window. An automatic retry was triggered — it also failed.</p>
  {action_html}
  <p style="color:#aaa;font-size:11px;margin-top:24px;">
    Unified Watchdog · midwestmade4u-prog/youtube-autopost
  </p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = "wisseinc@gmail.com"
    msg["To"]      = "wisseinc@gmail.com"
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login("wisseinc@gmail.com", gmail_pwd)
            s.sendmail("wisseinc@gmail.com", "wisseinc@gmail.com", msg.as_string())
        print(f"  ✅ Alert email sent → wisseinc@gmail.com")
    except Exception as e:
        print(f"  ❌ Email failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel",    required=True, choices=list(CHANNELS))
    parser.add_argument("--slot-utc",   required=True, type=int,
                        help="UTC hour of the posting slot (0–23)")
    parser.add_argument("--post-type",  required=True, choices=["shorts", "longform"])
    parser.add_argument("--check-type", required=True, choices=["retry", "alert"],
                        help="retry = T+90min check; alert = T+120min check")
    parser.add_argument("--slot-day",   type=int, default=None,
                        help="Day of week (0=Sun) for longform — omit for daily slots")
    args = parser.parse_args()

    cfg        = CHANNELS[args.channel]
    gh_token   = os.environ.get("GH_PAT", "")
    gmail_pwd  = os.environ.get("GMAIL_APP_PASSWORD", "")
    workflow   = cfg[f"workflow_{args.post_type}"]

    # Compute slot_start: most recent occurrence of this UTC hour
    now = datetime.utcnow()
    slot_start = now.replace(hour=args.slot_utc, minute=0, second=0, microsecond=0)
    if slot_start > now:
        slot_start -= timedelta(days=1)

    # For longform: ensure we're on the right weekday
    if args.slot_day is not None:
        # Walk back until we hit the right weekday
        for _ in range(7):
            if slot_start.weekday() == (args.slot_day % 7 if args.slot_day != 0 else 6):
                # Python weekday: Mon=0 … Sun=6; our input: 0=Sun … 6=Sat
                break
            slot_start -= timedelta(days=1)
        # Re-check: if slot_start is more than 3 days ago, we're probably not near a posting window
        if (now - slot_start).total_seconds() > 6 * 3600:
            print(f"⏰ Not near a {args.post_type} posting window for {cfg['label']} — skipping")
            sys.exit(0)

    # ── Phantom-slot guard ───────────────────────────────────────────────────
    # Skip slots the autopost workflow isn't actually scheduled for. Empty set
    # means "couldn't parse" -> fall through and behave as before.
    real_hours = _scheduled_slot_hours(workflow)
    if real_hours and args.slot_utc not in real_hours:
        print(f"⏭️  {cfg['label']} {args.post_type}: slot {args.slot_utc:02d}:00 UTC is not "
              f"scheduled in {workflow} (real slots: "
              f"{', '.join(f'{h:02d}:00' for h in sorted(real_hours))} UTC).")
        print(f"    Nothing can have run for it — skipping instead of alerting.")
        sys.exit(0)

    elapsed_min = (now - slot_start).total_seconds() / 60
    print(f"╔═════════════════════════════════════════════════════")
    print(f"║  Unified Watchdog — {cfg['label']} {args.post_type.title()}")
    print(f"║  Slot: {slot_start.strftime('%Y-%m-%d %H:%M')} UTC  |  T+{elapsed_min:.0f}min  |  Mode: {args.check_type}")
    print(f"╚═════════════════════════════════════════════════════")

    # ── Check YouTube directly ────────────────────────────────────────────────
    found, url = check_youtube_for_recent_video(cfg["channel_id"], cfg["token_file"], slot_start, args.post_type)

    if found:
        print(f"✅ {cfg['label']} {args.post_type} confirmed posted — all good")
        sys.exit(0)

    # ── Not found ─────────────────────────────────────────────────────────────
    if args.check_type == "retry":
        # Don't dispatch a duplicate while the scheduled run is still working.
        if gh_token:
            running, run_url = _run_still_in_progress(workflow, slot_start, gh_token)
            if running:
                print(f"⏳ {cfg['label']} {args.post_type} run is still in progress "
                      f"— skipping retry to avoid a duplicate post. {run_url}")
                sys.exit(0)

        print(f"⚠️  No video found — triggering automatic retry of {workflow}")
        if gh_token:
            ok = trigger_retry(workflow, gh_token)
            if ok:
                print(f"✅ Retry triggered — next watchdog check in ~30 min will verify")
            else:
                print(f"❌ Retry trigger failed — alert will fire at next check")
        else:
            print("⚠️  No GH_PAT — cannot trigger retry")

    elif args.check_type == "alert":
        # Diagnose before alerting
        print(f"🚨 Still no video after retry — diagnosing and alerting")
        diagnosis = diagnose_failure(workflow, slot_start, gh_token, args.channel) if gh_token else "no_gh_token"
        print(f"  Diagnosis: {diagnosis}")

        diag_type = diagnosis.split("|")[0]
        if diag_type == "still_running":
            print(f"⏳ Not a failure — {cfg['label']} {args.post_type} run is still in "
                  f"progress. Suppressing alert.")
            sys.exit(0)

        if diag_type == "burst_guard_skip":
            print(f"✅ Not a real failure — {cfg['label']} already posted earlier today (burst guard). Suppressing alert.")
            sys.exit(0)

        if diag_type == "content_skip":
            print(f"✅ Not a real failure — {cfg['label']} content generator skipped (no video produced this slot). Suppressing alert.")
            sys.exit(0)

        if gmail_pwd:
            send_alert(args.channel, cfg, diagnosis, args.post_type, gmail_pwd)
        else:
            print("⚠️  No GMAIL_APP_PASSWORD — skipping email")


if __name__ == "__main__":
    main()
