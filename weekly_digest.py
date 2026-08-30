#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  weekly_digest.py — Sunday morning performance digest        ║
╚══════════════════════════════════════════════════════════════╝

Runs Sunday at 3 AM CT via GitHub Actions (weekly-digest.yml).

For each channel:
  1. Pulls last 7 days of video stats (YouTube Data API)
  2. Pulls all-time top 10 videos for benchmarking
  3. Compares this week vs last week
  4. Tracks monetization threshold progress
  5. Calls Claude to generate bullet-point suggestions
  6. Writes formatted report to Google Sheets "Weekly Digest" tab
  7. Sends exec summary email with direct Sheet link

Required env vars (GitHub Secrets):
  GOOGLE_SHEETS_KEY     — service account JSON
  ANTHROPIC_API_KEY     — for analysis (Haiku — cheap)
  GMAIL_APP_PASSWORD    — app password for wisseinc@gmail.com
  YT_TOKEN_TMF / YT_TOKEN_BSG / YT_TOKEN_MZ
"""

from __future__ import annotations

import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

CT              = ZoneInfo("America/Chicago")
SPREADSHEET_ID  = "1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI"
SHEETS_TAB      = "Weekly Digest"
ALERT_EMAIL     = "wisseinc@gmail.com"
FROM_EMAIL      = "wisseinc@gmail.com"
SHEETS_URL      = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid=0"

# YouTube monetization thresholds (per-path)
# Standard YPP (ad revenue):   1,000 subs + 4,000 watch hours OR 1,000 subs + 10M Shorts views
# Tier-1 YPP (fan funding):      500 subs + 3,000 watch hours OR  500 subs + 3M Shorts views
YT_SUB_THRESHOLD_FULL         = 1000
YT_SUB_THRESHOLD_TIER1        = 500
YT_WATCH_HOURS_THRESHOLD_FULL = 4000
YT_WATCH_HOURS_THRESHOLD_T1   = 3000
YT_SHORTS_VIEWS_FULL          = 10_000_000
YT_SHORTS_VIEWS_TIER1         = 3_000_000

CHANNELS = {
    "tmf": {
        "label":          "The Mind Files",
        "channel_id":     "UC0O6KbbHKW4_a7d9epNo93A",
        "token_env":      "YT_TOKEN_TMF",
        "token_file":     "youtube_token_tmf.json",
        "expected_posts": 3,
        "niche":          "dark psychology / human behavior Shorts",
        "title_rule":     "Must start with 'Why You' or 'Why Your'",
        "top_video_note": "Best titles are 'Why You [observable behavior]' — 400-1300 views",
        "sub_target":     YT_SUB_THRESHOLD_FULL,   # targeting full YPP
        "wh_target":      YT_WATCH_HOURS_THRESHOLD_FULL,
    },
    "bsg": {
        "label":          "Bible Story Garden",
        "channel_id":     "UCcyBf84Mc-evMSYZlqh3zVA",
        "token_env":      "YT_TOKEN_BSG",
        "token_file":     "youtube_token_bsg.json",
        "expected_posts": 2,
        "niche":          "Bible stories for families / kids Shorts",
        "title_rule":     "Story-focused, no verse recitation",
        "top_video_note": "45-55s stories with payoff thumbnails perform best",
        "sub_target":     YT_SUB_THRESHOLD_FULL,
        "wh_target":      YT_WATCH_HOURS_THRESHOLD_FULL,
    },
    "mz": {
        "label":          "Minute Zero",
        "channel_id":     "UCMVhjR4HetJctXeYkuPgg6w",
        "token_env":      "YT_TOKEN_MZ",
        "token_file":     "youtube_token_mz.json",
        "expected_posts": 2,
        "niche":          "Business failures / fraud Shorts",
        "title_rule":     "Lead with dollar figure, date, or punch superlative in first 3 words",
        "top_video_note": "US stories outperform foreign; recovery/survival narratives outperform pure destruction",
        "sub_target":     YT_SUB_THRESHOLD_TIER1,   # Tier-1 first, then full YPP
        "wh_target":      YT_WATCH_HOURS_THRESHOLD_T1,
    },
}


# ─── YouTube Data API ─────────────────────────────────────────────────────────

def get_yt_service(token_file: str):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(json.loads(open(token_file).read()))
    return build("youtube", "v3", credentials=creds)


def get_channel_stats(svc, channel_id: str) -> dict:
    """Pull subscriber count and total view/watch stats from channel."""
    try:
        resp = svc.channels().list(
            part="statistics,snippet",
            id=channel_id,
        ).execute()
        item = (resp.get("items") or [{}])[0]
        stats = item.get("statistics", {})
        return {
            "subscribers":   int(stats.get("subscriberCount", 0)),
            "total_views":   int(stats.get("viewCount", 0)),
            "video_count":   int(stats.get("videoCount", 0)),
            "title":         item.get("snippet", {}).get("title", ""),
        }
    except Exception as e:
        return {"error": str(e)[:80]}


def get_videos_in_window(svc, channel_id: str, days_ago_start: int, days_ago_end: int = 0) -> list[dict]:
    """Get videos published between days_ago_start and days_ago_end, with stats."""
    try:
        now = datetime.now(timezone.utc)
        published_after  = (now - timedelta(days=days_ago_start)).strftime("%Y-%m-%dT%H:%M:%SZ")
        published_before = (now - timedelta(days=days_ago_end)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Search for videos in window
        search_resp = svc.search().list(
            part="snippet",
            channelId=channel_id,
            publishedAfter=published_after,
            publishedBefore=published_before,
            type="video",
            maxResults=50,
            order="date",
        ).execute()

        video_ids = [i["id"]["videoId"] for i in search_resp.get("items", [])]
        if not video_ids:
            return []

        # Get stats for each video (include contentDetails for duration → watch hours estimate)
        stats_resp = svc.videos().list(
            part="statistics,snippet,contentDetails",
            id=",".join(video_ids),
        ).execute()

        results = []
        for item in stats_resp.get("items", []):
            stats = item.get("statistics", {})
            duration = item.get("contentDetails", {}).get("duration", "PT0S")
            thumb_map = item["snippet"].get("thumbnails", {})
            thumb_url = (
                thumb_map.get("maxres") or
                thumb_map.get("high") or
                thumb_map.get("medium") or {}
            ).get("url", "")
            results.append({
                "video_id":      item["id"],
                "title":         item["snippet"]["title"],
                "published":     item["snippet"]["publishedAt"],
                "views":         int(stats.get("viewCount", 0)),
                "likes":         int(stats.get("likeCount", 0)),
                "comments":      int(stats.get("commentCount", 0)),
                "duration":      duration,
                "url":           f"https://youtu.be/{item['id']}",
                "thumbnail_url": thumb_url,
            })
        results.sort(key=lambda x: x["views"], reverse=True)
        return results
    except Exception as e:
        return [{"error": str(e)[:80]}]


def get_top_videos_alltime(svc, channel_id: str, limit: int = 10) -> list[dict]:
    """Get all-time top videos by view count."""
    try:
        resp = svc.search().list(
            part="snippet",
            channelId=channel_id,
            type="video",
            maxResults=50,
            order="viewCount",
        ).execute()

        video_ids = [i["id"]["videoId"] for i in resp.get("items", [])]
        if not video_ids:
            return []

        stats_resp = svc.videos().list(
            part="statistics,snippet",
            id=",".join(video_ids[:limit]),
        ).execute()

        results = []
        for item in stats_resp.get("items", []):
            stats = item.get("statistics", {})
            results.append({
                "video_id":  item["id"],
                "title":     item["snippet"]["title"],
                "published": item["snippet"]["publishedAt"][:10],
                "views":     int(stats.get("viewCount", 0)),
                "url":       f"https://youtu.be/{item['id']}",
            })
        results.sort(key=lambda x: x["views"], reverse=True)
        return results[:limit]
    except Exception as e:
        return [{"error": str(e)[:80]}]


# ─── Thumbnail duplicate detection ───────────────────────────────────────────

def check_thumbnail_diversity(videos: list[dict], label: str) -> dict | None:
    """Download up to 8 recent thumbnails, hash with MD5.
    Returns an alert dict if 3+ share the same hash (identical image = broken pipeline).
    Returns None if thumbnails look healthy.
    """
    import urllib.request
    import hashlib

    recent = [v for v in videos if "error" not in v and v.get("thumbnail_url")][:8]
    if len(recent) < 3:
        return None

    hashes: dict[str, list[dict]] = {}
    for v in recent:
        try:
            req = urllib.request.Request(
                v["thumbnail_url"],
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read()
            h = hashlib.md5(data).hexdigest()
            if h not in hashes:
                hashes[h] = []
            hashes[h].append({"title": v["title"], "video_url": v["url"]})
        except Exception:
            continue

    if not hashes:
        return None

    worst_hash, worst_videos = max(hashes.items(), key=lambda x: len(x[1]))
    if len(worst_videos) >= 3:
        return {
            "channel":         label,
            "duplicate_count": len(worst_videos),
            "total_checked":   len(recent),
            "videos":          worst_videos[:5],  # show up to 5 examples
        }
    return None


# ─── Claude analysis ──────────────────────────────────────────────────────────

def analyze_with_claude(channel_info: dict, this_week: list[dict], last_week: list[dict],
                        top_alltime: list[dict], channel_stats: dict) -> str:
    """Generate bullet-point suggestions via Claude Haiku (cheapest model)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return "• (Analysis unavailable — ANTHROPIC_API_KEY not set)"

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        this_week_summary = [{"title": v["title"], "views": v["views"]} for v in this_week[:10]]
        last_week_summary = [{"title": v["title"], "views": v["views"]} for v in last_week[:10]]
        top_summary       = [{"title": v["title"], "views": v["views"], "published": v["published"]} for v in top_alltime[:5]]

        this_views  = sum(v["views"] for v in this_week if "error" not in v)
        last_views  = sum(v["views"] for v in last_week if "error" not in v)
        delta_pct   = ((this_views - last_views) / max(last_views, 1)) * 100

        import subprocess as _sp
        try:
            _commits = _sp.run(["git", "log", "--oneline", "--since=7.days"],
                               capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            _commits = ""
        _commits = _commits or "(no commits in the last 7 days)"

        _tw = sorted(v["views"] for v in this_week if "error" not in v)
        _lw = sorted(v["views"] for v in last_week if "error" not in v)
        _med = lambda a: (a[len(a)//2] if len(a) % 2 else (a[len(a)//2 - 1] + a[len(a)//2]) / 2) if a else 0

        prompt = f"""You are a YouTube performance REPORTER. Report what the numbers show. Do not invent explanations.

WHAT YOU CANNOT KNOW FROM THIS DATA:
You are given titles and view counts only. You do NOT have retention, watch time,
impressions, click-through rate, traffic source, or subscriber counts per video.
You therefore CANNOT know why any video performed as it did. Never claim a title
pattern, topic, or format caused a result. On Aug 23 2026 this digest told the
creator to abandon "The Meeting That..." titles; that exact pattern had produced
the channel's best video of the month (1,020 views, 62% retention). The digest
could not see retention and guessed. Do not guess.

CODE CHANGED IN THE LAST 7 DAYS (check this before attributing anything to content):
{_commits}

COHORT AGE -- do not attribute this to content: "this week" is videos 0-7 days old,
"last week" is videos 7-14 days old. The newer set has had half the time to gather
views, so a negative delta is the DEFAULT state of this comparison, not a signal.
Only call out a decline if it is far larger than that bias would explain.

MEDIANS (use these for "typical video", not the totals):
  This week median: {_med(_tw):,.0f} views across {len(_tw)} videos
  Last week median: {_med(_lw):,.0f} views across {len(_lw)} videos
A weekly total can double on one lucky video while the typical video is unchanged.

Analyze this channel's weekly performance.

Channel: {channel_info['label']}
Niche: {channel_info['niche']}
Title rule: {channel_info['title_rule']}
Top video insight: {channel_info['top_video_note']}

THIS WEEK ({len(this_week)} videos, {this_views:,} total views, {delta_pct:+.1f}% vs last week):
{json.dumps(this_week_summary, indent=2)}

LAST WEEK ({len(last_week)} videos, {last_views:,} total views):
{json.dumps(last_week_summary, indent=2)}

ALL-TIME TOP 5 VIDEOS (benchmark — emulate these):
{json.dumps(top_summary, indent=2)}

Channel totals: {channel_stats.get('subscribers', '?'):,} subscribers, {channel_stats.get('total_views', '?'):,} total views

Respond with EXACTLY 3-5 bullet points, in this order of preference:

1. OBSERVATIONS the data actually supports. State absolute counts, never a bare
   percentage. "Median fell 41 -> 12 views (n=7 vs n=6)" not "views down 70%".
2. If a code commit above could plausibly explain a change, say so and stop there.
   A pipeline change is a far likelier cause than a title choice.
3. QUESTIONS worth checking in Studio, phrased as questions.
4. Only if a pattern holds across MANY videos, a tentative suggestion, explicitly
   flagged as a guess.

Hard rules:
- Never assert that a title or topic caused a view count. You cannot see retention.
- Never recommend abandoning a format on fewer than 5 videos of evidence.
- If nothing meaningful changed, say "no significant change this week" and stop.
- Small numbers are noise. Under ~30 views a swing means nothing.
Be direct and calibrated. The creator acts on this Sunday morning."""

        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return r.content[0].text.strip()
    except Exception as e:
        return f"• (Analysis failed: {e})"


# ─── Google Sheets ────────────────────────────────────────────────────────────

def write_to_sheets(all_channel_data: list[dict], week_label: str) -> None:
    """Write the weekly digest to Google Sheets."""
    creds_json = os.environ.get("GOOGLE_SHEETS_KEY", "")
    if not creds_json:
        print("  ⚠️  GOOGLE_SHEETS_KEY not set — skipping Sheets write")
        return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build as gcp_build
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        svc = gcp_build("sheets", "v4", credentials=creds)

        rows = [[f"=== WEEKLY DIGEST: {week_label} ==="]]
        rows.append([""])

        for ch in all_channel_data:
            rows.append([f"── {ch['label']} ──────────────────────────"])
            rows.append(["Metric", "This Week", "Last Week", "Change"])
            rows.append(["Videos posted", ch["this_count"], ch["last_count"], f"{ch['this_count'] - ch['last_count']:+d}"])
            rows.append(["Total views", ch["this_views"], ch["last_views"], f"{ch['this_views'] - ch['last_views']:+,}"])
            rows.append(["Avg views/video", ch["this_avg"], ch["last_avg"], f"{ch['this_avg'] - ch['last_avg']:+.0f}"])
            rows.append(["Subscribers", ch["subscribers"], "", ""])
            rows.append([""])
            rows.append(["Top video this week:", ch["top_this_week"], "", ""])
            rows.append(["All-time #1:", ch["alltime_top"], "", ""])
            rows.append([""])
            rows.append(["SUGGESTIONS:"])
            for line in ch["suggestions"].split("\n"):
                if line.strip():
                    rows.append([line.strip()])
            rows.append([""])
            rows.append(["Monetization:", ch["monetization_status"]])
            rows.append([""])
            rows.append([""])

        svc.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEETS_TAB}!A:E",
            valueInputOption="USER_ENTERED",
            body={"values": rows}
        ).execute()
        print(f"  📊 Weekly digest written to Sheets")
    except Exception as e:
        print(f"  ⚠️  Sheets write failed: {e}")


# ─── Email ────────────────────────────────────────────────────────────────────

def send_digest_email(all_channel_data: list[dict], week_label: str) -> bool:
    """Send Sunday morning exec summary email. Returns True only if it was sent.

    Aug 30 2026: this returned None and swallowed every exception with a print.
    Combined with `return 0` in main() and `continue-on-error: true` on the
    workflow step, a digest that failed to send looked EXACTLY like one that
    succeeded -- green check, no email, no alert. Three swallow layers on the
    one job whose entire output is an email. The Aug 24 "make silent failures
    loud" pass never reached this file.
    """
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not password:
        print("::error::GMAIL_APP_PASSWORD not set — the weekly digest CANNOT email.")
        return False

    # Build plain text
    lines = [f"YouTube Weekly Digest — {week_label}", "=" * 50, "",
             "* Read the week-over-week deltas with care: 'this week' is videos 0-7 days",
             "  old and 'last week' is videos 7-14 days old, so the newer cohort has had",
             "  half as long to accumulate views and will look worse even when nothing",
             "  changed. The bias is the same every week, so the TREND in the delta is",
             "  meaningful; a single week's number is not.",
             ""]
    for ch in all_channel_data:
        delta = ch["this_views"] - ch["last_views"]
        arrow = "📈" if delta >= 0 else "📉"
        lines.append(f"{arrow} {ch['label']}")
        lines.append(f"   {ch['this_count']} videos | {ch['this_views']:,} views ({delta:+,} vs last week*)")
        lines.append(f"   Avg: {ch['this_avg']:.0f} views/video | Subs: {ch['subscribers']:,}")
        lines.append(f"   {ch['monetization_status']}")
        lines.append("")
        lines.append("   Suggestions:")
        for line in ch["suggestions"].split("\n"):
            if line.strip():
                lines.append(f"   {line.strip()}")
        lines.append("")
    lines.append(f"Full report: {SHEETS_URL}")
    body_text = "\n".join(lines)

    # Build thumbnail alert blocks (plain text)
    thumb_alert_lines: list[str] = []
    for ch in all_channel_data:
        alert = ch.get("thumb_alert")
        if alert:
            thumb_alert_lines.append(
                f"⚠️  DUPLICATE THUMBNAILS — {alert['channel']}: "
                f"{alert['duplicate_count']}/{alert['total_checked']} videos share the same image."
            )
            thumb_alert_lines.append("   Likely cause: FAL AI credits exhausted (check fal.ai/dashboard)")
            for v in alert["videos"][:3]:
                thumb_alert_lines.append(f"   • {v['title'][:60]}  {v['video_url']}")
    if thumb_alert_lines:
        lines.insert(3, "\n".join(["🚨 THUMBNAIL ALERTS", "─" * 40] + thumb_alert_lines + [""]))

    # Build HTML
    # Thumbnail alert HTML block
    thumb_alert_html = ""
    for ch in all_channel_data:
        alert = ch.get("thumb_alert")
        if alert:
            video_list_html = "".join(
                f'<li style="margin-bottom:4px"><a href="{v["video_url"]}" style="color:#c0392b">'
                f'{v["title"][:70]}</a></li>'
                for v in alert["videos"]
            )
            thumb_alert_html += f"""
        <div style="background:#fff0f0;border:2px solid #e74c3c;border-radius:6px;
                    padding:16px;margin-bottom:12px">
          <h4 style="margin:0 0 8px 0;color:#c0392b">
            ⚠️ DUPLICATE THUMBNAILS — {alert["channel"]}
          </h4>
          <p style="margin:0 0 8px 0;font-size:14px">
            <b>{alert["duplicate_count"]}/{alert["total_checked"]}</b> recent videos share an
            <b>identical thumbnail image</b>. This tanks CTR and signals a broken visual pipeline.
          </p>
          <p style="margin:0 0 6px 0;font-size:13px"><b>Most likely causes:</b></p>
          <ul style="font-size:13px;margin:0 0 8px 0;padding-left:20px">
            <li><b>FAL AI credits ran out</b> — check
              <a href="https://fal.ai/dashboard" style="color:#2980b9">fal.ai/dashboard</a>
              and top up if balance is near zero</li>
            <li><b>Pollinations fallback seed collision</b> — identical seeds generate identical images;
              verify <code>video_app.py</code> topic-seed hashing is live</li>
          </ul>
          <p style="margin:0 0 4px 0;font-size:13px"><b>Affected videos:</b></p>
          <ul style="font-size:13px;margin:0;padding-left:20px">{video_list_html}</ul>
        </div>"""

    thumbnail_alerts_block = ""
    if thumb_alert_html:
        thumbnail_alerts_block = f"""
        <div style="margin-bottom:24px">
          <h3 style="color:#c0392b;margin:0 0 10px 0">🚨 Thumbnail Alerts</h3>
          {thumb_alert_html}
        </div>"""

    channel_blocks = ""
    for ch in all_channel_data:
        delta = ch["this_views"] - ch["last_views"]
        arrow = "📈" if delta >= 0 else "📉"
        delta_color = "#27ae60" if delta >= 0 else "#c0392b"
        suggestion_html = "".join(
            f"<li>{line.lstrip('•- ').strip()}</li>"
            for line in ch["suggestions"].split("\n")
            if line.strip()
        )
        channel_blocks += f"""
        <div style="background:#f8f9fa;border-left:4px solid #2980b9;padding:16px;margin-bottom:20px;border-radius:4px">
          <h3 style="margin:0 0 8px 0">{arrow} {ch['label']}</h3>
          <table style="border-collapse:collapse;width:100%;font-size:14px">
            <tr>
              <td style="padding:4px 12px 4px 0"><b>Videos</b></td>
              <td>{ch['this_count']} <span style="color:#888">(was {ch['last_count']})</span></td>
              <td style="padding:4px 12px 4px 16px"><b>Views</b></td>
              <td>{ch['this_views']:,} <span style="color:{delta_color}">({delta:+,})</span></td>
            </tr>
            <tr>
              <td style="padding:4px 12px 4px 0"><b>Avg/video</b></td>
              <td>{ch['this_avg']:.0f}</td>
              <td style="padding:4px 12px 4px 16px"><b>Subscribers</b></td>
              <td>{ch['subscribers']:,}</td>
            </tr>
          </table>
          <p style="font-size:12px;color:#666;margin:8px 0 4px 0">{ch['monetization_status']}</p>
          <p style="margin:8px 0 4px 0"><b>Suggestions:</b></p>
          <ul style="margin:4px 0;padding-left:20px;font-size:14px">{suggestion_html}</ul>
        </div>
        """

    # Build monetization summary table
    mono_rows = ""
    for ch in all_channel_data:
        mono = ch.get("mono", {})
        if not mono:
            continue
        sub_pct   = mono.get("sub_pct", 0)
        wh_pct    = mono.get("wh_pct", 0)
        subs      = mono.get("subscribers", 0)
        sub_tgt   = mono.get("sub_target", 1000)
        est_wh    = mono.get("est_watch_hours", 0)
        wh_tgt    = mono.get("wh_target", 4000)
        eta       = mono.get("sub_eta", "?")
        bar_color = "#27ae60" if sub_pct >= 50 else "#e67e22" if sub_pct >= 20 else "#c0392b"
        mono_rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:bold">{ch['label']}</td>
          <td style="padding:8px 12px">
            <div style="background:#eee;border-radius:4px;height:10px;width:140px;display:inline-block;vertical-align:middle">
              <div style="background:{bar_color};width:{min(sub_pct,100)}%;height:100%;border-radius:4px"></div>
            </div>
            &nbsp;{subs:,}/{sub_tgt:,} ({sub_pct}%)
          </td>
          <td style="padding:8px 12px">
            <div style="background:#eee;border-radius:4px;height:10px;width:100px;display:inline-block;vertical-align:middle">
              <div style="background:#2980b9;width:{min(wh_pct,100)}%;height:100%;border-radius:4px"></div>
            </div>
            &nbsp;~{est_wh:.0f}/{wh_tgt:,} hrs ({wh_pct}%)
          </td>
          <td style="padding:8px 12px;color:#666;font-size:13px">{eta}</td>
        </tr>"""

    monetization_block = f"""
        <div style="background:#fff8e1;border:1px solid #f39c12;border-radius:6px;padding:16px;margin-bottom:24px">
          <h3 style="margin:0 0 12px 0;color:#e67e22">💰 Monetization Tracker</h3>
          <table style="border-collapse:collapse;width:100%;font-size:14px">
            <tr style="color:#888;font-size:12px">
              <th style="text-align:left;padding:4px 12px">Channel</th>
              <th style="text-align:left;padding:4px 12px">Subscribers</th>
              <th style="text-align:left;padding:4px 12px">Watch Hours</th>
              <th style="text-align:left;padding:4px 12px">ETA to subs goal</th>
            </tr>
            {mono_rows}
          </table>
          <p style="font-size:11px;color:#999;margin:10px 0 0 0">
            Watch hours estimated from view × duration × completion rate. Sub ETA based on this week's view pace.
            MZ targets Tier-1 (500 subs). TMF + BSG target full YPP (1,000 subs + 4,000 hrs).
          </p>
        </div>"""

    body_html = f"""
    <div style="font-family:sans-serif;max-width:620px;margin:0 auto;padding:16px">
      <h2 style="color:#2c3e50;border-bottom:2px solid #2980b9;padding-bottom:8px">
        📊 YouTube Weekly Digest — {week_label}
      </h2>
      {thumbnail_alerts_block}
      {monetization_block}
      {channel_blocks}
      <div style="text-align:center;margin-top:24px">
        <a href="{SHEETS_URL}"
           style="background:#2980b9;color:white;padding:12px 28px;text-decoration:none;
                  border-radius:6px;font-size:16px;font-weight:bold">
          📋 Open Full Report
        </a>
      </div>
      <p style="color:#888;font-size:12px;text-align:center;margin-top:16px">
        Auto-generated by ChannelStack Monitor • {week_label}
      </p>
    </div>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📊 Weekly Digest — {week_label}"
        msg["From"]    = FROM_EMAIL
        msg["To"]      = ALERT_EMAIL
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(FROM_EMAIL, password)
            server.sendmail(FROM_EMAIL, ALERT_EMAIL, msg.as_string())
        print(f"  📧 Digest email sent to {ALERT_EMAIL}")
        return True
    except Exception as e:
        print(f"::error::Weekly digest email FAILED to send to {ALERT_EMAIL}: {e}")
        return False


# ─── Monetization tracker ─────────────────────────────────────────────────────

def estimate_watch_hours(videos_with_duration: list[dict]) -> float:
    """Estimate total watch hours from video list (duration × views × 0.5 completion).
    Requires videos fetched with contentDetails part (duration field).
    Duration is ISO 8601 e.g. PT1M5S → parse to seconds.
    """
    import re
    total_seconds = 0.0
    for v in videos_with_duration:
        if "error" in v:
            continue
        dur_str = v.get("duration", "PT0S")
        # Parse ISO 8601 duration
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur_str)
        if not m:
            continue
        h = int(m.group(1) or 0)
        mn = int(m.group(2) or 0)
        s = int(m.group(3) or 0)
        dur_sec = h * 3600 + mn * 60 + s
        views = v.get("views", 0)
        # Shorts (<= 90s): ~50% completion; Long-form (> 90s): ~40% completion
        completion = 0.50 if dur_sec <= 90 else 0.40
        total_seconds += views * dur_sec * completion
    return total_seconds / 3600.0   # convert to hours


# YPP thresholds are watch hours across a ROLLING 365 DAYS. est_watch_hours is
# built from videos PUBLISHED IN THE LAST 14 DAYS only. Aug 30 2026: those two
# were divided by each other and printed as a percentage, so MZ read "~80/3,000
# (2.7%)" when the same rate over a year is ~2,000 hrs -- about 65%. Off by ~25x,
# in the direction that makes a channel look further from monetising than it is.
# Now projected to a year and LABELLED with what it is and what it omits.
WATCH_HOURS_WINDOW_DAYS = 14


def monetization_status_full(ch_cfg: dict, subscribers: int, est_watch_hours: float,
                              sub_growth_per_week: float,
                              window_days: int = WATCH_HOURS_WINDOW_DAYS,
                              views_per_sub: float | None = None) -> dict:
    """Return structured monetization progress for both email + Sheets.

    Returns a dict with:
      one_liner   — compact status line (used in email header per-channel box)
      detail      — multi-line breakdown shown in monetization section
      weeks_to_subs — estimated weeks to hit sub target (None if already met)
    """
    sub_target = ch_cfg["sub_target"]
    wh_target  = ch_cfg["wh_target"]
    label      = ch_cfg["label"]

    sub_pct = min(100, round(subscribers / sub_target * 100, 1))
    # Project the measured window to the 365-day basis the threshold actually uses.
    # This counts ONLY videos published inside the window -- the back catalogue is
    # still earning watch time and is not represented, so treat this as a floor.
    wh_annual = est_watch_hours * (365.0 / max(window_days, 1))
    wh_pct  = min(100, round(wh_annual / wh_target * 100, 1))

    # Estimate weeks to sub target
    if subscribers >= sub_target:
        weeks_to_subs = 0
        sub_eta = "✅ met"
    elif sub_growth_per_week and sub_growth_per_week > 0:
        weeks_to_subs = int((sub_target - subscribers) / sub_growth_per_week)
        sub_eta = f"~{weeks_to_subs}w at current pace"
    else:
        weeks_to_subs = None
        sub_eta = "pace unknown"

    # Which channel is on Tier-1 vs full path
    tier_note = "(Tier-1 target)" if sub_target == YT_SUB_THRESHOLD_TIER1 else "(Full YPP target)"

    one_liner = (
        f"🎯 {subscribers:,}/{sub_target:,} subs {tier_note} ({sub_pct}%) | "
        f"~{wh_annual:,.0f}/{wh_target:,} watch hrs/yr ({wh_pct}%) | "
        f"{sub_eta}"
    )

    detail_lines = [
        f"Subscribers:   {subscribers:,} / {sub_target:,} {tier_note} — {sub_pct}% — {sub_eta}",
        f"Watch hours:   ~{wh_annual:,.0f} / {wh_target:,} hrs per year — {wh_pct}%",
        f"               Basis: {est_watch_hours:.0f} hrs from videos published in the last "
        f"{window_days} days, projected to 365. Estimated as views × duration × "
        f"assumed completion (50% Shorts / 40% long-form) — NOT measured retention. "
        f"Videos older than {window_days} days are still earning watch time and are "
        f"not counted here, so this is a floor.",
    ]
    if views_per_sub:
        detail_lines.append(
            f"Sub pace:      1 sub per ~{views_per_sub:,.0f} views, measured from this "
            f"channel's own lifetime views ÷ lifetime subs. The ETA above uses this "
            f"rate; it is a lifetime average, so a channel that has improved will beat it."
        )
    if sub_target == YT_SUB_THRESHOLD_TIER1:
        detail_lines.append(
            f"MZ note:       Tier-1 unlocks fan funding. Full ad revenue needs 1,000 subs + 4,000 watch hrs. "
            f"Long-form views are your fastest path to watch hours."
        )

    return {
        "one_liner":      one_liner,
        "detail":         "\n".join(detail_lines),
        "weeks_to_subs":  weeks_to_subs,
        "sub_pct":        sub_pct,
        "wh_pct":         wh_pct,
        "subscribers":    subscribers,
        "sub_target":     sub_target,
        "est_watch_hours": est_watch_hours,
        "wh_target":      wh_target,
        "sub_eta":        sub_eta,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    now_ct    = datetime.now(CT)
    week_end  = now_ct.strftime("%Y-%m-%d")
    week_start = (now_ct - timedelta(days=7)).strftime("%Y-%m-%d")
    week_label = f"{week_start} → {week_end}"

    print(f"\n{'═'*60}")
    print(f"  📊 Weekly Digest  |  {week_label}")
    print(f"{'═'*60}\n")

    all_channel_data = []
    failed_channels: list[str] = []

    for key, ch in CHANNELS.items():
        print(f"\nProcessing {ch['label']} ...")

        # Write token file
        token_json = os.environ.get(ch["token_env"], "")
        if token_json:
            open(ch["token_file"], "w").write(token_json)

        try:
            svc = get_yt_service(ch["token_file"])

            # Channel-level stats
            ch_stats   = get_channel_stats(svc, ch["channel_id"])
            subs       = ch_stats.get("subscribers", 0)

            # This week and last week videos
            this_week  = get_videos_in_window(svc, ch["channel_id"], days_ago_start=7, days_ago_end=0)
            last_week  = get_videos_in_window(svc, ch["channel_id"], days_ago_start=14, days_ago_end=7)
            top_all    = get_top_videos_alltime(svc, ch["channel_id"], limit=10)

            this_week_clean = [v for v in this_week if "error" not in v]
            last_week_clean = [v for v in last_week if "error" not in v]

            # Thumbnail diversity check — most recent 8 across this+last week
            seen_ids: set = set()
            all_recent: list = []
            for v in sorted(
                this_week_clean + last_week_clean,
                key=lambda x: x.get("published", ""),
                reverse=True,
            ):
                if v.get("video_id") not in seen_ids:
                    seen_ids.add(v["video_id"])
                    all_recent.append(v)
            print(f"  Checking thumbnail diversity ({min(len(all_recent), 8)} videos) ...")
            thumb_alert = check_thumbnail_diversity(all_recent, ch["label"])
            if thumb_alert:
                print(f"  ⚠️  DUPLICATE THUMBNAILS: {thumb_alert['duplicate_count']}/{thumb_alert['total_checked']} identical!")
            else:
                print(f"  ✅ Thumbnails look diverse")

            this_views = sum(v["views"] for v in this_week_clean)
            last_views = sum(v["views"] for v in last_week_clean)
            this_avg   = this_views / max(len(this_week_clean), 1)
            last_avg   = last_views / max(len(last_week_clean), 1)

            top_this   = this_week_clean[0]["title"] if this_week_clean else "none"
            top_all_t  = top_all[0]["title"] if top_all and "error" not in top_all[0] else "n/a"

            # Watch hours estimate — use all videos we know about (this week + last week + top all)
            all_known_videos = {v["video_id"]: v for v in this_week_clean + last_week_clean
                                if "video_id" in v}
            est_wh = estimate_watch_hours(list(all_known_videos.values()))

            # Sub growth rate. This used to be `this_views / 20.0` -- an ASSUMED
            # 1 sub per 20 views, with a comment calling it "good enough". The
            # channel's own numbers disprove it: on Aug 30 2026 MZ had 116 subs
            # against ~16,700 views in the previous month alone, i.e. worse than
            # 1 sub per 144 views even crediting every sub it has ever had to that
            # month. The constant was ~7x optimistic and it drove the ETA in the
            # email. Same defect as the MZ speech rate fixed Aug 29: a guessed
            # constant nobody checked against the data sitting right beside it.
            #
            # Derive it instead, from lifetime views / lifetime subs on THIS
            # channel. Falls back to the old constant only if the API gave us
            # nothing to divide, and says so.
            lifetime_views = ch_stats.get("total_views", 0)
            if lifetime_views and subs:
                views_per_sub  = lifetime_views / subs
                sub_growth_est = max(0.01, this_views / views_per_sub)
            else:
                views_per_sub  = None
                sub_growth_est = max(0.1, this_views / 20.0)
                print("  ⚠️  No lifetime view/sub data — sub ETA falls back to a guessed rate")

            mono = monetization_status_full(ch, subs, est_wh, sub_growth_est,
                                            views_per_sub=views_per_sub)

            print(f"  This week: {len(this_week_clean)} videos, {this_views:,} views")
            print(f"  Last week: {len(last_week_clean)} videos, {last_views:,} views")
            print(f"  Subs: {subs:,} / {ch['sub_target']:,} ({mono['sub_pct']}%) | "
                  f"Watch hrs: ~{est_wh:.0f} / {ch['wh_target']:,} ({mono['wh_pct']}%)")
            print(f"  Generating Claude analysis ...")

            suggestions = analyze_with_claude(ch, this_week_clean, last_week_clean, top_all, ch_stats)

            all_channel_data.append({
                "label":             ch["label"],
                "this_count":        len(this_week_clean),
                "last_count":        len(last_week_clean),
                "this_views":        this_views,
                "last_views":        last_views,
                "this_avg":          this_avg,
                "last_avg":          last_avg,
                "subscribers":       subs,
                "top_this_week":     top_this,
                "alltime_top":       top_all_t,
                "suggestions":       suggestions,
                "monetization_status": mono["one_liner"],
                "monetization_detail": mono["detail"],
                "mono":              mono,
                "thumb_alert":       thumb_alert,
            })

        except Exception as e:
            print(f"::error::Weekly digest failed to process {ch['label']}: {e}")
            failed_channels.append(ch["label"])
            all_channel_data.append({
                "label":             ch["label"],
                "this_count":        0,
                "last_count":        0,
                "this_views":        0,
                "last_views":        0,
                "this_avg":          0,
                "last_avg":          0,
                "subscribers":       0,
                "top_this_week":     "error",
                "alltime_top":       "error",
                "suggestions":       f"• Error fetching data: {str(e)[:100]}",
                "monetization_status": "unknown",
                "monetization_detail": "",
                "mono":              {},
                "thumb_alert":       None,
            })

    # Write to Sheets
    write_to_sheets(all_channel_data, week_label)

    # Send email
    emailed = send_digest_email(all_channel_data, week_label)

    print(f"\n{'═'*60}")
    if emailed and not failed_channels:
        print(f"  ✅ Weekly digest complete")
        print(f"{'═'*60}\n")
        return 0
    # Aug 30 2026: `return 0` used to be unconditional. The whole point of this
    # job is the email; if it did not send, the job did not do its job.
    if not emailed:
        print(f"  ❌ Weekly digest did NOT email. Nobody was told anything.")
    if failed_channels:
        print(f"  ❌ Channels that failed: {', '.join(failed_channels)}")
    print(f"{'═'*60}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
