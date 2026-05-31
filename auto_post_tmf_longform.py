#!/usr/bin/env python3
"""
auto_post_tmf_longform.py — The Mind Files Long-Form (8–10 min) Auto-Post
══════════════════════════════════════════════════════════════════════════
Generates, renders, and uploads a private 16:9 YouTube video for The Mind Files.
Sends an email notification to Matt confirming what was posted.
Runs automatically Mon/Wed/Fri at 9 AM CT via tmf-longform.yml.

Usage:
    python3 auto_post_tmf_longform.py
    python3 auto_post_tmf_longform.py --topic "Why you stay loyal to people who hurt you"
    python3 auto_post_tmf_longform.py --dry-run   # render only, skip upload
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
BASE_DIR        = Path(__file__).parent
TMF_CHANNEL_DIR = BASE_DIR / "TMF_Channel"
TMF_LONGFORM_PROMPT = TMF_CHANNEL_DIR / "TMF_Longform_Prompt_v1.md"
LOG_FILE        = BASE_DIR / "auto_post_log.json"
OUTPUT_DIR      = BASE_DIR / "TMF_Longform_Output"

# ── Config ────────────────────────────────────────────────────────────────────
TMF_CHANNEL_ID  = "UC0O6KbbHKW4_a7d9epNo93A"
TOKEN_FILE      = BASE_DIR / "youtube_token_tmf.json"
YT_SCOPES       = ["https://www.googleapis.com/auth/youtube.upload",
                   "https://www.googleapis.com/auth/youtube"]
# Create this playlist manually in YouTube Studio first, then paste the ID here
TMF_LONGFORM_PLAYLIST_ID = os.getenv("TMF_LONGFORM_PLAYLIST_ID", "")
NOTIFY_EMAIL    = "wisseinc@gmail.com"

# Word targets: 1400–1700w at 2.5 wps = ~9.3–11.3 min (guarantees 8-min mid-roll threshold)
WORD_MIN, WORD_MAX = 1400, 1700

# ── Topic bank ────────────────────────────────────────────────────────────────
# Seed topics — expand from best-performing shorts + proven psychology hooks
LONGFORM_TOPICS = [
    # Tier 1 — expand from proven TMF short performers
    "Why you stay loyal to people who treat you badly — the psychology of intermittent reinforcement",
    "Why you can't stop thinking about the person who rejected you — the scarcity effect and attachment",
    "Why the least competent people are always the most confident — the Dunning-Kruger effect in depth",
    "Why one bad thing erases ten good ones — negativity bias and how it controls every relationship",
    "Why you believe lies you've heard twice — the illusory truth effect and propaganda",
    "Why you can't leave — the full psychology of the sunk cost fallacy",
    "Why you keep picking the same type of person — attachment theory and trauma bonding",
    "Why you remember your failures more than your successes — the brain's negativity default",
    # Tier 2 — dark psychology deep dives
    "Why people stay in cults — the psychology of identity destruction and manufactured belonging",
    "Why good people do terrible things — Milgram's obedience experiments and what they revealed",
    "Why you trust confident people even when they're wrong — the confidence heuristic",
    "Why narcissists are so hard to leave — intermittent reinforcement, trauma bonds, and identity erosion",
    "Why gaslighting works — the neuroscience of self-doubt and manufactured uncertainty",
    "Why you can't read people as well as you think — the accuracy myth in emotion detection",
    "Why you keep secrets from yourself — motivated reasoning and unconscious self-deception",
    "Why loneliness is physically painful — the neuroscience of social rejection",
    # Tier 3 — decision-making and cognition
    "Why you make terrible decisions under pressure — cortisol, tunneling, and the stress blindspot",
    "Why you're more easily manipulated than you think — influence mechanics from Cialdini",
    "Why your memory of the past is mostly fiction — the reconstructive nature of human memory",
    "Why you can't stop doomscrolling — the variable reward schedule and digital compulsion loops",
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


LONGFORM_QUEUE_FILE = BASE_DIR / "tmf_longform_queue.json"


def _load_longform_queue() -> list:
    """Load the short→longform amplification queue (high-performing shorts queued by channel monitor)."""
    if LONGFORM_QUEUE_FILE.exists():
        try:
            return json.loads(LONGFORM_QUEUE_FILE.read_text())
        except Exception:
            pass
    return []


def _save_longform_queue(queue: list) -> None:
    LONGFORM_QUEUE_FILE.write_text(json.dumps(queue, indent=2))


def pick_topic() -> str:
    """Pick a long-form topic.

    Priority order:
    1. Short→Longform queue (high-performing TMF Shorts queued by daily monitor)
    2. Random from LONGFORM_TOPICS bank (excluding already-used topics).
    """
    # ── Priority 1: amplification queue ───────────────────────────────────────
    queue = _load_longform_queue()
    pending = [item for item in queue if item.get("status") == "pending"]
    if pending:
        best = max(pending, key=lambda x: x.get("views", 0))
        print(f"  🚀 Longform queue hit! Amplifying short-form breakout: {best.get('title', '')[:60]}")
        print(f"     Views: {best.get('views', 0)}")
        for item in queue:
            if item.get("topic") == best.get("topic"):
                item["status"] = "used"
        _save_longform_queue(queue)
        return best.get("topic", "")

    # ── Priority 2: random from topic bank ────────────────────────────────────
    log = _load_log()
    used = set(log.get("tmf_longform_topics_used", []))
    available = [t for t in LONGFORM_TOPICS if t not in used]
    if not available:
        print("  🔄 All long-form topics used — resetting cycle")
        log["tmf_longform_topics_used"] = []
        _save_log(log)
        available = LONGFORM_TOPICS[:]
    return random.choice(available)


def mark_posted(topic: str, title: str, url: str) -> None:
    log = _load_log()
    used = log.get("tmf_longform_topics_used", [])
    if topic not in used:
        used.append(topic)
    log["tmf_longform_topics_used"] = used
    posts = log.get("tmf_longform_posts", [])
    ts = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")
    posts.append({"timestamp": ts, "topic": topic, "title": title, "url": url, "status": "private"})
    log["tmf_longform_posts"] = posts
    _save_log(log)


def load_system_prompt() -> str:
    """Extract the system prompt from the TMF longform prompt file."""
    text = TMF_LONGFORM_PROMPT.read_text()
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
        raise ValueError("Could not extract system prompt from TMF_Longform_Prompt_v1.md")
    return "\n".join(lines)


def longform_title_ok(title: str) -> tuple[bool, str]:
    """Enforce 'Why You' / 'Why Your' opener."""
    t = (title or "").strip()
    if len(t) < 10:
        return False, "title too short"
    if len(t) > 70:
        return False, f"title too long ({len(t)} chars)"
    t_lower = t.lower()
    if not (t_lower.startswith("why you") or t_lower.startswith("why your")):
        return False, "must start with 'Why You' or 'Why Your'"
    return True, ""


def generate_script(topic: str) -> dict:
    """
    Two-step generation:
    Step 1 — Write the narration as plain prose (Claude writes long text naturally).
    Step 2 — Wrap the validated script into the full JSON metadata package.
    """

    PROSE_SYSTEM = (
        "You are the scriptwriter for 'The Mind Files' — a YouTube channel about the hidden psychological "
        "forces that drive human behavior. Why people lie, manipulate, stay loyal to abusers, and make "
        "decisions that destroy them. "
        "Voice: calm, intelligent, slightly unsettling. Like a professor who knows too much. "
        "Narration-only. No host. No first person. Address viewer as 'you' throughout. "
        "Short punchy sentences mixed with longer explanatory ones. "
        "Facts feel like revelations, not lectures. Never moralize. US English."
    )

    PROSE_USER = (
        f"Write a complete 8–10 minute psychology documentary narration about: {topic}\n\n"
        f"Use this exact 5-act structure. Write ONLY the narration prose — no labels, no act headings, "
        f"no JSON, no markdown. Just the continuous spoken narration.\n\n"
        f"REQUIRED word counts per act (total must be 1,400–1,700 words):\n"
        f"  Act 1 — THE HOOK (110–130 words): Open on a shocking statement or uncomfortable question "
        f"the viewer cannot immediately answer. First sentence must create immediate personal recognition — "
        f"the viewer thinks 'wait, that's me.' Do NOT open with a named psychological effect. Open with behavior. "
        f"End with a one-sentence question that locks the viewer in.\n\n"
        f"  Act 2 — THE SETUP (260–290 words): Establish the behavior pattern with 2-3 concrete "
        f"real-world examples across different contexts (relationships, work, self-perception). "
        f"Introduce the psychology research: name the researchers, the study, the year. "
        f'End with: "And the reason this happens is stranger than you think."\n\n'
        f"  Act 3 — THE MECHANISM (380–420 words): Explain exactly why this behavior exists at the "
        f"neurological or evolutionary level. Use real studies with precise details — sample size, "
        f"what participants did, what the numbers showed. Show the internal logic of the brain. "
        f"Make the viewer feel the mechanism happening in their own mind.\n\n"
        f"  Act 4 — THE COST (360–400 words): What does this behavior cost people in real life? "
        f"Follow 2-3 archetypal scenarios the viewer recognizes. Include one where the person doing "
        f"the behavior is the last to realize it. Tone: quiet recognition, slightly uncomfortable. "
        f'End with: "Which raises the question — can any of this actually change?"\n\n'
        f"  Act 5 — THE REFRAME (360–400 words): What does understanding this mechanism actually give you? "
        f"Not a fix — a different lens. Show how awareness shifts what's possible. Connect to something "
        f"universal about being human. Final sentence must be 8–12 words, punchy, slightly uncomfortable. "
        f"Not motivational. A truth that lingers.\n\n"
        f"Use 'you' at least 8 times across the full narration. "
        f"Write all 1,400–1,700 words now. Do NOT summarize. Do NOT compress. "
        f"Expand every beat with specific details, research, and human moments."
    )

    def _call_prose_anthropic(extra: str = "") -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=6000,
            system=PROSE_SYSTEM,
            messages=[{"role": "user", "content": PROSE_USER + extra}],
        )
        return resp.content[0].text.strip()

    def _call_prose_openai(extra: str = "") -> str:
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": PROSE_SYSTEM},
                {"role": "user",   "content": PROSE_USER + extra},
            ],
            max_tokens=6000,
            temperature=0.75,
        )
        return resp.choices[0].message.content.strip()

    def _get_prose(extra: str = "") -> str:
        try:
            print("    Calling Anthropic Claude (prose)...")
            return _call_prose_anthropic(extra)
        except Exception as e:
            print(f"    Anthropic failed ({e}) — falling back to OpenAI GPT-4o...")
            return _call_prose_openai(extra)

    # Retry loop on prose length
    narration = ""
    for attempt in range(1, 4):
        print(f"  Attempt {attempt}/3 (narration)...")
        narration = _get_prose(
            "" if attempt == 1 else (
                f"\n\nYour previous draft was {len(narration.split())} words — "
                f"REJECTED. Must be 1,400–1,700 words. "
                f"Write more for EVERY act: Act 1: 120w, Act 2: 275w, "
                f"Act 3: 400w, Act 4: 380w, Act 5: 380w. "
                f"Add more specific research details, examples, and human moments."
            )
        )
        wc = len(narration.split())
        print(f"    Word count: {wc}")
        if WORD_MIN <= wc <= WORD_MAX:
            print(f"  ✅ Narration passed ({wc}w)")
            break
        print(
            f"  ⚠️  LENGTH FAIL attempt {attempt}: {wc} words. "
            f"Must be {WORD_MIN}–{WORD_MAX}."
        )
        if attempt == 3:
            raise ValueError(
                f"VALIDATION_SKIP: all 3 attempts failed — last narration: {wc}w"
            )

    # ── Step 2: Build full JSON metadata from the validated prose ────────────
    words = narration.split()
    total_words = len(words)
    act1_end_w  = min(120, int(total_words * 0.08))
    act2_end_w  = act1_end_w  + int(total_words * 0.19)
    act3_end_w  = act2_end_w  + int(total_words * 0.28)
    act4_end_w  = act3_end_w  + int(total_words * 0.27)

    def _w_to_ts(w: int) -> str:
        secs = int(w / 2.5)
        return f"{secs // 60}:{secs % 60:02d}"

    ts1 = _w_to_ts(0)
    ts2 = _w_to_ts(act1_end_w)
    ts3 = _w_to_ts(act2_end_w)
    ts4 = _w_to_ts(act3_end_w)
    ts5 = _w_to_ts(act4_end_w)

    system_full = load_system_prompt()
    json_user = (
        f"Topic: {topic}\n\n"
        f"Here is the complete narration script ({total_words} words):\n\n"
        f"{narration}\n\n"
        f"Produce the YouTube metadata JSON for this video. Rules:\n\n"
        f"TITLE:\n"
        f"- MUST start with 'Why You' or 'Why Your'\n"
        f"- Describes an OBSERVABLE BEHAVIOR the viewer recognizes in themselves\n"
        f"- Max 60 characters. No colons unless the behavior comes first.\n"
        f"- GOOD: 'Why You Stay Loyal to Mean People' / 'Why You Believe Lies You've Heard Twice'\n"
        f"- BAD: 'The Dark Psychology of...' / 'Cognitive Dissonance Explained'\n\n"
        f"DESCRIPTION (150-200 words):\n"
        f"- First sentence: the gut-punch behavior or stat from the video\n"
        f"- Do NOT start with channel name, 'In this video', or 'Discover how'\n"
        f"- Lead with the uncomfortable truth. Then explain why this video matters.\n"
        f"- After the prose, add chapter timestamps on their own lines:\n"
        f"\n"
        f"{ts1} The Hook\n"
        f"{ts2} The Setup\n"
        f"{ts3} The Mechanism\n"
        f"{ts4} The Cost\n"
        f"{ts5} The Reframe\n"
        f"\n"
        f"- After timestamps, add hashtags on their own line. Always include "
        f"#psychology #darkpsychology, then pick 2-4 from: #humanbehavior #mentalhealth "
        f"#mindset #manipulation #narcissism #cognitivebiases #brainscience #relationships #selfawareness\n\n"
        f"TAGS (array, 12-15 tags):\n"
        f"- Include: psychology, dark psychology, human behavior, mind files, why you, "
        f"plus topic-specific terms\n\n"
        f"THUMBNAIL_TEXT: 3-5 words ALL CAPS, provocative, works on a dark cinematic photo\n\n"
        f"PEXELS_QUERIES: 12-16 landscape b-roll queries — cinematic, moody, people-focused. "
        f"Include queries for: lone person in dramatic lighting, close-up hands or face, "
        f"dark atmospheric environments. These should feel like film stills, not stock photos.\n\n"
        f"Return ONLY valid JSON with these fields: title, description, tags, "
        f"thumbnail_text, pexels_queries, act_breaks\n"
        f"act_breaks = {{act1_end_word: {act1_end_w}, act2_end_word: {act2_end_w}, "
        f"act3_end_word: {act3_end_w}, act4_end_word: {act4_end_w}}}\n"
        f"No markdown, no explanation."
    )

    def _call_json_openai(sys: str, usr: str) -> dict:
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": sys},
                      {"role": "user",   "content": usr}],
            max_tokens=3000,
            temperature=0.5,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    def _call_json_anthropic(sys: str, usr: str) -> dict:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            system=sys,
            messages=[{"role": "user", "content": usr}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    print("  📋 Building JSON metadata...")
    try:
        print("    Calling OpenAI GPT-4o (JSON)...")
        data = _call_json_openai(system_full, json_user)
    except Exception as e:
        print(f"    OpenAI JSON failed ({e}) — falling back to Anthropic...")
        data = _call_json_anthropic(system_full, json_user)

    data["script"] = narration

    title = (data.get("title") or "").strip()
    title_ok, title_reason = longform_title_ok(title)
    if not title_ok:
        raise ValueError(
            f"VALIDATION_SKIP: title failed — {title_reason} (title: \"{title}\")"
        )

    word_count = len(narration.split())
    print(f"  ✅ Script passed validators ({word_count}w, title OK: {title})")
    return data


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
    title       = script_data.get("title", "The Mind Files")
    queries     = script_data.get("pexels_queries", [])

    # ── 1. Generate narration audio ───────────────────────────────────────────
    print("  🎙️  Generating narration audio...")
    audio_path = out_dir / f"{video_id}_narration.mp3"
    # Guy Neural: deep, calm, authoritative — fits TMF's "professor who knows too much" tone
    tts_voice  = os.getenv("TMF_LONGFORM_VOICE", "en-US-GuyNeural")

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
    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    clip_paths = []

    if pexels_key and queries:
        import requests
        dedup_file = BASE_DIR / "pexels_used_tmf_longform.json"
        used_ids = set(json.loads(dedup_file.read_text()) if dedup_file.exists() else [])

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
                fresh = [v for v in videos if v["id"] not in used_ids]
                if not fresh:
                    fresh = videos
                if not fresh:
                    continue

                vid = fresh[0]
                files = [f for f in vid.get("video_files", []) if f.get("quality") in ("hd", "sd")]
                files = [f for f in files if (f.get("width", 0) / max(f.get("height", 1), 1)) > 1.5]
                files.sort(key=lambda f: abs(f.get("width", 0) - 1920))
                if not files:
                    continue

                clip_url  = files[0]["link"]
                clip_path = out_dir / f"clip_{i:02d}.mp4"
                r = requests.get(clip_url, timeout=30)
                clip_path.write_bytes(r.content)

                trimmed = out_dir / f"clip_{i:02d}_trim.mp4"
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(clip_path),
                    "-t", str(clip_duration),
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-r", "30",
                    "-an", str(trimmed)
                ], capture_output=True)
                clip_paths.append(trimmed)
                used_ids.add(vid["id"])
                print(f"    ✅ Clip {i+1}: {query[:40]}")
            except Exception as e:
                print(f"    ⚠️  Clip {i+1} failed ({query[:30]}): {e}")

        dedup_file.write_text(json.dumps(list(used_ids), indent=2))

    # ── 4. Build video ────────────────────────────────────────────────────────
    print("  🎞️  Compositing final video...")
    output_path = out_dir / f"{video_id}_longform.mp4"

    if clip_paths:
        clips_needed = int(duration_sec / max(clip_duration, 1)) + 2
        if len(clip_paths) < clips_needed:
            repeats = (clips_needed // len(clip_paths)) + 1
            extended = (clip_paths * repeats)[:clips_needed]
            print(f"  🔁 Extending {len(clip_paths)} clips → {len(extended)} to cover {duration_sec:.0f}s")
        else:
            extended = clip_paths

        concat_file = out_dir / "concat.txt"
        concat_file.write_text("\n".join(f"file '{p.resolve()}'" for p in extended))
        backdrop = out_dir / "backdrop.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-t", str(duration_sec),
            "-c:v", "copy",
            str(backdrop)
        ], capture_output=True)
    else:
        # Fallback: very dark almost-black background (fits TMF aesthetic)
        backdrop = out_dir / "backdrop.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=0x080810:size=1920x1080:duration={duration_sec}:rate=30",
            "-c:v", "libx264", "-preset", "ultrafast",
            str(backdrop)
        ], capture_output=True)

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(backdrop),
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac",
        "-t", str(duration_sec),
        str(output_path)
    ], capture_output=True)

    print(f"  ✅ Video: {output_path.name}")

    # ── 5. Generate thumbnail (dark cinematic Pexels photo + text overlay) ────
    thumb_path = out_dir / f"{video_id}_thumb.jpg"
    try:
        import requests as _req
        from io import BytesIO
        from PIL import ImageFont, ImageFilter

        thumb_text = script_data.get("thumbnail_text", title[:40].upper())
        queries    = script_data.get("pexels_queries", [])

        # TMF thumbnail: dark, moody, cinematic — person in dramatic lighting
        moody_queries = [f"cinematic dark {q}" for q in queries[:3]] + queries[3:]

        bg = None
        if pexels_key and moody_queries:
            for q in moody_queries[:6]:
                try:
                    r = _req.get(
                        "https://api.pexels.com/v1/search",
                        headers={"Authorization": pexels_key},
                        params={"query": q, "orientation": "landscape",
                                "per_page": 5, "size": "large"},
                        timeout=10,
                    )
                    photos = r.json().get("photos", [])
                    if photos:
                        pick = abs(hash(title)) % len(photos)
                        photo_url = photos[pick]["src"]["large"]
                        img_r = _req.get(photo_url, timeout=20)
                        bg = Image.open(BytesIO(img_r.content)).convert("RGB")
                        print(f"  📸 Thumbnail photo: {q[:45]}")
                        break
                except Exception:
                    continue

        if bg is None:
            bg = Image.new("RGB", (1280, 720), (8, 8, 16))
            print("  📸 Thumbnail: using dark fallback background")

        # Scale to 1280×720
        bg_w, bg_h = bg.size
        scale = max(1280 / bg_w, 720 / bg_h)
        new_w, new_h = int(bg_w * scale), int(bg_h * scale)
        bg = bg.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - 1280) // 2
        top  = (new_h - 720)  // 2
        bg   = bg.crop((left, top, left + 1280, top + 720))

        # Slight blur
        bg = bg.filter(ImageFilter.GaussianBlur(radius=1.5))

        # Heavy dark overlay — TMF needs darker than MZ (more sinister aesthetic)
        dark_layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 130))
        bg = Image.alpha_composite(bg.convert("RGBA"), dark_layer)

        # Deep purple-black gradient at bottom (TMF color language)
        overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        grad_top = 200
        for y in range(grad_top, 720):
            t = (y - grad_top) / (720 - grad_top)
            alpha = int(210 * t)
            r_val = int(20 * t)
            g_val = 0
            b_val = int(40 * t)  # subtle purple tint
            ov_draw.rectangle([(0, y), (1280, y + 1)], fill=(r_val, g_val, b_val, alpha))
        bg = Image.alpha_composite(bg, overlay).convert("RGB")

        # Font
        draw = ImageDraw.Draw(bg)
        font_large = font_small = None
        for fp in [
            "/Library/Fonts/Impact.ttf",
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/usr/local/share/fonts/Oswald-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]:
            try:
                font_large = ImageFont.truetype(fp, size=120)
                font_small = ImageFont.truetype(fp, size=95)
                break
            except Exception:
                continue
        if font_large is None:
            font_large = font_small = ImageFont.load_default()

        words_t = thumb_text.split()
        mid   = max(1, len(words_t) // 2)
        line1 = " ".join(words_t[:mid])
        line2 = " ".join(words_t[mid:]) if len(words_t) > 1 else ""

        def _outlined(draw, x, y, text, font, fill, stroke_fill=(0, 0, 0), stroke_w=7):
            draw.text((x, y), text, font=font, fill=fill,
                      anchor="mm", stroke_width=stroke_w, stroke_fill=stroke_fill)

        if line2:
            # White line 1, purple-tinted line 2 — TMF palette
            _outlined(draw, 640, 565, line1, font_large, fill=(255, 255, 255))
            _outlined(draw, 640, 660, line2, font_small,  fill=(180, 100, 255))
        else:
            _outlined(draw, 640, 620, line1, font_large, fill=(255, 255, 255))

        bg.save(str(thumb_path), quality=95)
        print(f"  ✅ Thumbnail: {thumb_path.name}")
    except Exception as e:
        print(f"  ⚠️  Thumbnail generation failed: {e}")

    return {
        "video_path": output_path,
        "thumb_path": thumb_path,
        "duration_sec": duration_sec,
        "video_id": video_id,
    }


def _format_description(desc: str) -> str:
    """Enforce YouTube chapter and hashtag formatting rules."""
    import re
    lines = desc.splitlines()
    prose_lines = []
    timestamp_lines = []
    hashtag_line = ""
    ts_pattern = re.compile(r"^\s*(\d{1,2}:\d{2})\s+(.+)$")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or re.match(r"^(#\w+\s*)+$", stripped):
            hashtag_line = stripped
            continue
        inline_ts = re.findall(r"(\d{1,2}:\d{2})\s+([A-Za-z][A-Za-z\s]+?)(?=\s+\d{1,2}:\d{2}|$)", stripped)
        if inline_ts and len(inline_ts) >= 2:
            for ts, label in inline_ts:
                timestamp_lines.append(f"{ts} {label.strip()}")
            continue
        if ts_pattern.match(stripped):
            timestamp_lines.append(stripped)
            continue
        if "#" in stripped:
            parts = re.split(r"\s+(#\w)", stripped, maxsplit=1)
            if len(parts) > 1:
                prose_lines.append(parts[0].strip())
                hashtag_line = "#" + parts[1] + (parts[2] if len(parts) > 2 else "")
            else:
                prose_lines.append(stripped)
            continue
        prose_lines.append(stripped)

    parts = []
    if prose_lines:
        parts.append("\n".join(prose_lines))
    if timestamp_lines:
        parts.append("\n".join(timestamp_lines))
    if hashtag_line:
        parts.append(hashtag_line)
    return "\n\n".join(parts)


def upload_to_youtube(video_path: Path, title: str, description: str,
                      tags: list, thumb_path: Path | None = None) -> tuple[str, str]:
    """Upload as PUBLIC. Returns (video_url, studio_url)."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token_data = json.loads(TOKEN_FILE.read_text())
    creds = Credentials.from_authorized_user_info(token_data, YT_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)

    # Verify channel identity
    me = youtube.channels().list(part="id,snippet", mine=True).execute()
    channel_id   = me["items"][0]["id"]
    channel_name = me["items"][0]["snippet"]["title"]
    if channel_id != TMF_CHANNEL_ID:
        raise ValueError(
            f"TOKEN MISMATCH: expected TMF channel {TMF_CHANNEL_ID} "
            f"but token is bound to {channel_name} ({channel_id})"
        )
    print(f"  🔑 Uploading as: {channel_name} ({channel_id})")

    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "tags":        tags[:15],
            "categoryId":  "27",  # Education
        },
        "status": {
            "privacyStatus":           "public",
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

    video_id_yt  = response["id"]
    video_url    = f"https://www.youtube.com/watch?v={video_id_yt}"
    studio_url   = f"https://studio.youtube.com/video/{video_id_yt}/edit"

    if thumb_path and thumb_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id_yt,
                media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
            ).execute()
            print("  ✅ Thumbnail uploaded")
        except Exception as e:
            print(f"  ⚠️  Thumbnail upload failed: {e}")

    # Add to TMF long-form playlist (if playlist ID is configured)
    if TMF_LONGFORM_PLAYLIST_ID:
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={"snippet": {
                    "playlistId": TMF_LONGFORM_PLAYLIST_ID,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id_yt},
                }}
            ).execute()
            print(f"  ✅ Added to TMF long-form playlist")
        except Exception as e:
            print(f"  ⚠️  Playlist add failed: {e}")
    else:
        print("  ℹ️  TMF_LONGFORM_PLAYLIST_ID not set — skipping playlist")

    print(f"  ✅ Uploaded (PUBLIC): {video_url}")
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

    subject = f"[TMF Long-Form — PUBLIC] {title}"
    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #1a0a2e;">🧠 New Long-Form Posted — The Mind Files</h2>
    <p style="color: #666;">Generated {ts} | Duration: {duration_str} | Status: <strong>PUBLIC</strong></p>
    <hr>
    <h3>{title}</h3>
    <p><strong>Topic:</strong> {topic}</p>
    <p>The video is live as <strong>PUBLIC</strong>. Review in Studio to edit or adjust.</p>
    <p>
      <a href="{studio_url}" style="background:#6a0dad;color:white;padding:12px 24px;
         text-decoration:none;border-radius:4px;display:inline-block;margin-right:10px;">
        📊 Review in Studio
      </a>
      <a href="{video_url}" style="background:#333;color:white;padding:12px 24px;
         text-decoration:none;border-radius:4px;display:inline-block;">
        ▶ Preview on YouTube
      </a>
    </p>
    <hr>
    <p style="color: #999; font-size: 12px;">The Mind Files Long-Form Auto-Post System</p>
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
    """Log to Google Sheets Auto-Post Log."""
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
        row = [ts, "The Mind Files (Long-Form)", title, "Private - Pending Review", url, ""]
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
    parser = argparse.ArgumentParser(description="TMF Long-Form Auto-Post")
    parser.add_argument("--topic", default="", help="Override topic string")
    parser.add_argument("--dry-run", action="store_true", help="Render only, skip upload")
    args = parser.parse_args()

    print(f"\n{'═' * 60}")
    print(f"  🧠 TMF Long-Form  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'═' * 60}")

    topic = args.topic.strip() if args.topic else pick_topic()
    print(f"\n📖 Topic: {topic}")

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

    title      = script_data["title"]
    word_count = len(script_data.get("script", "").split())
    print(f"  ✅ Title: {title}")
    print(f"  ✅ Words: {word_count}")

    print(f"\n🎬 Rendering 16:9 landscape video...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_dir = OUTPUT_DIR / datetime.now().strftime("%Y-%m-%d")
    render_result = render_longform_video(script_data, date_dir)

    if args.dry_run:
        print(f"\n⏹️  Dry run — skipping upload.")
        print(f"  Video: {render_result['video_path']}")
        return 0

    print(f"\n📤 Uploading to YouTube (PUBLIC)...")
    description = script_data.get("description", f"{title}\n\n#psychology #darkpsychology")
    description = _format_description(description)
    tags        = script_data.get("tags", ["psychology", "dark psychology", "human behavior"])
    video_url, studio_url = upload_to_youtube(
        render_result["video_path"], title, description, tags,
        render_result.get("thumb_path")
    )

    mark_posted(topic, title, video_url)
    log_to_sheets(title, video_url, topic)
    send_review_email(title, video_url, studio_url, topic, render_result["duration_sec"])

    print(f"\n{'═' * 60}")
    print(f"  ✅ DONE — Uploaded PUBLIC and live")
    print(f"  Title   : {title}")
    print(f"  Duration: {render_result['duration_sec']/60:.1f} min")
    print(f"  Review  : {studio_url}")
    print(f"{'═' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
