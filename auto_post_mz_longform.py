#!/usr/bin/env python3
"""
auto_post_mz_longform.py — Minute Zero Long-Form (8–10 min) Auto-Post
══════════════════════════════════════════════════════════════════════
Generates, renders, and uploads a private 16:9 YouTube video for Minute Zero.
Sends an email notification to Matt with the YouTube Studio review link.
Matt manually reviews and flips to public / schedules.

Usage:
    python3 auto_post_mz_longform.py
    python3 auto_post_mz_longform.py --topic "Enron: the last 90 days"
    python3 auto_post_mz_longform.py --dry-run   # render only, skip upload

Schedule: Tuesday + Friday at 9 AM CT via mz-longform.yml
"""

import argparse
import json
import os
import random
import smtplib
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
MZ_CHANNEL_DIR = BASE_DIR / "MZ_Channel"
MZ_LONGFORM_PROMPT = MZ_CHANNEL_DIR / "MZ_Longform_Prompt_v1.md"
LOG_FILE       = BASE_DIR / "auto_post_log.json"
OUTPUT_DIR     = BASE_DIR / "MZ_Longform_Output"

# ── Config ────────────────────────────────────────────────────────────────────
MZ_CHANNEL_ID  = "UCMVhjR4HetJctXeYkuPgg6w"
TOKEN_FILE     = BASE_DIR / "youtube_token_mz.json"
YT_SCOPES      = ["https://www.googleapis.com/auth/youtube.upload",
                  "https://www.googleapis.com/auth/youtube"]
NOTIFY_EMAIL   = "wisseinc@gmail.com"
MODEL_BACKEND  = os.getenv("MZ_MODEL_BACKEND", "openai")

# Word targets: 1300–1600w at 2.5 wps = ~8.5–10.5 min
WORD_MIN, WORD_MAX = 1300, 1600

# ── Topic bank ────────────────────────────────────────────────────────────────
LONGFORM_TOPICS = [
    # Tier 1 — proven short performers, expand to long-form
    "Harley-Davidson 1981 — 13 executives pool personal savings to buy the company back from AMF",
    "Marvel 1996 — $700M in debt, Ike Perlmutter buys the company out of bankruptcy for $82.5M",
    "General Motors Jun 1, 2009 — Chapter 11, $82B federal bailout, the largest industrial bankruptcy in US history",
    "Lehman Brothers Sep 14, 2008 — the weekend Hank Paulson refused to bail them out",
    "Knight Capital Aug 1, 2012 — 45 minutes of bad code destroys $440M and nearly takes down the NYSE",
    # Tier 2 — deep stories
    "Enron 2001 — the last 90 days: from Fortune's Most Innovative to $63B bankruptcy",
    "WorldCom Jun 25, 2002 — internal auditor Cynthia Cooper walks into the board meeting with proof of $3.8B in fake entries",
    "FTX Nov 2022 — the 72 hours that destroyed $32B and sent Sam Bankman-Fried to prison",
    "Theranos 2015 — the WSJ reporter who spent a year cracking the story that ended Elizabeth Holmes",
    "Bear Stearns Mar 2008 — the midnight call where Jimmy Cayne admitted insolvency to the Fed",
    "WeWork Aug 2019 — the S-1 filing that revealed Adam Neumann's empire was built on nothing",
    "Blockbuster — the full story: from 9,000 stores to zero, and the Netflix meeting that sealed it",
    "Toys R Us — how three private equity firms loaded a beloved brand with $5B in debt and walked away",
    "Sears — 15 years of Eddie Lampert dismantling a $30B retailer in slow motion",
    # Tier 3 — near-death survival
    "Apple Aug 1997 — 90 days from bankruptcy, a $150M lifeline from Microsoft, and the Steve Jobs return",
    "FedEx 1973 — Fred Smith flies to Vegas with the company's last $5,000, wins at blackjack, makes Monday's payroll",
    "Starbucks Jan 2008 — Howard Schultz returns as CEO, closes 600 stores in one weekend, rewrites the company",
    "Netflix Sep 2011 — the Qwikster disaster: 800K subscribers quit in a month, stock drops 77%",
    "Domino's 2009 — the CEO who went on national TV and admitted his pizza was terrible, then fixed it",
]


def _load_log() -> dict:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_log(log: dict) -> None:
    LOG_FILE.write_text(json.dumps(log, indent=2))


def pick_topic() -> str:
    log = _load_log()
    used = set(log.get("mz_longform_topics_used", []))
    available = [t for t in LONGFORM_TOPICS if t not in used]
    if not available:
        print("  🔄 All long-form topics used — resetting cycle")
        log["mz_longform_topics_used"] = []
        _save_log(log)
        available = LONGFORM_TOPICS[:]
    return random.choice(available)


def mark_posted(topic: str, title: str, url: str) -> None:
    log = _load_log()
    used = log.get("mz_longform_topics_used", [])
    if topic not in used:
        used.append(topic)
    log["mz_longform_topics_used"] = used
    posts = log.get("mz_longform_posts", [])
    ts = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")
    posts.append({"timestamp": ts, "topic": topic, "title": title, "url": url, "status": "private"})
    log["mz_longform_posts"] = posts
    _save_log(log)


def load_system_prompt() -> str:
    """Extract the system prompt from the markdown prompt file."""
    text = MZ_LONGFORM_PROMPT.read_text()
    in_block = False
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("```") and not in_block:
            in_block = True
            continue
        if line.strip().startswith("```") and in_block:
            break
        if in_block:
            lines.append(line)
    if not lines:
        raise ValueError("Could not extract system prompt from MZ_Longform_Prompt_v1.md")
    return "\n".join(lines)


def longform_title_ok(title: str) -> tuple[bool, str]:
    """Enforce 'How' or number/dollar opener."""
    t = (title or "").strip()
    if len(t) < 10:
        return False, "title too short"
    if len(t) > 70:
        return False, f"title too long ({len(t)} chars)"
    t_lower = t.lower()
    words = t_lower.split()
    banned = ("the night", "the day", "the moment", "the story", "the hour")
    for b in banned:
        if t_lower.startswith(b):
            return False, f"banned opener '{b}' — use 'How' or a number/dollar figure"
    starts_with_how = t_lower.startswith("how ")
    has_number = any(c.isdigit() or c == "$" for c in " ".join(words[:5]))
    if not starts_with_how and not has_number:
        return False, "must start with 'How' or contain number/$dollar in first 5 words"
    return True, ""


def generate_script(topic: str) -> dict:
    """Generate long-form script via OpenAI (primary) or Anthropic (fallback)."""
    system = load_system_prompt()
    user_msg = (
        f"Write a complete 8–10 minute Minute Zero long-form documentary script about: {topic}\n\n"
        f"CRITICAL: The JSON 'script' field (the narration text ONLY — not title, description, or tags) "
        f"MUST contain 1,300–1,600 words. Count them before returning.\n\n"
        f"Minimum words per act — all five acts must be fully expanded:\n"
        f"  Act 1 (Hook):       100–120 words\n"
        f"  Act 2 (Context):    260–290 words\n"
        f"  Act 3 (Minute Zero): 380–420 words\n"
        f"  Act 4 (Fallout):    360–400 words\n"
        f"  Act 5 (Lesson):     360–400 words\n\n"
        f"Each act must be narrated in full — specific dollar figures, names, precise timestamps, "
        f"what people said in the room, who got hurt, what the consequences looked like. "
        f"Do NOT summarize. Do NOT compress. A script under 1,300 words is a SHORT VIDEO and will be REJECTED."
    )

    def _call_openai(system_prompt: str, user: str) -> dict:
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user}],
            max_tokens=6000,
            temperature=0.75,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    def _call_anthropic(system_prompt: str, user: str) -> dict:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=6000,
            system=system_prompt,
            messages=[{"role": "user", "content": user}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    def _call(system_prompt: str, user: str) -> dict:
        try:
            print("    Calling OpenAI GPT-4o...")
            return _call_openai(system_prompt, user)
        except Exception as e:
            print(f"    OpenAI failed ({e}) — falling back to Anthropic...")
            return _call_anthropic(system_prompt, user)

    last_data = None
    extra = ""

    for attempt in range(1, 4):
        print(f"  Attempt {attempt}/3...")
        data = _call(system + extra, user_msg)
        last_data = data

        title = (data.get("title") or "").strip()
        title_ok, title_reason = longform_title_ok(title)
        word_count = len((data.get("script") or "").split())
        wc_ok = WORD_MIN <= word_count <= WORD_MAX

        problems = []
        if not title_ok:
            problems.append(f"TITLE FAIL: {title_reason}")
        if not wc_ok:
            est_sec = int(word_count / 2.5)
            target_min_sec = int(WORD_MIN / 2.5)
            target_max_sec = int(WORD_MAX / 2.5)
            problems.append(
                f"LENGTH FAIL: script is {word_count} words (~{est_sec}s). "
                f"Must be {WORD_MIN}–{WORD_MAX} words (target {target_min_sec}–{target_max_sec}s). "
                f"{'Expand every act with more specific details.' if word_count < WORD_MIN else 'Trim without losing key facts.'}"
            )

        if not problems:
            print(f"  ✅ Script passed validators ({word_count}w, title OK)")
            return data

        print(f"  ⚠️  Validator failed attempt {attempt}: {' | '.join(problems)}")
        extra = (
            "\n\nIMPORTANT — your previous draft was REJECTED:\n- "
            + "\n- ".join(problems)
            + f"\n\nFix ALL issues in this next attempt.\n"
              f"LENGTH is the #1 issue: the 'script' field must be {WORD_MIN}–{WORD_MAX} words. "
              f"Your previous script was under {WORD_MIN} words — that is a SHORT VIDEO SUMMARY, not a documentary.\n"
              f"Required minimum words per act:\n"
              f"  Act 1 (Hook): 100 words | Act 2 (Context): 260 words | "
              f"Act 3 (Minute Zero): 380 words | Act 4 (Fallout): 360 words | Act 5 (Lesson): 360 words\n"
              f"Expand EVERY beat: specific names, exact dollar amounts, precise timestamps, "
              f"direct quotes, who got hurt, what the aftermath looked like. "
              f"Do NOT compress. Do NOT summarise. Write the FULL story.\n"
              f"Title must start with 'How' or a number/dollar figure."
        )

    # All retries exhausted — skip
    last_title = (last_data or {}).get("title", "n/a")
    last_wc = len((last_data or {}).get("script", "").split())
    raise ValueError(
        f"VALIDATION_SKIP: all 3 attempts failed — last script: {last_wc}w, last title: \"{last_title}\""
    )


def render_longform_video(script_data: dict, out_dir: Path) -> dict:
    """
    Render a 16:9 landscape long-form video using ffmpeg + edge-tts.
    Returns paths to the rendered video and thumbnail.
    """
    import edge_tts
    import asyncio
    from PIL import Image, ImageDraw, ImageFont

    out_dir.mkdir(parents=True, exist_ok=True)
    video_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    script_text = script_data.get("script", "")
    title       = script_data.get("title", "Minute Zero")
    queries     = script_data.get("pexels_queries", [])

    # ── 1. Generate narration audio ───────────────────────────────────────────
    print("  🎙️  Generating narration audio...")
    audio_path = out_dir / f"{video_id}_narration.mp3"
    tts_voice  = os.getenv("MZ_VOICE", "en-US-ChristopherNeural")

    async def _tts():
        communicate = edge_tts.Communicate(script_text, tts_voice)
        await communicate.save(str(audio_path))

    asyncio.run(_tts())
    print(f"  ✅ Audio: {audio_path.name}")

    # ── 2. Get audio duration ─────────────────────────────────────────────────
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(audio_path)],
        capture_output=True, text=True
    )
    duration_sec = float(json.loads(result.stdout)["format"]["duration"])
    print(f"  ✅ Duration: {duration_sec:.1f}s ({duration_sec/60:.1f} min)")

    # ── 3. Fetch landscape Pexels footage ─────────────────────────────────────
    print("  🎬 Fetching landscape Pexels footage...")
    pexels_key = os.getenv("PEXELS_API_KEY", "")
    clip_paths = []

    if pexels_key and queries:
        import requests
        # Load dedup ledger
        dedup_file = BASE_DIR / "pexels_used_mz_longform.json"
        used_ids = set(json.loads(dedup_file.read_text()) if dedup_file.exists() else [])
        new_used = []

        clip_duration = duration_sec / max(len(queries), 1)

        for i, query in enumerate(queries[:16]):
            try:
                resp = requests.get(
                    "https://api.pexels.com/videos/search",
                    headers={"Authorization": pexels_key},
                    params={"query": query, "orientation": "landscape", "per_page": 10, "size": "medium"},
                    timeout=10,
                )
                videos = resp.json().get("videos", [])
                # Filter dedup and prefer landscape
                fresh = [v for v in videos if v["id"] not in used_ids]
                if not fresh:
                    fresh = videos  # reuse if exhausted
                if not fresh:
                    continue

                # Pick best landscape file
                vid = fresh[0]
                files = [f for f in vid.get("video_files", []) if f.get("quality") in ("hd", "sd")]
                files = [f for f in files if (f.get("width", 0) / max(f.get("height", 1), 1)) > 1.5]  # landscape ratio
                files.sort(key=lambda f: abs(f.get("width", 0) - 1920))
                if not files:
                    continue

                clip_url  = files[0]["link"]
                clip_path = out_dir / f"clip_{i:02d}.mp4"
                r = requests.get(clip_url, timeout=30)
                clip_path.write_bytes(r.content)

                # Trim + scale to 1920x1080
                trimmed = out_dir / f"clip_{i:02d}_trim.mp4"
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(clip_path),
                    "-t", str(clip_duration),
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                    "-an", str(trimmed)
                ], capture_output=True)
                clip_paths.append(trimmed)
                used_ids.add(vid["id"])
                new_used.append(vid["id"])
                print(f"    ✅ Clip {i+1}: {query[:40]}")
            except Exception as e:
                print(f"    ⚠️  Clip {i+1} failed ({query[:30]}): {e}")

        # Save dedup
        all_used = list(used_ids)
        dedup_file.write_text(json.dumps(all_used, indent=2))

    # ── 4. Build video ────────────────────────────────────────────────────────
    print("  🎞️  Compositing final video...")
    output_path = out_dir / f"{video_id}_longform.mp4"

    if clip_paths:
        # Concat clips to match audio duration
        concat_file = out_dir / "concat.txt"
        concat_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths))
        backdrop = out_dir / "backdrop.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-t", str(duration_sec), "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p", str(backdrop)
        ], capture_output=True)
    else:
        # Fallback: dark slate background
        backdrop = out_dir / "backdrop.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=0x0a0a0a:size=1920x1080:duration={duration_sec}:rate=30",
            "-c:v", "libx264", str(backdrop)
        ], capture_output=True)

    # Merge audio + video
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(backdrop),
        "-i", str(audio_path),
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(output_path)
    ], capture_output=True)

    print(f"  ✅ Video: {output_path.name}")

    # ── 5. Generate thumbnail ─────────────────────────────────────────────────
    thumb_path = out_dir / f"{video_id}_thumb.jpg"
    try:
        img = Image.new("RGB", (1280, 720), (10, 10, 10))
        draw = ImageDraw.Draw(img)
        thumb_text = script_data.get("thumbnail_text", title[:30].upper())
        draw.text((640, 360), thumb_text, fill=(255, 255, 255), anchor="mm")
        img.save(str(thumb_path))
    except Exception:
        pass

    return {
        "video_path": output_path,
        "thumb_path": thumb_path,
        "duration_sec": duration_sec,
        "video_id": video_id,
    }


def upload_to_youtube(video_path: Path, title: str, description: str,
                      tags: list, thumb_path: Path | None = None) -> str:
    """Upload as PRIVATE. Returns YouTube video URL."""
    import json as _json
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token_data = _json.loads(TOKEN_FILE.read_text())
    creds = Credentials.from_authorized_user_info(token_data, YT_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)

    # Verify channel identity
    me = youtube.channels().list(part="id,snippet", mine=True).execute()
    channel_id = me["items"][0]["id"]
    channel_name = me["items"][0]["snippet"]["title"]
    if channel_id != MZ_CHANNEL_ID:
        raise ValueError(
            f"TOKEN MISMATCH: expected MZ channel {MZ_CHANNEL_ID} "
            f"but token is bound to {channel_name} ({channel_id})"
        )
    print(f"  🔑 Uploading as: {channel_name} ({channel_id})")

    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "tags":        tags[:15],
            "categoryId":  "25",  # News & Politics
        },
        "status": {
            "privacyStatus":           "private",  # Matt reviews before publishing
            "selfDeclaredMadeForKids": False,
        }
    }

    media = MediaFileUpload(str(video_path), mimetype="video/mp4",
                            resumable=True, chunksize=5 * 1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  ⬆️  Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    studio_url = f"https://studio.youtube.com/video/{video_id}/edit"

    # Upload thumbnail if available
    if thumb_path and thumb_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
            ).execute()
            print("  ✅ Thumbnail uploaded")
        except Exception as e:
            print(f"  ⚠️  Thumbnail upload failed: {e}")

    print(f"  ✅ Uploaded (PRIVATE): {video_url}")
    return video_url, studio_url


def send_review_email(title: str, video_url: str, studio_url: str,
                      topic: str, duration_sec: float) -> None:
    """Email Matt with the Studio link for review."""
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    if not password:
        print("  ⚠️  GMAIL_APP_PASSWORD not set — skipping email notification")
        return

    duration_str = f"{int(duration_sec // 60)}:{int(duration_sec % 60):02d}"
    ts = datetime.now(ZoneInfo("America/Chicago")).strftime("%b %d, %Y at %I:%M %p CT")

    subject = f"[MZ Long-Form Ready] {title}"
    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #1a1a2e;">📹 New Long-Form Ready for Review</h2>
    <p style="color: #666;">Generated {ts} | Duration: {duration_str}</p>
    <hr>
    <h3>{title}</h3>
    <p><strong>Topic:</strong> {topic}</p>
    <p>The video has been uploaded as <strong>PRIVATE</strong> to the Minute Zero channel.
    Review it in YouTube Studio and flip to public (or schedule) when you're happy with it.</p>
    <p>
      <a href="{studio_url}" style="background:#ff0000;color:white;padding:12px 24px;
         text-decoration:none;border-radius:4px;display:inline-block;margin-right:10px;">
        ▶ Review in YouTube Studio
      </a>
      <a href="{video_url}" style="background:#333;color:white;padding:12px 24px;
         text-decoration:none;border-radius:4px;display:inline-block;">
        🔗 Direct Video Link
      </a>
    </p>
    <hr>
    <p style="color: #999; font-size: 12px;">Minute Zero Auto-Post System</p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = NOTIFY_EMAIL
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(NOTIFY_EMAIL, password)
            server.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"  📧 Review email sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"  ⚠️  Email failed: {e}")


def log_to_sheets(title: str, url: str, topic: str) -> None:
    """Log to Google Sheets Auto-Post Log with status Private."""
    if not os.getenv("GITHUB_ACTIONS"):
        return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds_json = os.getenv("GOOGLE_SHEETS_KEY")
        if not creds_json:
            return
        creds = service_account.Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        ts = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")
        row = [ts, "Minute Zero (Long-Form)", title, "Private - Pending Review", url, ""]
        service.spreadsheets().values().append(
            spreadsheetId="1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI",
            range="Auto-Post Log!A:G",
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()
        print(f"  📊 Logged to Sheets: {title}")
    except Exception as e:
        print(f"  ⚠️  Sheets logging failed: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="MZ Long-Form Auto-Post")
    parser.add_argument("--topic", default="", help="Override topic string")
    parser.add_argument("--dry-run", action="store_true", help="Render only, skip upload")
    args = parser.parse_args()

    print(f"\n{'═' * 60}")
    print(f"  📹 MZ Long-Form  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═' * 60}")

    # Pick topic
    topic = args.topic.strip() if args.topic else pick_topic()
    print(f"\n📖 Topic: {topic}")

    # Generate script
    print(f"\n✍️  Generating long-form script...")
    try:
        script_data = generate_script(topic)
    except ValueError as e:
        err = str(e)
        if err.startswith("VALIDATION_SKIP"):
            print(f"\n⏭️  SKIPPED (validation): {err}")
            print("   No video posted. This is expected behavior.")
            log_to_sheets(f"[SKIPPED] {err[16:100]}", "", topic)
            return 0
        raise

    title = script_data["title"]
    word_count = len(script_data.get("script", "").split())
    print(f"  ✅ Title: {title}")
    print(f"  ✅ Words: {word_count}")

    # Render video
    print(f"\n🎬 Rendering 16:9 landscape video...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_dir = OUTPUT_DIR / datetime.now().strftime("%Y-%m-%d")
    render_result = render_longform_video(script_data, date_dir)

    if args.dry_run:
        print(f"\n⏹️  Dry run — skipping upload.")
        print(f"  Video: {render_result['video_path']}")
        return 0

    # Upload to YouTube (private)
    print(f"\n📤 Uploading to YouTube (PRIVATE)...")
    description = script_data.get("description", f"{title}\n\n#MinuteZero #BusinessHistory")
    tags        = script_data.get("tags", ["minute zero", "business failure", "corporate history"])
    video_url, studio_url = upload_to_youtube(
        render_result["video_path"], title, description, tags,
        render_result.get("thumb_path")
    )

    # Log + notify
    mark_posted(topic, title, video_url)
    log_to_sheets(title, video_url, topic)
    send_review_email(title, video_url, studio_url, topic, render_result["duration_sec"])

    print(f"\n{'═' * 60}")
    print(f"  ✅ DONE — Uploaded PRIVATE")
    print(f"  Title   : {title}")
    print(f"  Duration: {render_result['duration_sec']/60:.1f} min")
    print(f"  Review  : {studio_url}")
    print(f"{'═' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
