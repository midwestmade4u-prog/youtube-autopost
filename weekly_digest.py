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
            results.append({
                "video_id":    item["id"],
                "title":       item["snippet"]["title"],
                "published":   item["snippet"]["publishedAt"],
                "views":       int(stats.get("viewCount", 0)),
                "likes":       int(stats.get("likeCount", 0)),
                "comments":    int(stats.get("commentCount", 0)),
                "duration":    duration,
                "url":         f"https://youtu.be/{item['id']}",
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

        prompt = f"""You are a YouTube growth analyst. Analyze this channel's weekly performance and give actionable suggestions.

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

Respond with EXACTLY 3-5 bullet points. Each bullet must be a specific, actionable recommendation.
Compare recent videos to the all-time top performers and identify what patterns to replicate or avoid.
Focus on: title patterns, topic selection, what's working vs not working.
Be direct. No fluff. Write as if giving advice to a creator who will read this Sunday morning and act on it."""

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

def send_digest_email(all_channel_data: list[dict], week_label: str) -> None:
    """Send Sunday morning exec summary email."""
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not password:
        print("  ⚠️  GMAIL_APP_PASSWORD not set — skipping email")
        return

    # Build plain text
    lines = [f"YouTube Weekly Digest — {week_label}", "=" * 50, ""]
    for ch in all_channel_data:
        delta = ch["this_views"] - ch["last_views"]
        arrow = "📈" if delta >= 0 else "📉"
        lines.append(f"{arrow} {ch['label']}")
        lines.append(f"   {ch['this_count']} videos | {ch['this_views']:,} views ({delta:+,} vs last week)")
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

    # Build HTML
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
    except Exception as e:
        print(f"  ⚠️  Email failed: {e}")


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


def monetization_status_full(ch_cfg: dict, subscribers: int, est_watch_hours: float,
                              sub_growth_per_week: float) -> dict:
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
    wh_pct  = min(100, round(est_watch_hours / wh_target * 100, 1))

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
        f"~{est_watch_hours:.0f}/{wh_target:,} watch hrs ({wh_pct}%) | "
        f"{sub_eta}"
    )

    detail_lines = [
        f"Subscribers:   {subscribers:,} / {sub_target:,} {tier_note} — {sub_pct}% — {sub_eta}",
        f"Watch hours:   ~{est_watch_hours:.0f} / {wh_target:,} hrs — {wh_pct}% (estimated from view × duration × completion rate)",
    ]
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

            # Sub growth rate: subs gained this week vs last week is tricky without historical data.
            # Use this week's view-to-sub conversion as proxy: assume 1 sub per ~20 views.
            # Rough but good enough for ETA estimation.
            sub_growth_est = max(0.1, this_views / 20.0)

            mono = monetization_status_full(ch, subs, est_wh, sub_growth_est)

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
            })

        except Exception as e:
            print(f"  ❌ Failed to process {ch['label']}: {e}")
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
            })

    # Write to Sheets
    write_to_sheets(all_channel_data, week_label)

    # Send email
    send_digest_email(all_channel_data, week_label)

    print(f"\n{'═'*60}")
    print(f"  ✅ Weekly digest complete")
    print(f"{'═'*60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
