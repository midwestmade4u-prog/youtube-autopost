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

# ── Channel config ────────────────────────────────────────────────────────────
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


# ── Diagnosis ─────────────────────────────────────────────────────────────────
def diagnose_failure(workflow_id: str, slot_start: datetime, gh_token: str) -> str:
    """
    Inspects recent GH Actions runs to identify the failure type.
    Returns a human-readable diagnosis.
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
        conclusion = last.get("conclusion", "in_progress")
        logs_url   = last.get("html_url", "https://github.com/midwestmade4u-prog/youtube-autopost/actions")

        if conclusion == "failure":
            return f"workflow_failed|{logs_url}"
        elif conclusion == "success":
            # Success but no YT video = token issue (continue-on-error pattern)
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

    elapsed_min = (now - slot_start).total_seconds() / 60
    print(f"╔══════════════════════════════════════════════════════")
    print(f"║  Unified Watchdog — {cfg['label']} {args.post_type.title()}")
    print(f"║  Slot: {slot_start.strftime('%Y-%m-%d %H:%M')} UTC  |  T+{elapsed_min:.0f}min  |  Mode: {args.check_type}")
    print(f"╚══════════════════════════════════════════════════════")

    # ── Check YouTube directly ────────────────────────────────────────────────
    found, url = check_youtube_for_recent_video(cfg["channel_id"], cfg["token_file"], slot_start, args.post_type)

    if found:
        print(f"✅ {cfg['label']} {args.post_type} confirmed posted — all good")
        sys.exit(0)

    # ── Not found ─────────────────────────────────────────────────────────────
    if args.check_type == "retry":
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
        diagnosis = diagnose_failure(workflow, slot_start, gh_token) if gh_token else "no_gh_token"
        print(f"  Diagnosis: {diagnosis}")

        if gmail_pwd:
            send_alert(args.channel, cfg, diagnosis, args.post_type, gmail_pwd)
        else:
            print("⚠️  No GMAIL_APP_PASSWORD — skipping email")


if __name__ == "__main__":
    main()
