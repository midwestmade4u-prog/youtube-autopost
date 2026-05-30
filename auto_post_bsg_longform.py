#!/usr/bin/env python3
"""
auto_post_bsg_longform.py — Bible Story Garden Long-Form (7–9 min) Auto-Post
═════════════════════════════════════════════════════════════════════════════
Generates, renders, and uploads a public 16:9 YouTube video for Bible Story Garden.
Sends an email notification to Matt confirming what was posted.
Runs automatically Sun/Tue/Fri per bsg-longform.yml.

Usage:
    python3 auto_post_bsg_longform.py
    python3 auto_post_bsg_longform.py --topic "Moses and the Burning Bush"
    python3 auto_post_bsg_longform.py --dry-run   # render only, skip upload
"""

import argparse
import json
import os
import random
import smtplib
import subprocess
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
BSG_CHANNEL_DIR = BASE_DIR / "BSG_Channel"
BSG_LONGFORM_PROMPT = BSG_CHANNEL_DIR / "BSG_Longform_Prompt_v1.md"
LOG_FILE        = BASE_DIR / "auto_post_log.json"
OUTPUT_DIR      = BASE_DIR / "BSG_Longform_Output"

# ── Config ────────────────────────────────────────────────────────────────────
BSG_CHANNEL_ID  = "UCcyBf84Mc-evMSYZlqh3zVA"
TOKEN_FILE      = BASE_DIR / "youtube_token_bsg.json"
YT_SCOPES       = ["https://www.googleapis.com/auth/youtube.upload",
                   "https://www.googleapis.com/auth/youtube"]
BSG_LONGFORM_PLAYLIST_ID = os.getenv("BSG_LONGFORM_PLAYLIST_ID", "PLWwJ5gjyjteowfCIsBJ-9UuoMd-12I3Jg")
NOTIFY_EMAIL    = "wisseinc@gmail.com"

# Word targets: 1,100–1,400w at 2.5 wps = ~7.3–9.3 min
WORD_MIN, WORD_MAX = 1100, 1400

# ── Topic bank ────────────────────────────────────────────────────────────────
LONGFORM_TOPICS = [
    # Old Testament — foundational stories
    "Noah and the Flood: the man who believed when no one else did",
    "Abraham and Isaac: the sacrifice on Mount Moriah",
    "Joseph and the Coat of Many Colors: betrayal, slavery, and redemption",
    "Moses and the Burning Bush: the day God called an unlikely man",
    "The Exodus: the night everything changed for Israel",
    "Moses parts the Red Sea: faith at the water's edge",
    "David and Goliath: the shepherd boy who changed everything",
    "Elijah and the prophets of Baal: the showdown on Mount Carmel",
    "Jonah and the whale: the prophet who ran from God",
    "Daniel in the lion's den: a man who would not bow",
    "Shadrach, Meshach, and Abednego: the fire that could not burn them",
    "Esther: the queen who risked everything to save her people",
    "Ruth and Naomi: loyalty that crossed every boundary",
    "Samson and Delilah: strength, betrayal, and final redemption",
    "Solomon's wisdom: the king who asked for the right thing",
    # New Testament — life of Jesus
    "The Birth of Jesus: the night the world changed forever",
    "Jesus feeds five thousand: a miracle in the wilderness",
    "Jesus walks on water: the moment Peter stepped out of the boat",
    "The Prodigal Son: the parable of coming home",
    "Lazarus raised from the dead: the miracle that changed everything",
    "The Last Supper: the final meal before the storm",
    "The Crucifixion: the darkest day that became the greatest story",
    "The Resurrection: the morning that rewrote history",
    # New Testament — early church
    "Paul on the road to Damascus: the most dramatic conversion in history",
    "Peter and Cornelius: the vision that opened the church to the world",
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


LONGFORM_QUEUE_FILE = BASE_DIR / "bsg_longform_queue.json"


def _load_longform_queue() -> list:
    if LONGFORM_QUEUE_FILE.exists():
        try:
            return json.loads(LONGFORM_QUEUE_FILE.read_text())
        except Exception:
            pass
    return []


def _save_longform_queue(queue: list) -> None:
    LONGFORM_QUEUE_FILE.write_text(json.dumps(queue, indent=2))


def pick_topic() -> str:
    queue = _load_longform_queue()
    pending = [item for item in queue if item.get("status") == "pending"]
    if pending:
        best = max(pending, key=lambda x: x.get("views", 0))
        print(f"  🌿 Queue hit! Amplifying short breakout: {best.get('title', '')[:60]}")
        for item in queue:
            if item.get("topic") == best.get("topic"):
                item["status"] = "used"
        _save_longform_queue(queue)
        return best.get("topic", "")

    log = _load_log()
    used = set(log.get("bsg_longform_topics_used", []))
    available = [t for t in LONGFORM_TOPICS if t not in used]
    if not available:
        print("  🔄 All long-form topics used — resetting cycle")
        log["bsg_longform_topics_used"] = []
        _save_log(log)
        available = LONGFORM_TOPICS[:]
    return random.choice(available)


def mark_posted(topic: str, title: str, url: str) -> None:
    log = _load_log()
    used = log.get("bsg_longform_topics_used", [])
    if topic not in used:
        used.append(topic)
    log["bsg_longform_topics_used"] = used
    posts = log.get("bsg_longform_posts", [])
    ts = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")
    posts.append({"timestamp": ts, "topic": topic, "title": title, "url": url, "status": "public"})
    log["bsg_longform_posts"] = posts
    _save_log(log)


def load_system_prompt() -> str:
    text = BSG_LONGFORM_PROMPT.read_text()
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
        raise ValueError("Could not extract system prompt from BSG_Longform_Prompt_v1.md")
    return "\n".join(lines)


def longform_title_ok(title: str) -> tuple[bool, str]:
    t = (title or "").strip()
    if len(t) < 10:
        return False, "title too short"
    if len(t) > 75:
        return False, f"title too long ({len(t)} chars)"
    # BSG titles should name a Bible character or event
    banned_openers = ("why ", "how ", "the hidden", "the dark", "the secret")
    for b in banned_openers:
        if t.lower().startswith(b):
            return False, f"BSG title should name the story, not start with '{b}'"
    return True, ""


def generate_script(topic: str) -> dict:
    PROSE_SYSTEM = (
        "You are the scriptwriter for 'Bible Story Garden' — a YouTube channel that brings Bible stories "
        "to life with warmth, wonder, and narrative depth. You tell the great stories of scripture as "
        "real human stories — with emotion, specific detail, and reverence. "
        "Voice: warm, wonder-filled, reverent. Like a gifted storyteller by a fire. "
        "Narration-only. No host. No first person. Rich sensory detail throughout. "
        "Appropriate for families. US English."
    )

    PROSE_USER = (
        f"Write a complete 7–9 minute Bible story narration about: {topic}\n\n"
        f"Use this exact 4-act structure. Write ONLY the narration prose — no labels, no act headings, "
        f"no JSON, no markdown. Just the continuous spoken narration.\n\n"
        f"REQUIRED word counts per act (total must be 1,100–1,400 words):\n\n"
        f"  Act 1 — THE WORLD (230 words): Open with the world of the story. Paint the setting vividly — "
        f"the land, the era, the people. Introduce the central character(s) with humanity and specificity. "
        f"First sentence should be vivid and immediate. End with the tension or question that drives the story.\n\n"
        f"  Act 2 — THE CONFLICT (390 words): The heart of the story. The challenge, the test, the impossible "
        f"moment. Show the human side — doubt, fear, the cost of the choice. Use specific scripture details: "
        f"names, places, numbers, direct quotes. Slow down the key moment. Stay in the tension — do NOT rush to resolution.\n\n"
        f"  Act 3 — THE TURNING POINT (390 words): The moment of faith, action, or divine intervention. "
        f"Show it with care and reverence. Include the human response — awe, disbelief turning to belief. "
        f"Trace immediate consequences: what changed, who was affected, what it meant.\n\n"
        f"  Act 4 — THE MEANING (280 words): Step back and reflect. What does this story reveal about God, "
        f"faith, and being human? Connect to something universal. Do NOT moralize or give a sermon — offer "
        f"a reflection, not a lesson. Final sentence: beautiful, lingering, quietly powerful. 8–14 words.\n\n"
        f"Rich sensory detail throughout — what people saw, heard, felt. Make the ancient world real. "
        f"Write all 1,100–1,400 words now. Do NOT summarize or compress. Expand every beat with specific "
        f"detail, human emotion, and narrative depth."
    )

    def _call_prose_anthropic(extra: str = "") -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=5000,
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
            max_tokens=5000,
            temperature=0.75,
        )
        return resp.choices[0].message.content.strip()

    def _get_prose(extra: str = "") -> str:
        try:
            print("    Calling Anthropic Claude (prose)...")
            return _call_prose_anthropic(extra)
        except Exception as e:
            print(f"    Anthropic failed ({e}) — falling back to OpenAI...")
            return _call_prose_openai(extra)

    narration = ""
    for attempt in range(1, 4):
        print(f"  Attempt {attempt}/3 (narration)...")
        narration = _get_prose(
            "" if attempt == 1 else (
                f"\n\nYour previous draft was {len(narration.split())} words — "
                f"REJECTED. Must be 1,100–1,400 words. "
                f"Expand every act: Act 1: 230w, Act 2: 390w, Act 3: 390w, Act 4: 280w. "
                f"Add more sensory detail, character emotion, and specific scripture detail."
            )
        )
        wc = len(narration.split())
        print(f"    Word count: {wc}")
        if WORD_MIN <= wc <= WORD_MAX:
            print(f"  ✅ Narration passed ({wc}w)")
            break
        print(f"  ⚠️  LENGTH FAIL attempt {attempt}: {wc} words. Must be {WORD_MIN}–{WORD_MAX}.")
        if attempt == 3:
            raise ValueError(f"VALIDATION_SKIP: all 3 attempts failed — last narration: {wc}w")

    # ── Build timestamps ──────────────────────────────────────────────────────
    words = narration.split()
    total_words = len(words)
    act1_end_w = min(230, int(total_words * 0.17))
    act2_end_w = act1_end_w + int(total_words * 0.29)
    act3_end_w = act2_end_w + int(total_words * 0.29)

    def _w_to_ts(w: int) -> str:
        secs = int(w / 2.5)
        return f"{secs // 60}:{secs % 60:02d}"

    ts1 = _w_to_ts(0)
    ts2 = _w_to_ts(act1_end_w)
    ts3 = _w_to_ts(act2_end_w)
    ts4 = _w_to_ts(act3_end_w)

    system_full = load_system_prompt()
    json_user = (
        f"Topic: {topic}\n\n"
        f"Here is the complete narration script ({total_words} words):\n\n"
        f"{narration}\n\n"
        f"Produce the YouTube metadata JSON for this video. Rules:\n\n"
        f"TITLE:\n"
        f"- Name the Bible story clearly — character and compelling angle\n"
        f"- Format: '[Character/Event]: [What makes this story remarkable]'\n"
        f"- Under 70 characters. Warm, inviting, not clickbait.\n"
        f"- GOOD: 'David and Goliath: The Shepherd Who Changed Everything'\n"
        f"- BAD: 'Why Faith Matters' or 'A Bible Story About Courage'\n\n"
        f"DESCRIPTION (150-200 words):\n"
        f"- First sentence names the story and its central drama warmly and specifically\n"
        f"- Do NOT start with 'In this video' or the channel name\n"
        f"- Warm, inviting tone — like recommending a story to a friend\n"
        f"- After prose, add chapter timestamps on their own lines:\n"
        f"\n"
        f"{ts1} The World\n"
        f"{ts2} The Conflict\n"
        f"{ts3} The Turning Point\n"
        f"{ts4} The Meaning\n"
        f"\n"
        f"- After timestamps, hashtags on their own line. Always include "
        f"#BibleStories #BibleStoryGarden, then 2-4 from: #Faith #Christianity "
        f"#BibleForKids #Scripture #OldTestament #NewTestament #Jesus #God "
        f"#FamilyFaith #Inspirational\n\n"
        f"TAGS (array, 12-15 tags):\n"
        f"- Include: bible stories, bible story garden, [story name], [character names], "
        f"family faith, scripture, plus relevant terms\n\n"
        f"THUMBNAIL_TEXT: 3-5 words ALL CAPS, names the story clearly\n\n"
        f"PEXELS_QUERIES: 12-16 landscape b-roll queries — warm, ancient, natural. "
        f"Think: desert landscapes, stone walls, olive trees, rivers at sunrise, "
        f"candlelight in stone rooms, crowds in ancient markets, sunsets over hills, "
        f"shepherds with sheep, wheat fields, ocean waves, mountain peaks. "
        f"Warm golden tones. No modern imagery.\n\n"
        f"Return ONLY valid JSON with these fields: title, description, tags, "
        f"thumbnail_text, pexels_queries, act_breaks\n"
        f"act_breaks = {{act1_end_word: {act1_end_w}, act2_end_word: {act2_end_w}, "
        f"act3_end_word: {act3_end_w}}}\n"
        f"No markdown, no explanation."
    )

    def _call_json_openai(sys: str, usr: str) -> dict:
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": sys},
                      {"role": "user",   "content": usr}],
            max_tokens=2500,
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
            max_tokens=2500,
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
        raise ValueError(f"VALIDATION_SKIP: title failed — {title_reason} (title: \"{title}\")")

    print(f"  ✅ Script passed validators ({len(narration.split())}w, title OK: {title})")
    return data


def render_longform_video(script_data: dict, out_dir: Path) -> dict:
    import edge_tts
    import asyncio
    from PIL import Image, ImageDraw, ImageFont

    out_dir.mkdir(parents=True, exist_ok=True)
    video_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    script_text = script_data.get("script", "")
    title       = script_data.get("title", "Bible Story Garden")
    queries     = script_data.get("pexels_queries", [])

    # ── 1. Audio ──────────────────────────────────────────────────────────────
    print("  🎙️  Generating narration audio...")
    audio_path = out_dir / f"{video_id}_narration.mp3"
    # AndrewNeural: warm, clear, storytelling quality — fits BSG's reverent tone
    # BrianNeural is the fallback alternative
    tts_voice  = os.getenv("BSG_LONGFORM_VOICE", "en-US-AndrewNeural")

    async def _tts():
        communicate = edge_tts.Communicate(script_text, tts_voice)
        await communicate.save(str(audio_path))

    asyncio.run(_tts())
    print(f"  ✅ Audio: {audio_path.name}")

    # ── 2. Duration ───────────────────────────────────────────────────────────
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(audio_path)],
        capture_output=True, text=True
    )
    duration_sec = float(json.loads(result.stdout)["format"]["duration"])
    print(f"  ✅ Duration: {duration_sec:.1f}s ({duration_sec/60:.1f} min)")

    # ── 3. Pexels footage ─────────────────────────────────────────────────────
    print("  🎬 Fetching landscape Pexels footage...")
    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    clip_paths = []

    if pexels_key and queries:
        import requests
        dedup_file = BASE_DIR / "pexels_used_bsg_longform.json"
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

                clip_path = out_dir / f"clip_{i:02d}.mp4"
                r = requests.get(files[0]["link"], timeout=30)
                clip_path.write_bytes(r.content)

                trimmed = out_dir / f"clip_{i:02d}_trim.mp4"
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(clip_path),
                    "-t", str(clip_duration),
                    "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-r", "30", "-an", str(trimmed)
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
        else:
            extended = clip_paths

        concat_file = out_dir / "concat.txt"
        concat_file.write_text("\n".join(f"file '{p.resolve()}'" for p in extended))
        backdrop = out_dir / "backdrop.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-t", str(duration_sec), "-c:v", "copy", str(backdrop)
        ], capture_output=True)
    else:
        # Warm amber fallback background for BSG
        backdrop = out_dir / "backdrop.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=0x1a1208:size=1920x1080:duration={duration_sec}:rate=30",
            "-c:v", "libx264", "-preset", "ultrafast", str(backdrop)
        ], capture_output=True)

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(backdrop), "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac",
        "-t", str(duration_sec), str(output_path)
    ], capture_output=True)
    print(f"  ✅ Video: {output_path.name}")

    # ── 5. Thumbnail ──────────────────────────────────────────────────────────
    thumb_path = out_dir / f"{video_id}_thumb.jpg"
    try:
        import requests as _req
        from io import BytesIO
        from PIL import ImageFont, ImageFilter

        thumb_text = script_data.get("thumbnail_text", title[:40].upper())
        # BSG thumbnail: warm golden landscape
        warm_queries = [f"golden sunrise {q}" for q in queries[:2]] + queries[2:]

        bg = None
        if pexels_key and warm_queries:
            for q in warm_queries[:6]:
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
                        img_r = _req.get(photos[pick]["src"]["large"], timeout=20)
                        bg = Image.open(BytesIO(img_r.content)).convert("RGB")
                        print(f"  📸 Thumbnail photo: {q[:45]}")
                        break
                except Exception:
                    continue

        if bg is None:
            bg = Image.new("RGB", (1280, 720), (26, 18, 8))

        # Scale to 1280×720
        bg_w, bg_h = bg.size
        scale = max(1280 / bg_w, 720 / bg_h)
        new_w, new_h = int(bg_w * scale), int(bg_h * scale)
        bg = bg.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - 1280) // 2
        top  = (new_h - 720)  // 2
        bg   = bg.crop((left, top, left + 1280, top + 720))
        # No blur — keep the image crisp and bright for Option A
        # BSG Option A: barely darkened, warm sunrise feel
        # Very light global darkening — just enough to make text readable
        dark_layer = Image.new("RGBA", (1280, 720), (0, 0, 0, 30))
        bg = Image.alpha_composite(bg.convert("RGBA"), dark_layer)

        # Warm amber gradient ONLY at the bottom quarter — text area only
        overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        grad_top = 480  # only bottom 240px darkened
        for y in range(grad_top, 720):
            t = (y - grad_top) / (720 - grad_top)
            alpha = int(160 * t)       # lighter than before
            r_val = int(30 * t)        # very subtle warm amber tint
            g_val = int(15 * t)
            b_val = 0
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

        def _outlined(draw, x, y, text, font, fill, stroke_fill=(80, 40, 0), stroke_w=5):
            # Warm dark brown stroke instead of black — feels warmer on bright images
            draw.text((x, y), text, font=font, fill=fill,
                      anchor="mm", stroke_width=stroke_w, stroke_fill=stroke_fill)

        if line2:
            # Both lines golden/warm white — bright and inviting
            _outlined(draw, 640, 600, line1, font_large, fill=(255, 248, 220))  # warm white
            _outlined(draw, 640, 680, line2, font_small,  fill=(255, 210, 60))  # bright gold
        else:
            _outlined(draw, 640, 640, line1, font_large, fill=(255, 248, 220))

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
    import re
    lines = desc.splitlines()
    prose_lines, timestamp_lines, hashtag_line = [], [], ""
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

    me = youtube.channels().list(part="id,snippet", mine=True).execute()
    channel_id   = me["items"][0]["id"]
    channel_name = me["items"][0]["snippet"]["title"]
    if channel_id != BSG_CHANNEL_ID:
        raise ValueError(
            f"TOKEN MISMATCH: expected BSG channel {BSG_CHANNEL_ID} "
            f"but token is bound to {channel_name} ({channel_id})"
        )
    print(f"  🔑 Uploading as: {channel_name} ({channel_id})")

    body = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "tags":        tags[:15],
            "categoryId":  "22",  # People & Blogs (fits faith/family content)
        },
        "status": {
            "privacyStatus":           "private",
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

    video_id_yt = response["id"]
    video_url   = f"https://www.youtube.com/watch?v={video_id_yt}"
    studio_url  = f"https://studio.youtube.com/video/{video_id_yt}/edit"

    if thumb_path and thumb_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id_yt,
                media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
            ).execute()
            print("  ✅ Thumbnail uploaded")
        except Exception as e:
            print(f"  ⚠️  Thumbnail upload failed: {e}")

    if BSG_LONGFORM_PLAYLIST_ID:
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={"snippet": {
                    "playlistId": BSG_LONGFORM_PLAYLIST_ID,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id_yt},
                }}
            ).execute()
            print(f"  ✅ Added to BSG long-form playlist")
        except Exception as e:
            print(f"  ⚠️  Playlist add failed: {e}")

    print(f"  ✅ Uploaded (PUBLIC): {video_url}")
    return video_url, studio_url


def send_notification_email(title: str, video_url: str, studio_url: str,
                             topic: str, duration_sec: float) -> None:
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    if not password:
        print("  ⚠️  GMAIL_APP_PASSWORD not set — skipping email")
        return

    duration_str = f"{int(duration_sec // 60)}:{int(duration_sec % 60):02d}"
    ts = datetime.now(ZoneInfo("America/Chicago")).strftime("%b %d, %Y at %I:%M %p CT")

    subject = f"[BSG Long-Form Posted] {title}"
    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #5c3a1e;">🌿 New Long-Form Posted — Bible Story Garden</h2>
    <p style="color: #666;">Posted {ts} | Duration: {duration_str} | Status: <strong>PUBLIC</strong></p>
    <hr>
    <h3>{title}</h3>
    <p><strong>Topic:</strong> {topic}</p>
    <p>
      <a href="{video_url}" style="background:#c8860a;color:white;padding:12px 24px;
         text-decoration:none;border-radius:4px;display:inline-block;margin-right:10px;">
        ▶ Watch on YouTube
      </a>
      <a href="{studio_url}" style="background:#333;color:white;padding:12px 24px;
         text-decoration:none;border-radius:4px;display:inline-block;">
        📊 View in Studio
      </a>
    </p>
    <hr>
    <p style="color: #999; font-size: 12px;">Bible Story Garden Long-Form Auto-Post System</p>
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
        print(f"  📧 Notification email sent")
    except Exception as e:
        print(f"  ⚠️  Email failed: {e}")


def log_to_sheets(title: str, url: str, topic: str) -> None:
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
        row = [ts, "Bible Story Garden (Long-Form)", title, "Public", url, ""]
        service.spreadsheets().values().append(
            spreadsheetId="1JKlBnYdv-_r3FcjozBtpRxLNRiAoA1ezLRz2W-7vVWI",
            range="Auto-Post Log!A:G",
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()
        print(f"  📊 Logged to Sheets")
    except Exception as e:
        print(f"  ⚠️  Sheets logging failed: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="BSG Long-Form Auto-Post")
    parser.add_argument("--topic", default="", help="Override topic string")
    parser.add_argument("--dry-run", action="store_true", help="Render only, skip upload")
    args = parser.parse_args()

    print(f"\n{'═' * 60}")
    print(f"  🌿 BSG Long-Form  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
    description = script_data.get("description", f"{title}\n\n#BibleStories #BibleStoryGarden")
    description = _format_description(description)
    tags        = script_data.get("tags", ["bible stories", "bible story garden", "faith"])
    video_url, studio_url = upload_to_youtube(
        render_result["video_path"], title, description, tags,
        render_result.get("thumb_path")
    )

    mark_posted(topic, title, video_url)
    log_to_sheets(title, video_url, topic)
    send_notification_email(title, video_url, studio_url, topic, render_result["duration_sec"])

    print(f"\n{'═' * 60}")
    print(f"  ✅ DONE — Uploaded PUBLIC")
    print(f"  Title   : {title}")
    print(f"  Duration: {render_result['duration_sec']/60:.1f} min")
    print(f"  Watch   : {video_url}")
    print(f"{'═' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
