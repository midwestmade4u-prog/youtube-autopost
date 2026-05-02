#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  auto_post_mz.py — Minute Zero auto-post orchestrator        ║
╚══════════════════════════════════════════════════════════════╝

Flow:
  1. Pick topic (based on weekday + time → Format A / B / C)
  2. Load v3 prompt from MZ_Channel/MZ_Script_Generator_Prompt_v3.md
  3. Call OpenAI (or Anthropic) API → get v3 JSON output
  4. video_mz.render_video() → produces master + platform variants + thumb
  5. Upload master to YouTube (via video_mz_upload helper)
  6. Log to auto_post_log.json + append to Google Sheets
  7. (Future) Push TikTok variant to Content Posting API

Usage:
  python3 auto_post_mz.py                   # pick topic automatically
  python3 auto_post_mz.py --format A        # force a specific format
  python3 auto_post_mz.py --topic "Knight Capital"
  python3 auto_post_mz.py --dry-run         # render only, no upload

Required env vars:
  OPENAI_API_KEY                — script generation (or ANTHROPIC_API_KEY, see MODEL_BACKEND below)
  PEXELS_API_KEY                — video clip sourcing
  (YouTube token is loaded from youtube_token_mz.json)

Required Python deps (installed in GH Action workflow):
  edge-tts, Pillow, requests, openai, google-api-python-client,
  google-auth, google-auth-httplib2, google-auth-oauthlib
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "auto_post_log.json"
MZ_CHANNEL_DIR = BASE_DIR / "MZ_Channel"
MZ_PROMPT_V3 = MZ_CHANNEL_DIR / "MZ_Script_Generator_Prompt_v3.md"
MZ_OUTPUT_DIR = BASE_DIR / "MZ_Output"
MZ_OUTPUT_DIR.mkdir(exist_ok=True)

# ── Model backend ──────────────────────────────────────────────────────────
MODEL_BACKEND = os.environ.get("MZ_MODEL_BACKEND", "openai").lower()   # openai|anthropic
OPENAI_MODEL    = os.environ.get("MZ_OPENAI_MODEL",    "gpt-4o")
ANTHROPIC_MODEL = os.environ.get("MZ_ANTHROPIC_MODEL", "claude-sonnet-4-6")


# ─── Topic banks (mirror of MZ_Topic_Bank_v1.md as of Apr 24 2026) ──────────

ONE_BAD_DAY_TOPICS = [
    "Knight Capital — 12 minutes of bad code → $440M evaporated, Aug 1, 2012, 9:30 AM",
    "Coca-Cola — Apr 23, 1985 — the day they announced 'New Coke'",
    "Yahoo — 1998 meeting — Yahoo passes on buying Google for $1M",
    "Blockbuster — 2000 — the phone call rejecting Netflix for $50M",
    "Quaker Oats — 1994 — the Snapple acquisition decision ($1.7B → $300M in 27 months)",
    "JCPenney (Ron Johnson) — Feb 1, 2012 — killing all coupons on day one",
    "AOL–Time Warner — Jan 10, 2000 — merger announcement press conference",
    "Enron — Aug 14, 2001 — Skilling's sudden resignation call",
    "Theranos — Oct 16, 2015 — WSJ story drops",
    "FTX — Nov 2, 2022 — CoinDesk leaks the Alameda balance sheet",
    "Long-Term Capital Management — Aug 17, 1998 — Russia defaults",
    "Arthur Andersen — Oct 23, 2001 — the shredding-party memo",
    "Borders — 2001 — signing the deal to hand their website to Amazon",
    "Wells Fargo — The 2011 sales mandate memo ('eight is great')",
    "Boeing — The MCAS single-sensor design call (737 MAX)",
    "MySpace — Jul 19, 2005 — News Corp pays $580M and hands it to people who saw it as a billboard, not a platform",
    "Bear Stearns — Mar 13, 2008 — the midnight call admitting insolvency",
    "Lehman Brothers — Sep 14, 2008 — the weekend Paulson refused to bail them out",
    "MF Global — Oct 2011 — Jon Corzine's Euro bond doubling-down call",
    "Sears — Mar 24, 2005 — Eddie Lampert merges Kmart and Sears, announces he'll run the combined company like a hedge fund",
    "Groupon — 2011 — the pre-IPO 'accounting correction' announcement",
    "WeWork — Aug 14, 2019 — the S-1 filing that killed the IPO",
    "RJR Nabisco — 1988 — the 'Premier' smokeless cigarette launch call",
    # Moved to end — same company as GM bailout (already posted Apr 28); space these out
    "General Motors — 2001 — the 57¢ ignition switch cost-cut decision",
]
# Removed from ONE_BAD_DAY (Apr 30 2026 cleanup):
# - Barings Bank (UK), Société Générale (France), Swissair (Switzerland),
#   Volkswagen (Germany) → moved to UNKNOWN_FAILURE pool (Format B only)
# - Friendster → cut entirely (too obscure, no emotional pull for US audience)
# - Polaroid → moved to NEAR_DEATH_TOPICS (better fit: invented digital, shelved it)
# - MySpace reframed: News Corp acquisition (Jul 19 2005) is the real minute zero
# - Sears reframed: Lampert merger announcement (Mar 24 2005) is the real minute zero

# Tier 1 (fire first) then Tier 2 — kill criterion applies after first 10 publish
UNKNOWN_FAILURE_TOPICS_TIER1 = [
    "Wirecard (Germany) — Jun 18, 2020 — the €1.9B 'doesn't exist' admission",
    "Thomas Cook (UK) — Sep 23, 2019 — 178 years of travel ends at midnight",
    "Olympus (Japan) — Oct 14, 2011 — CEO Michael Woodford fired for asking questions",
    "Parmalat (Italy) — Dec 2003 — the €3.95B Bank of America 'deposit' is fake",
    "Satyam (India) — Jan 7, 2009 — Chairman's fraud confession letter",
    "HMV UK — Jan 15, 2013 — administration at flagship Oxford Street store",
    "Sharp (Japan) — Feb 2016 — Foxconn takeover signing",
    "Flybe (UK) — Mar 5, 2020 — the 2 AM insolvency email",
    # Moved from ONE_BAD_DAY Apr 30 2026 — foreign companies belong in Format B
    "Barings Bank (UK) — Feb 23, 1995 — Nick Leeson's hidden account #88888 discovered",
    "Société Générale (France) — Jan 24, 2008 — Jerome Kerviel's €4.9B position unwound",
    "Swissair (Switzerland) — Oct 2, 2001 — fleet grounded at 3:02 PM",
    "Volkswagen (Germany) — 2006 — the 'defeat device' engineering decision",
]
UNKNOWN_FAILURE_TOPICS_TIER2 = [
    "Carillion (UK) — Jan 15, 2018 — liquidation announced",
    "Woolworths UK — Dec 26, 2008 — the Boxing Day closing-down sale",
    "BHS (UK) — Apr 25, 2016 — administration filing",
    "Debenhams (UK) — Dec 1, 2020 — liquidation announced",
    "Arcadia Group (UK) — Nov 30, 2020 — Philip Green's empire collapses",
    "Monarch Airlines (UK) — Oct 2, 2017 — 4 AM grounding",
    "Ansett Australia — Sep 14, 2001 — grounding announcement",
    "Sanlu (China) — Sep 2008 — melamine detected in baby formula",
    "Laker Airways (UK) — Feb 5, 1982 — cash pulled by creditors",
    "Kirch Media (Germany) — Apr 8, 2002 — €6.5B insolvency filing",
    "OneTel (Australia) — May 28, 2001 — administrators appointed",
    "HIH Insurance (Australia) — Mar 15, 2001 — provisional liquidation",
    "Jessops (UK) — Jan 9, 2013 — administration, all 192 stores gone overnight",
    "Comet (UK) — Nov 2, 2012 — administration",
]

NEAR_DEATH_TOPICS = [
    "Apple — Aug 6, 1997 — Steve Jobs announces Microsoft's $150M lifeline",
    "LEGO — 2003 — the emergency board meeting, near-liquidation vote",
    "Marvel — Dec 1996 — Chapter 11 filing",
    "IBM — 1993 — Lou Gerstner's first board meeting, $8B loss",
    "Chrysler — 1979 — the $1.5B loan guarantee vote in Congress",
    "Disney — 1984 — Bass brothers rescue from Saul Steinberg's raid",
    "FedEx — 1973 — Fred Smith's $5K blackjack win to make Monday's payroll",
    "Starbucks — Jan 2008 — Schultz returns, closes 600 stores in one weekend",
    "Harley-Davidson — 1981 — the buyout from AMF, 13 executives' personal savings",
    "Ford — Nov 2006 — mortgaging the blue oval logo + all assets for $23.6B",
    "Nintendo — 1985 — post-video-game-crash, betting everything on the NES launch",
    "Converse — 2001 — Chapter 11, sold to Nike",
    "American Express — 1963 — Salad Oil Scandal, $150M exposure",
    "Delta Air Lines — Sep 14, 2005 — Chapter 11 filing at 5:30 AM",
    "J.Crew — May 4, 2020 — COVID bankruptcy filing",
    "GM — Jun 1, 2009 — Chapter 11, $82B federal bailout",
    "Continental Airlines — 1983 & 1990 — double bankruptcy survival",
    "Harrods — 1985 — Mohammed Al-Fayed's last-minute Takeover win",
    # Moved from ONE_BAD_DAY Apr 30 2026 — better as near-death/missed opportunity
    "Polaroid — 1975 — engineers invent the digital camera, management shelves it; Polaroid files bankruptcy 26 years later having never shipped it",
]


# ─── Rotation logic ──────────────────────────────────────────────────────────

def pick_format_for_slot(weekday: int, hour_ct: int) -> str:
    """
    Rotation from MZ_Channel #3 plan:
      09:00 CT daily  → Format A (one_bad_day)
      19:00 CT Mon/Wed/Fri/Sun → Format B (unknown_failure)
      19:00 CT Tue/Thu/Sat     → Format C (near_death)

    weekday: Python datetime.weekday() (Monday=0 ... Sunday=6)
    hour_ct: hour in Central Time (24h)
    """
    if hour_ct < 12:
        return "A"
    # Evening slot
    # Mon=0, Wed=2, Fri=4, Sun=6  → Format B
    # Tue=1, Thu=3, Sat=5         → Format C
    if weekday in (0, 2, 4, 6):
        return "B"
    return "C"


def pick_topic(format_letter: str) -> tuple[str, str]:
    """Return (topic_string, format_tag_for_prompt)."""
    log = _load_log()
    used = set(log.get("mz_topics_used", []))

    if format_letter == "A":
        pool = ONE_BAD_DAY_TOPICS
        tag = "one_bad_day"
    elif format_letter == "B":
        # Exhaust Tier 1 before dipping into Tier 2
        tier1_available = [t for t in UNKNOWN_FAILURE_TOPICS_TIER1 if t not in used]
        tier2_available = [t for t in UNKNOWN_FAILURE_TOPICS_TIER2 if t not in used]
        pool = tier1_available if tier1_available else tier2_available
        if not pool:
            pool = UNKNOWN_FAILURE_TOPICS_TIER1 + UNKNOWN_FAILURE_TOPICS_TIER2
        tag = "unknown_failure"
    elif format_letter == "C":
        pool = NEAR_DEATH_TOPICS
        tag = "near_death"
    else:
        raise ValueError(f"Invalid format letter: {format_letter}")

    available = [t for t in pool if t not in used]
    if not available:
        print(f"  🔄 All MZ Format {format_letter} topics used — resetting cycle")
        # Clear only this format's used-set — preserve other formats' rotation
        for t in pool:
            used.discard(t)
        log["mz_topics_used"] = list(used)
        _save_log(log)
        available = pool[:]

    return random.choice(available), tag


# ─── Log helpers ─────────────────────────────────────────────────────────────

def _load_log() -> dict:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_log(log: dict) -> None:
    LOG_FILE.write_text(json.dumps(log, indent=2))


def mark_mz_posted(topic: str, title: str, video_url: str, format_tag: str) -> None:
    log = _load_log()
    log.setdefault("mz_topics_used", []).append(topic)
    log.setdefault("posts", []).append({
        "channel":    "mz",
        "format":     format_tag,
        "topic":      topic,
        "title":      title,
        "url":        video_url,
        "posted_at":  time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_log(log)


# ─── Script generation (v3 prompt → JSON) ────────────────────────────────────

def load_system_prompt() -> str:
    """Read v3 prompt markdown and extract the code-block payload."""
    if not MZ_PROMPT_V3.exists():
        raise FileNotFoundError(f"Missing v3 prompt: {MZ_PROMPT_V3}")
    text = MZ_PROMPT_V3.read_text()
    # The prompt lives inside a ```...``` code fence
    in_block = False
    lines: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("```") and not in_block:
            in_block = True
            continue
        if line.strip().startswith("```") and in_block:
            break
        if in_block:
            lines.append(line)
    if not lines:
        raise RuntimeError("Could not extract code block from v3 prompt file")
    return "\n".join(lines)


def generate_script(topic: str, format_tag: str) -> dict:
    """Call the LLM backend with v3 prompt + tagged topic, return parsed JSON."""
    system = load_system_prompt()
    user = f"[{format_tag.upper()}] {topic}"

    if MODEL_BACKEND == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.8,
        )
        content = r.choices[0].message.content
    elif MODEL_BACKEND == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        r = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        content = r.content[0].text
    else:
        raise RuntimeError(f"Unknown MZ_MODEL_BACKEND: {MODEL_BACKEND}")

    # Defensive parse: sometimes models wrap in ```json ... ```
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].lstrip()
    data = json.loads(content)
    if "error" in data:
        raise RuntimeError(f"Script generator self-rejected: {data['error']}")
    return data


# ─── YouTube upload ──────────────────────────────────────────────────────────

def upload_to_youtube(video_path: Path, title: str, description: str,
                      tags: list[str], thumbnail_path: Path | None = None,
                      privacy_status: str = "public") -> str:
    """Upload the MZ master to YouTube. Returns video URL.

    privacy_status: "public" (default, used by cron), "unlisted" (manual
    routing test — video uploads but doesn't appear in feed/search), or
    "private" (only owner can view).
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token_path = BASE_DIR / "youtube_token_mz.json"
    if not token_path.exists():
        raise RuntimeError("youtube_token_mz.json missing — complete OAuth first")

    creds = Credentials.from_authorized_user_file(
        str(token_path),
        ["https://www.googleapis.com/auth/youtube.upload",
         "https://www.googleapis.com/auth/youtube"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    yt = build("youtube", "v3", credentials=creds)

    # Safety check: verify token's channel identity matches MZ
    me = yt.channels().list(mine=True, part="id,snippet").execute()
    if not me.get("items"):
        raise RuntimeError("YouTube token returned no channel — bad OAuth?")
    channel_id = me["items"][0]["id"]
    # Log — don't hard-fail if MZ channel id isn't yet configured
    print(f"  🔑 Uploading as channel: {channel_id} ({me['items'][0]['snippet']['title']})")

    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "tags":        tags[:15],
            "categoryId":  "22",   # People & Blogs — matches MZ_Channel_Setup.md
        },
        "status": {
            "privacyStatus":           privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), resumable=True, chunksize=1024 * 1024 * 4)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = req.next_chunk()

    video_id = response["id"]
    video_url = f"https://youtu.be/{video_id}"

    # Optional: upload custom thumbnail
    if thumbnail_path and thumbnail_path.exists():
        try:
            yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))).execute()
            print(f"  🖼️  Custom thumbnail uploaded")
        except Exception as e:
            print(f"  ⚠️ Thumbnail upload failed (non-fatal): {e}")

    return video_url


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format",  choices=["A", "B", "C"],
                        help="Force a specific format (skip auto-rotation).")
    parser.add_argument("--topic",   help="Override topic string.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Render only, skip YouTube upload.")
    parser.add_argument("--unlisted", action="store_true",
                        help="Upload as unlisted (not public). Use for first routing test.")
    args = parser.parse_args()

    print(f"\n{'═' * 60}")
    print(f"  🎬 Minute Zero Auto-Post  |  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═' * 60}")

    # 1. Topic selection
    if args.topic:
        topic = args.topic
        format_tag = {"A": "one_bad_day", "B": "unknown_failure", "C": "near_death"}[args.format or "A"]
    else:
        if args.format:
            fmt = args.format
        else:
            now = dt.datetime.now(dt.timezone.utc)
            # Central Time is UTC-5 (CDT) or -6 (CST). Use -5 as conservative default for daylight savings.
            ct = now - dt.timedelta(hours=5)
            fmt = pick_format_for_slot(ct.weekday(), ct.hour)
        topic, format_tag = pick_topic(fmt)

    print(f"\n📖 Format: {format_tag}")
    print(f"📖 Topic : {topic}")

    # 2. Generate script
    print(f"\n✍️  Generating v3 script (backend: {MODEL_BACKEND}) ...")
    script_data = generate_script(topic, format_tag)
    print(f"  ✅ Title: {script_data['title']}")
    print(f"  ✅ Duration target: {script_data.get('target_duration_sec', '?')}s")
    # Hook rotation telemetry (v3 → v4): log each variant's style + validity.
    # A variant's `hook` may legitimately be null if the LLM couldn't generate
    # that style; we surface those so v4 weighting can trust the data.
    hooks = script_data.get("hooks", []) or []
    for i, h in enumerate(hooks):
        style = (h or {}).get("style", "?")
        text  = (h or {}).get("hook")
        status = "∅ null" if not text else f"{len(text)} chars"
        print(f"  ✅ Hook[{i}] {style}: {status}")
    if not any((h or {}).get("hook") for h in hooks):
        print("  ⚠️  All hook variants null — script body hook will still render, but v4 rotation data is empty")

    # 3. Render
    print(f"\n🎥 Rendering video (clean master + variants) ...")
    from video_mz import render_video
    out_dir = MZ_OUTPUT_DIR / dt.date.today().isoformat()
    result = render_video(script_data, out_dir)
    print(f"  ✅ Master:    {result['master_path']}")
    print(f"  ✅ YT:        {result['yt_path']}")
    print(f"  ✅ TikTok:    {result['tt_path']}")
    print(f"  ✅ Instagram: {result['ig_path']}")
    print(f"  ✅ Thumb:     {result['thumb_path']}")

    if args.dry_run:
        print(f"\n⏹️  Dry run — skipping YouTube upload.")
        return 0

    # 4. Upload to YouTube
    print(f"\n📤 Uploading to YouTube ...")
    hashtags = script_data.get("hashtags", "").strip()
    tags = [h.lstrip("#") for h in hashtags.split() if h.startswith("#")]
    description = (
        f"{script_data.get('description', '')}\n\n"
        f"{hashtags}"
    ).strip()
    video_url = upload_to_youtube(
        Path(result["yt_path"]),
        title=script_data["title"],
        description=description,
        tags=tags,
        thumbnail_path=Path(result["thumb_path"]),
        privacy_status="unlisted" if args.unlisted else "public",
    )
    print(f"  ✅ Posted ({'unlisted' if args.unlisted else 'public'}): {video_url}")

    # 5. Log
    mark_mz_posted(topic, script_data["title"], video_url, format_tag)

    # 6. Trigger file for traceability (matches TMF/BSG pattern)
    trigger_path = BASE_DIR / f"auto_trigger_mz_{time.strftime('%Y%m%d_%H%M')}.json"
    trigger_path.write_text(json.dumps({
        "channel":     "mz",
        "format_tag":  format_tag,
        "topic":       topic,
        "title":       script_data["title"],
        "video_url":   video_url,
        "master_path": result["master_path"],
        "tt_path":     result["tt_path"],    # TikTok variant — for cross-post once wired
        "ig_path":     result["ig_path"],    # Instagram variant — future
        "thumb_path":  result["thumb_path"],
        "posted_at":   time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2))
    print(f"  📄 Trigger file: {trigger_path.name}")

    print(f"\n{'═' * 60}")
    print(f"  🎉 SUCCESS — Minute Zero")
    print(f"  Topic : {topic}")
    print(f"  Title : {script_data['title']}")
    print(f"  URL   : {video_url}")
    print(f"{'═' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
