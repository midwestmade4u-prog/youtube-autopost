#!/usr/bin/env python3
"""
check_shorts_retention.py -- Pull average view percentage (retention) for each
channel's recent Shorts via the YouTube Analytics API, and flag anything below
YouTube's current "good retention" bar for Shorts (~70%+ as of the Jul 5 2026
research digest -- see SCHEDULE.md / project_research_digest_jul5 memory).

REQUIRES: youtube_token_{channel}.json must have been generated with the
yt-analytics.readonly scope (added Jul 5 2026 to video_app.py / refresh_token_*.py).
If a token predates that change, re-run the OAuth flow for that channel first
(delete the token file, then hit /youtube-connect?channel=X in video_app.py,
or run refresh_token_bsg.py / refresh_token_mz.py), then re-paste into the
matching GH secret (YT_TOKEN_TMF / YT_TOKEN_BSG / YT_TOKEN_MZ).

Usage:
    python3 check_shorts_retention.py            # all 3 channels, last 14 days
    python3 check_shorts_retention.py --days 30   # wider window
    python3 check_shorts_retention.py --channel tmf
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent

RETENTION_BAR = 70.0  # percent -- Jul 5 2026 research digest finding

CHANNELS = {
    "tmf": {"label": "The Mind Files",      "channel_id": "UC0O6KbbHKW4_a7d9epNo93A", "token_file": BASE_DIR / "youtube_token_tmf.json"},
    "bsg": {"label": "Bible Story Garden",  "channel_id": "UCcyBf84Mc-evMSYZlqh3zVA", "token_file": BASE_DIR / "youtube_token_bsg.json"},
    "mz":  {"label": "Minute Zero",         "channel_id": "UCMVhjR4HetJctXeYkuPgg6w", "token_file": BASE_DIR / "youtube_token_mz.json"},
}

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def _get_credentials(token_file: Path):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    if not token_file.exists():
        raise FileNotFoundError(f"{token_file} not found -- run OAuth for this channel first.")
    creds = Credentials.from_authorized_user_info(json.loads(token_file.read_text()), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.write_text(creds.to_json())
    if "yt-analytics.readonly" not in " ".join(creds.scopes or []):
        raise PermissionError(
            "Token doesn't have yt-analytics.readonly scope yet -- re-run OAuth "
            "for this channel (see script docstring) before this will work."
        )
    return creds


def _recent_shorts(svc_data, channel_id: str, days: int) -> list[dict]:
    """Return [{video_id, title}] for Shorts (<=180s) published in the last N days."""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    search_resp = svc_data.search().list(
        part="id,snippet", channelId=channel_id, type="video",
        publishedAfter=since, maxResults=50, order="date",
    ).execute()
    video_ids = [i["id"]["videoId"] for i in search_resp.get("items", []) if i.get("id", {}).get("videoId")]
    if not video_ids:
        return []
    stats_resp = svc_data.videos().list(part="contentDetails,snippet", id=",".join(video_ids)).execute()
    shorts = []
    for v in stats_resp.get("items", []):
        duration = v.get("contentDetails", {}).get("duration", "PT99M")
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        h = int(m.group(1) or 0) if m else 0
        mi = int(m.group(2) or 0) if m else 99
        s = int(m.group(3) or 0) if m else 0
        if h * 3600 + mi * 60 + s <= 180:
            shorts.append({"video_id": v["id"], "title": v["snippet"]["title"]})
    return shorts


def check_channel(key: str, days: int) -> None:
    from googleapiclient.discovery import build

    cfg = CHANNELS[key]
    print(f"\n=== {cfg['label']} ({key.upper()}) -- last {days}d ===")
    try:
        creds = _get_credentials(cfg["token_file"])
    except Exception as e:
        print(f"  SKIPPED: {e}")
        return

    svc_data = build("youtube", "v3", credentials=creds)
    svc_analytics = build("youtubeAnalytics", "v2", credentials=creds)

    shorts = _recent_shorts(svc_data, cfg["channel_id"], days)
    if not shorts:
        print("  No Shorts found in this window.")
        return

    id_to_title = {s["video_id"]: s["title"] for s in shorts}
    video_ids = list(id_to_title.keys())

    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    resp = svc_analytics.reports().query(
        ids="channel==MINE",
        startDate=start_date,
        endDate=end_date,
        metrics="views,averageViewPercentage,averageViewDuration",
        dimensions="video",
        filters="video==" + ",".join(video_ids),
        sort="-views",
    ).execute()

    rows = resp.get("rows", [])
    if not rows:
        print("  No analytics rows returned (videos may be too new for data).")
        return

    below_bar = 0
    for vid, views, avg_pct, avg_dur in rows:
        title = id_to_title.get(vid, vid)[:55]
        flag = "  <-- BELOW 70% BAR" if avg_pct < RETENTION_BAR else ""
        if flag:
            below_bar += 1
        print(f"  {avg_pct:5.1f}%  {int(views):>5} views  {title}{flag}")

    channel_avg = sum(r[2] for r in rows) / len(rows)
    print(f"  --- channel avg: {channel_avg:.1f}% across {len(rows)} Shorts ({below_bar} below {RETENTION_BAR}% bar) ---")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--channel", choices=list(CHANNELS.keys()), default=None)
    args = parser.parse_args()

    keys = [args.channel] if args.channel else list(CHANNELS.keys())
    for key in keys:
        check_channel(key, args.days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
