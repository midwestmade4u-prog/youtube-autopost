#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║         MidwestMade4U — Video Studio                    ║
║         Bible Story Garden + The Mind Files             ║
╚══════════════════════════════════════════════════════════╝

One-time setup (run in Terminal first):
    pip3 install flask edge-tts Pillow openai

Optional — YouTube auto-posting:
    pip3 install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Optional — YOUR voice clone:
    pip3 install TTS   (downloads ~2GB model on first use)

Usage:
    python3 video_app.py

Then Chrome opens automatically at: http://localhost:5002
"""

import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string, request, send_file

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
TEMP_DIR   = BASE_DIR / "temp_work"
VOICE_DIR  = BASE_DIR / "bsg_voices"
MUSIC_DIR  = BASE_DIR / "bsg_music"

# Per-channel output folders — created on demand in run_video_job
CHANNEL_OUTPUT = {
    "bsg": BASE_DIR / "BSG_Output",
    "tmf": BASE_DIR / "TMF_Output",
}

for d in [TEMP_DIR, VOICE_DIR, MUSIC_DIR] + list(CHANNEL_OUTPUT.values()):
    d.mkdir(exist_ok=True)

# ── Config (API keys) ─────────────────────────────────────────────────────────
CONFIG_FILE = BASE_DIR / "config.json"

def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}

def get_openai_key():
    return load_config().get("openai_api_key", "").strip()

def get_elevenlabs_key():
    return load_config().get("elevenlabs_api_key", "").strip()

def get_fal_key():
    return load_config().get("fal_api_key", "").strip()

# ── Brand Colors ──────────────────────────────────────────────────────────────
from PIL import Image, ImageDraw, ImageFont, ImageOps
GREEN = (29, 158, 117)
GOLD  = (239, 159,  39)
CREAM = (250, 238, 218)

WIDTH, HEIGHT = 1280, 720
VERT_WIDTH, VERT_HEIGHT = 1080, 1920

# ── Channel styles ────────────────────────────────────────────────────────────
CHANNEL_STYLES = {
    "bsg": {
        "label":      "Bible Story Garden",
        "watermark":  "Bible Story Garden",
        "style":      (
            "bright colorful animated children's bible storybook illustration, "
            "warm family friendly art, vibrant cheerful colors, "
            "{prompt}, no text, no words, clean illustration"
        ),
        "fallback_generic": [
            "peaceful biblical landscape, colorful storybook art, warm sunlight",
            "peaceful sunlit meadow, colorful cheerful illustration",
        ],
    },
    "tmf": {
        "label":      "The Mind Files",
        "watermark":  "The Mind Files",
        "style":      (
            "Dark cinematic still photograph, black and white or heavily desaturated, film noir aesthetic. "
            "Atmospheric and symbolic: {prompt}. "
            "Use dramatic objects, environments, shadows, textures, and silhouettes — "
            "absolutely NO faces, NO identifiable people, NO portraits. "
            "Examples: empty chairs, worn clocks, burning candles, heavy chains, long corridors, "
            "cracked mirrors, hands gripping objects, locked doors, broken glass. "
            "High contrast lighting, deep blacks, moody atmosphere. "
            "Photorealistic editorial photography style. Full frame composition. No text. No logos."
        ),
        "fallback_generic": [
            "dark empty hallway with a single overhead light casting long shadows, black and white cinematic photography, high contrast, no people",
            "close-up of a worn clock face on a dark wooden table, dramatic side lighting, black and white photorealistic, no people",
            "heavy iron chains coiled on concrete floor, dramatic high-contrast lighting, black and white symbolic photography, no people",
        ],
    },
}

# ── Voice cloning setup ───────────────────────────────────────────────────────
VOICE_FILE = VOICE_DIR / "my_voice.m4a"
VOICE_WAV  = VOICE_DIR / "my_voice.wav"
_xtts_model = None

def has_voice_file():
    return VOICE_FILE.exists() or VOICE_WAV.exists()

def _find_bold_font(size):
    """Find the best available bold font on Mac or Linux."""
    candidates = [
        # macOS system fonts
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        # macOS fallback — Courier is always present
        "/System/Library/Fonts/Courier New Bold.ttf",
        "/Library/Fonts/Microsoft/Arial Bold.ttf",
        # Linux fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _find_regular_font(size):
    """Find the best available regular font on Mac or Linux."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def has_xtts():
    try:
        import TTS
        return True
    except ImportError:
        return False

def get_xtts_model():
    global _xtts_model
    if _xtts_model is None:
        from TTS.api import TTS as CoquiTTS
        _xtts_model = CoquiTTS("tts_models/multilingual/multi-dataset/xtts_v2")
    return _xtts_model

def prepare_voice_wav():
    """Convert m4a → wav for XTTS (runs once)."""
    if VOICE_WAV.exists():
        return True
    if not VOICE_FILE.exists():
        return False
    result = subprocess.run([
        "ffmpeg", "-y", "-i", str(VOICE_FILE),
        "-ar", "22050", "-ac", "1", str(VOICE_WAV)
    ], capture_output=True)
    return VOICE_WAV.exists()

# ── Progress queue ────────────────────────────────────────────────────────────
progress_queue = queue.Queue()
current_job    = {"running": False, "output": None, "error": None}

app = Flask(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  VIDEO GENERATION  (same logic as bible_video_maker.py)
# ══════════════════════════════════════════════════════════════════════════════

def emit(msg):
    progress_queue.put({"msg": msg})

def emit_done(path):
    progress_queue.put({"done": True, "path": str(path)})

def emit_error(err):
    progress_queue.put({"error": str(err)})


def _fal_image(prompt_str, output_path, width=1280, height=720):
    """Generate image using fal.ai Flux Pro. Returns True on success.
    ~40% cheaper than DALL-E 3 at equivalent quality."""
    try:
        import json as _json
        api_key = get_fal_key()
        if not api_key:
            return False
        # Always request square to avoid rotation artifacts (same strategy as DALL-E)
        # _normalize_portrait() will center-crop to 9:16 after download
        payload = _json.dumps({
            "prompt": prompt_str,
            "image_size": "square_hd",   # 1024x1024
            "num_images": 1,
            "enable_safety_checker": False,
            "output_format": "jpeg",
        }).encode()
        req = urllib.request.Request(
            "https://fal.run/fal-ai/flux-pro",
            data=payload,
            headers={
                "Authorization": f"Key {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            result = _json.loads(r.read())
        image_url = result["images"][0]["url"]
        img_req = urllib.request.Request(image_url, headers={"User-Agent": "VideoStudio/1.0"})
        with urllib.request.urlopen(img_req, timeout=60) as r:
            data = r.read()
        if len(data) > 5000:
            with open(output_path, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        emit(f"  ⚠️ fal.ai error: {str(e)[:80]}")
    return False


def _dalle_image(prompt_str, output_path, width=1280, height=720):
    """Generate image using DALL-E 3. Returns True on success."""
    try:
        import openai
        client = openai.OpenAI(api_key=get_openai_key())
        # Always request SQUARE (1024x1024) from DALL-E.
        # DALL-E 3's portrait size (1024x1792) has a known bug where it renders
        # the scene in landscape orientation inside the portrait canvas, making
        # content appear sideways. Square images never have this rotation artifact.
        # _normalize_portrait() crops the square to the correct 9:16 portrait shape.
        dalle_size = "1024x1024"
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt_str,
            size=dalle_size,
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        req = urllib.request.Request(image_url, headers={"User-Agent": "VideoStudio/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        if len(data) > 5000:
            with open(output_path, "wb") as f:
                f.write(data)
            return True
    except Exception as e:
        emit(f"  ⚠️ DALL-E error: {str(e)[:80]}")
    return False


def _pollinations_image(prompt_str, seed, output_path, width=1280, height=720, timeout=60):
    """Fallback: fetch image from Pollinations.ai."""
    encoded = urllib.parse.quote(prompt_str)
    url = (f"https://image.pollinations.ai/prompt/{encoded}"
           f"?width={width}&height={height}&seed={seed}&nologo=true")
    req = urllib.request.Request(url, headers={"User-Agent": "VideoStudio/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if len(data) > 5000:
        with open(output_path, "wb") as f:
            f.write(data)
        return True
    return False


def _normalize_portrait(path, target_w, target_h):
    """
    Guarantee the saved image file is exactly target_w × target_h (portrait).

    DALL-E is requested as square (1024x1024) to avoid a DALL-E 3 bug where
    portrait-size requests (1024x1792) render the scene rotated sideways inside
    the canvas.  Pollinations may also return landscape.  In both cases we
    center-crop to portrait aspect ratio so content stays upright.

    Steps:
      1. Apply any EXIF rotation tag so PIL sees real pixel orientation.
      2. If wider than portrait target ratio → center-crop the sides.
         (Covers square 1:1 and landscape 16:9 inputs.)
      3. Resize to exact target_w × target_h with LANCZOS.
      4. Save back to the same path as JPEG.
    """
    try:
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)     # honour any EXIF rotation
        img = img.convert("RGB")

        target_ratio = target_w / target_h     # e.g. 1080/1920 = 0.5625

        # Center-crop whenever the image is wider than the portrait ratio.
        # This handles: square (1:1), landscape (>1:1) — any wider-than-portrait source.
        # Pure portrait inputs (already narrow) pass through uncropped.
        if img.width / img.height > target_ratio:
            # Crop sides: keep full height, trim left and right
            crop_w = int(img.height * target_ratio)
            left   = (img.width - crop_w) // 2
            img    = img.crop((left, 0, left + crop_w, img.height))

        img = img.resize((target_w, target_h), Image.LANCZOS)
        img.save(path, "JPEG", quality=95)
    except Exception as e:
        emit(f"  ⚠️ Portrait normalisation failed for {path}: {e}")


def generate_image(prompt, output_path, scene_num, width=1280, height=720, channel="bsg"):
    """
    Primary: DALL-E 3 (if API key set). Fallback: Pollinations with retries.
    Never gives up — always produces a real image.
    After every successful download the image is normalised to portrait
    (target width × height) so FFmpeg always receives portrait pixels.
    """
    p     = prompt.strip()
    style = CHANNEL_STYLES.get(channel, CHANNEL_STYLES["bsg"])
    styled = style["style"].format(prompt=p)

    # ── fal.ai Flux Pro (primary — cheapest, best quality) ────────────────────
    if get_fal_key():
        for attempt in range(3):
            try:
                if _fal_image(styled, output_path, width=width, height=height):
                    _normalize_portrait(output_path, width, height)
                    emit(f"  🎨 Image generated via Flux Pro")
                    return True
                emit(f"  ⚠️ Flux Pro attempt {attempt+1} failed, retrying...")
            except Exception as e:
                emit(f"  ⚠️ Flux Pro attempt {attempt+1} error: {str(e)[:60]}")
            time.sleep(2)
        emit(f"  ⚠️ Flux Pro failed 3 times — trying DALL-E...")

    # ── DALL-E 3 (secondary — if fal.ai key absent or failed) ────────────────
    if get_openai_key():
        for attempt in range(3):
            try:
                if _dalle_image(styled, output_path, width=width, height=height):
                    _normalize_portrait(output_path, width, height)
                    return True
                emit(f"  ⚠️ DALL-E attempt {attempt+1} failed, retrying...")
            except Exception as e:
                emit(f"  ⚠️ DALL-E attempt {attempt+1} error: {str(e)[:60]}")
            time.sleep(2)
        emit(f"  ⚠️ DALL-E failed 3 times — switching to backup image service...")

    # ── Pollinations fallback ──────────────────────────────────────────────────
    generics = style["fallback_generic"]
    fallback_attempts = [
        (styled,                                                  scene_num * 42),
        (styled,                                                  scene_num * 77),
        (style["style"].format(prompt=p[:120]),                   scene_num * 31),
        (style["style"].format(prompt=p[:60]),                    scene_num * 67),
        (style["style"].format(prompt=p[:30]),                    scene_num * 101),
        (generics[0],                                             scene_num * 23),
        (generics[1] if len(generics) > 1 else generics[0],      scene_num * 37),
    ]

    for i, (prompt_str, seed) in enumerate(fallback_attempts):
        try:
            if _pollinations_image(prompt_str, seed, output_path, width=width, height=height):
                _normalize_portrait(output_path, width, height)
                if i > 0:
                    emit(f"  ✅ Backup image succeeded (attempt {i+1})")
                return True
        except Exception:
            pass
        time.sleep(3)

    # Last resort placeholder
    emit(f"  ❌ All image attempts failed for scene {scene_num+1}")
    _make_placeholder(output_path, scene_num, width=width, height=height)
    return False


def _make_placeholder(path, scene_num, width=1280, height=720):
    """Last-resort placeholder — should almost never appear."""
    img  = Image.new("RGB", (width, height), (20, 20, 30))
    draw = ImageDraw.Draw(img)
    cx, cy = width // 2, height // 2
    try:
        font  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except:
        font  = ImageFont.load_default()
        small = font
    draw.text((cx, cy),    f"Scene {scene_num+1}", fill=(160, 160, 180), font=font,  anchor="mm")
    draw.text((cx, cy+50), "Image unavailable",    fill=(100, 100, 120), font=small, anchor="mm")
    img.save(path)


def add_text_overlay(image_path, text, output_path, width=1280, height=720, channel="bsg", animated_captions=False):
    # Open image and correct any EXIF rotation
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGBA")
    img = img.resize((width, height), Image.LANCZOS)

    W, H        = width, height
    is_vertical = H > W
    overlay     = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw        = ImageDraw.Draw(overlay)

    # Channel watermark — top-right corner
    brand_size = 30 if is_vertical else 20
    font_brand = _find_regular_font(brand_size)
    watermark  = CHANNEL_STYLES.get(channel, CHANNEL_STYLES["bsg"])["watermark"]

    # Semi-transparent dark pill behind watermark for legibility
    wm_bbox = draw.textbbox((0, 0), watermark, font=font_brand)
    wm_w    = wm_bbox[2] - wm_bbox[0]
    pad     = 10
    wx      = W - 20 - wm_w
    wy      = 16
    draw.rounded_rectangle(
        [wx - pad, wy - pad // 2, wx + wm_w + pad, wy + (wm_bbox[3] - wm_bbox[1]) + pad // 2],
        radius=8, fill=(0, 0, 0, 100)
    )
    draw.text((wx, wy), watermark, fill=(255, 255, 255, 200), font=font_brand)

    # Static narration card — skipped when animated captions handle the text
    if not animated_captions:
        # Border color: warm wood-brown for BSG, dark indigo for TMF
        border_color = (125, 82, 53) if channel == "bsg" else (50, 50, 140)

        text_size = 60 if is_vertical else 44
        font_text = _find_bold_font(text_size)

        # Word-wrap text to fit inside card (82% of frame width)
        card_w      = int(W * 0.82)
        inner_pad   = 36
        max_text_w  = card_w - inner_pad * 2
        words, lines, current = text.split(), [], ""
        for word in words:
            test = (current + " " + word).strip()
            bbox = draw.textbbox((0, 0), test, font=font_text)
            if bbox[2] - bbox[0] > max_text_w:
                if current:
                    lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)

        lh      = text_size + 12
        tot_h   = len(lines) * lh
        border  = 5
        card_h  = tot_h + inner_pad * 2

        # Position card: center horizontally, ~68% down the frame
        card_x  = (W - card_w) // 2
        card_y  = int(H * 0.68) - card_h // 2
        # Keep card on screen
        card_y  = max(card_y, int(H * 0.04))
        card_y  = min(card_y, H - card_h - int(H * 0.04))

        # Draw border rectangle (slightly larger), then white fill
        r = 18  # corner radius
        draw.rounded_rectangle(
            [card_x - border, card_y - border,
             card_x + card_w + border, card_y + card_h + border],
            radius=r + border, fill=(*border_color, 230)
        )
        draw.rounded_rectangle(
            [card_x, card_y, card_x + card_w, card_y + card_h],
            radius=r, fill=(255, 255, 255, 245)
        )

        # Draw text centered inside card
        text_start_y = card_y + inner_pad
        for i, line in enumerate(lines):
            y = text_start_y + i * lh
            # Subtle shadow
            draw.text((W // 2 + 2, y + 2), line, fill=(0, 0, 0, 60),  font=font_text, anchor="mt")
            draw.text((W // 2,     y),     line, fill=(30, 20, 10, 255), font=font_text, anchor="mt")

    Image.alpha_composite(img, overlay).convert("RGB").save(output_path)


async def _gen_audio_async(text, path, voice):
    import edge_tts
    await edge_tts.Communicate(text, voice).save(str(path))


async def _gen_audio_with_timing_async(text, path, voice):
    """
    Generate audio AND capture word-level timing from edge-tts WordBoundary events.
    This gives us animated captions for ALL voices — no ElevenLabs required.
    Returns list of {word, start, end} dicts (same format as ElevenLabs output).
    """
    import edge_tts
    communicate  = edge_tts.Communicate(text, voice)
    word_timings = []

    with open(path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset and duration are in 100-nanosecond units → convert to seconds
                start = chunk["offset"] / 10_000_000
                end   = (chunk["offset"] + chunk["duration"]) / 10_000_000
                word_timings.append({
                    "word":  chunk["text"],
                    "start": start,
                    "end":   end,
                })

    return word_timings if word_timings else None


def _elevenlabs_audio(text, path, voice_id, get_timestamps=False):
    """
    Generate audio using ElevenLabs API.
    If get_timestamps=True, uses the with-timestamps endpoint and returns
    a list of {word, start, end} dicts alongside the audio.
    """
    import base64
    api_key = get_elevenlabs_key()

    if get_timestamps:
        # Use the timestamps endpoint — returns audio + character-level timing
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
        payload = json.dumps({
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())

        # Save audio
        audio_data = base64.b64decode(resp["audio_base64"])
        with open(path, "wb") as f:
            f.write(audio_data)

        # Build word-level timing from character alignment
        alignment  = resp.get("alignment", {})
        chars      = alignment.get("characters", [])
        starts     = alignment.get("character_start_times_seconds", [])
        ends       = alignment.get("character_end_times_seconds", [])

        word_timings = []
        current_word = ""
        word_start   = None
        for ch, s, e in zip(chars, starts, ends):
            if ch == " " or ch == "\n":
                if current_word:
                    word_timings.append({"word": current_word, "start": word_start, "end": e})
                    current_word = ""
                    word_start   = None
            else:
                if not current_word:
                    word_start = s
                current_word += ch
        if current_word:
            word_timings.append({"word": current_word, "start": word_start, "end": ends[-1] if ends else 0})

        return word_timings

    else:
        # Standard audio-only endpoint
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = json.dumps({
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return None


# ElevenLabs voice IDs — warm voices that suit narration well
ELEVENLABS_VOICES = {
    "el_sarah":   "EXAVITQu4vr4xnSDxMaL",   # Sarah — warm, clear female
    "el_rachel":  "21m00Tcm4TlvDq8ikWAM",   # Rachel — calm female
    "el_adam":    "pNInz6obpgDQGcFmaJgB",   # Adam — deep male narrator
    "el_antoni":  "ErXwobaYiN019PkySvjV",   # Antoni — warm male
    "el_josh":    "TxGEqnHWrfWFTfGW9XjX",   # Josh — deep storytelling male
}

EDGE_TTS_VOICES = {
    "en-US-JennyNeural", "en-US-AriaNeural", "en-US-MichelleNeural",
    "en-US-GuyNeural", "en-US-DavisNeural"
}


def generate_audio(text, path, voice):
    """
    Route audio generation: ElevenLabs > Edge TTS > voice clone.
    Returns word-timing list [{word, start, end}] when ElevenLabs is used,
    otherwise returns None (captions will fall back to static display).
    """
    if voice == "my_voice":
        generate_audio_xtts(text, path)
        return None

    # ElevenLabs voices — request timestamps for animated captions
    if voice.startswith("el_") and get_elevenlabs_key():
        voice_id = ELEVENLABS_VOICES.get(voice)
        if voice_id:
            try:
                timings = _elevenlabs_audio(text, path, voice_id, get_timestamps=True)
                return timings
            except Exception as e:
                emit(f"  ⚠️ ElevenLabs error: {str(e)[:60]} — falling back to Edge TTS")

    # Edge TTS — use streaming mode to capture word timing for animated captions
    # This means ALL voices (free or premium) get word-by-word animated captions
    tts_voice = voice if voice in EDGE_TTS_VOICES else "en-US-MichelleNeural"
    fallback_voices = ["en-US-MichelleNeural", "en-US-JennyNeural", "en-US-AriaNeural"]
    for attempt in range(3):
        try:
            timings = asyncio.run(_gen_audio_with_timing_async(text, path, tts_voice))
            if timings:
                emit(f"  ✨ {len(timings)} word timings — animated captions active")
            else:
                emit(f"  ℹ️ No word timings from edge-tts — using static text overlay")
            return timings  # returns word timings for captions (or None if streaming gave none)
        except Exception as tts_err:
            if attempt < 2:
                emit(f"  ⚠️ Voice attempt {attempt+1}/3 failed — retrying in 2s...")
                time.sleep(2)
                tts_voice = fallback_voices[attempt + 1]
            else:
                raise Exception(
                    f"Audio generation failed after 3 attempts. "
                    f"Check your internet connection and try again. ({tts_err})"
                )
    return None

def generate_audio_xtts(text, output_path):
    """Generate speech in your cloned voice using Coqui XTTS v2."""
    emit("  🎤 Using your voice clone...")
    prepare_voice_wav()
    if not VOICE_WAV.exists():
        emit("  ⚠️ Voice file not found — falling back to AI voice")
        asyncio.run(_gen_audio_async(text, output_path, "en-US-JennyNeural"))
        return
    model = get_xtts_model()
    wav_out = output_path.with_suffix(".wav")
    model.tts_to_file(
        text=text,
        speaker_wav=str(VOICE_WAV),
        language="en",
        file_path=str(wav_out)
    )
    # Convert wav → mp3
    subprocess.run([
        "ffmpeg", "-y", "-i", str(wav_out), str(output_path)
    ], capture_output=True)


def _make_ass_captions(word_timings, ass_path, width=1280, height=720, channel="bsg"):
    """
    Generate an ASS subtitle file with bold word-by-word highlighted captions.
    AutoShorts-style: large bold text, one line at a time, active word in accent color.
    """
    is_vertical = height > width

    # Large bold font — sized so it's readable on a phone screen
    # AutoShorts-style: very large text, 1-2 words per line, punchy and immediate
    font_size = 95 if is_vertical else 52
    margin_v  = int(height * 0.08)   # distance from bottom

    # Channel accent color in ASS &HAABBGGRR format (AA=00 = fully opaque)
    # ASS uses BGR order: BSG = amber #C8923A → BGR 3A92C8, TMF = vivid yellow → BGR 00EEFF
    accent = "&H003A92C8" if channel == "bsg" else "&H0000EEFF"
    white  = "&H00FFFFFF"
    black_outline = "&H00000000"
    bg_box = "&H00000000"   # transparent — thick outline is enough

    # Group into short lines — 2 words per line for big punchy captions
    WORDS_PER_LINE = 2
    lines = []
    i = 0
    while i < len(word_timings):
        chunk = word_timings[i:i + WORDS_PER_LINE]
        lines.append({
            "words":  chunk,
            "start":  chunk[0]["start"],
            "end":    chunk[-1]["end"],
        })
        i += WORDS_PER_LINE

    def ts(seconds):
        h  = int(seconds // 3600)
        m  = int((seconds % 3600) // 60)
        s  = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    # BorderStyle 1 = outline + shadow, no box — bold thick outline is the AutoShorts look
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,Strikeout,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial Black,{font_size},{white},{accent},{black_outline},{bg_box},-1,0,0,0,100,100,0,0,1,5,2,2,20,20,{margin_v},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

    events = []
    for line in lines:
        words   = line["words"]
        line_e  = line["end"]

        for wi, word_info in enumerate(words):
            w_start = word_info["start"]
            w_end   = word_info["end"] if wi < len(words) - 1 else line_e

            parts = []
            for j, w in enumerate(words):
                word_upper = w["word"].upper()
                if j == wi:
                    # Active word: accent color, slightly larger scale
                    parts.append(f"{{\\c{accent}\\fscx108\\fscy108}}{word_upper}{{\\fscx100\\fscy100}}")
                else:
                    # Inactive words: white
                    parts.append(f"{{\\c{white}}}{word_upper}")
            styled = " ".join(parts)
            events.append(f"Dialogue: 0,{ts(w_start)},{ts(w_end)},Default,,0,0,0,,{styled}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")


def create_scene_clip(img_path, audio_path, out_path, scene_num=0,
                      width=1280, height=720, word_timings=None, channel="bsg"):
    """Create a video clip with Ken Burns slow zoom + optional animated captions."""
    # CRITICAL: scale to exact target dimensions FIRST, THEN zoompan.
    # This guarantees zoompan always receives the correct-sized input regardless
    # of what DALL-E or Pollinations returned. Without this, portrait videos can
    # come out landscape if the source image is the wrong aspect ratio.
    motion = scene_num % 3
    # Use even dimensions only (libx264 requirement)
    w = width  + (width  % 2)
    h = height + (height % 2)

    if motion == 0:
        zoom_expr = f"zoompan=z='min(zoom+0.0006,1.07)':d=9999:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}"
    elif motion == 1:
        zoom_expr = f"zoompan=z='if(lte(zoom,1.0),1.07,max(1.0,zoom-0.0006))':d=9999:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}"
    else:
        if h > w:
            zoom_expr = f"zoompan=z='1.06':d=9999:x='iw/2-(iw/zoom/2)':y='min(ih*(zoom-1)/zoom,y+0.3)':s={w}x{h}"
        else:
            zoom_expr = f"zoompan=z='1.06':d=9999:x='min(iw*(zoom-1)/zoom,x+0.4)':y='ih/2-(ih/zoom/2)':s={w}x{h}"

    # scale={w}:{h} BEFORE zoompan forces correct portrait/landscape input
    # scale again after zoompan is a double safety net
    base_vf = f"scale={w}:{h}:flags=lanczos,{zoom_expr},scale={w}:{h}:flags=lanczos,fps=25"

    # Build animated captions if we have word timings
    vf = base_vf
    ass_tmp = None
    if word_timings:
        try:
            import tempfile, os as _os
            ass_fd, ass_str = tempfile.mkstemp(suffix=".ass")
            _os.close(ass_fd)
            ass_tmp = Path(ass_str)
            _make_ass_captions(word_timings, ass_tmp, width=width, height=height, channel=channel)
            if ass_tmp.exists():
                # Resolve symlinks (macOS /tmp → /private/tmp) and escape for FFmpeg
                real_path = str(ass_tmp.resolve())
                # FFmpeg subtitles filter: escape backslashes and single quotes only
                safe = real_path.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
                vf = f"{base_vf},subtitles='{safe}'"
                emit(f"  📝 Captions file ready")
        except Exception as e:
            emit(f"  ⚠️ Caption build failed: {str(e)[:80]}")

    result = subprocess.run([
        "ffmpeg", "-y", "-loop", "1",
        "-i", str(img_path), "-i", str(audio_path),
        "-c:v", "libx264",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-shortest",
        "-vf", vf,
        str(out_path)
    ], capture_output=True)

    # If FFmpeg failed (e.g. libass issue), retry without captions
    if result.returncode != 0 and ass_tmp is not None:
        err_snippet = result.stderr[-300:].decode("utf-8", errors="replace") if result.stderr else ""
        emit(f"  ⚠️ Caption render failed — retrying without captions")
        if "subtitles" in err_snippet or "ass" in err_snippet.lower():
            emit(f"  ℹ️ libass issue detected — captions disabled for this clip")
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1",
            "-i", str(img_path), "-i", str(audio_path),
            "-c:v", "libx264",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest",
            "-vf", base_vf,
            str(out_path)
        ], capture_output=True)

    # Clean up temp ASS file
    if ass_tmp and ass_tmp.exists():
        try: ass_tmp.unlink()
        except: pass


def _generate_ambient_music(path, duration=150):
    """
    Generate a gentle ambient chord pad using pure Python — no downloads needed.
    C major → A minor → F major → G major, cycling every 4 seconds.
    """
    import wave, math, array as arr
    sr      = 44100
    n       = sr * duration
    chords  = [
        [261.63, 329.63, 392.00],   # C major
        [220.00, 261.63, 329.63],   # A minor
        [174.61, 220.00, 261.63],   # F major
        [196.00, 246.94, 293.66],   # G major
    ]
    chord_len = sr * 4   # 4 seconds per chord
    volume    = 0.07     # 7% — quiet bed, won't overpower narration

    samples = arr.array('h', [0] * n)
    for i in range(n):
        t   = i / sr
        ci  = (i // chord_len) % len(chords)
        cp  = (i % chord_len) / chord_len
        # Per-chord soft fade in/out so chords blend rather than click
        env = min(cp * 12, 1.0) * min((1.0 - cp) * 12, 1.0)
        # Overall track fade-in and fade-out (2 seconds each)
        fade = min(t * 0.5, 1.0) * min((duration - t) * 0.5, 1.0)
        v = sum(math.sin(2 * math.pi * f * t) for f in chords[ci]) / 3.0
        samples[i] = max(-32767, min(32767, int(v * env * fade * volume * 32767)))

    with wave.open(str(path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


def get_background_music():
    """Return path to background music, generating it if needed."""
    # User can drop their own .mp3/.wav into bsg_music/ — use that first
    for pattern in ["*.mp3", "*.wav", "*.m4a"]:
        tracks = [t for t in MUSIC_DIR.glob(pattern) if "ambient_bg" not in t.name]
        if tracks:
            return tracks[0]

    # Auto-generate ambient pad if not already done
    wav_path = MUSIC_DIR / "ambient_bg.wav"
    if not wav_path.exists():
        try:
            _generate_ambient_music(wav_path, duration=150)
        except Exception:
            return None
    return wav_path if wav_path.exists() else None


def concatenate_clips(clip_paths, out_path):
    """Concatenate scene clips and mix in background music."""
    list_file  = TEMP_DIR / "clips.txt"
    concat_tmp = TEMP_DIR / "concat_raw.mp4"

    # Filter out missing/empty clips — a failed scene shouldn't kill the whole video
    valid_clips = [c for c in clip_paths if c.exists() and c.stat().st_size > 10000]
    if not valid_clips:
        raise Exception("No valid scene clips were produced. Check progress log for errors.")
    if len(valid_clips) < len(clip_paths):
        emit(f"  ⚠️ {len(clip_paths) - len(valid_clips)} scene(s) failed — continuing with {len(valid_clips)} clips")

    with open(list_file, "w") as f:
        for c in valid_clips:
            f.write(f"file '{c.resolve()}'\n")

    # Step 1: concatenate — use re-encode (not copy) to guarantee consistent
    # dimensions across all clips. -c copy can fail silently when clips differ.
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(concat_tmp)
    ], capture_output=True)

    # Step 2: mix background music under narration
    music = get_background_music()
    if music and concat_tmp.exists():
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(concat_tmp),
            "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            "[1:a]volume=0.12[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=3[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            str(out_path)
        ], capture_output=True)

        if result.returncode != 0 or not Path(out_path).exists():
            # Music mixing failed — fall back to no-music version
            if concat_tmp.exists():
                import shutil
                shutil.copy(str(concat_tmp), str(out_path))
    elif concat_tmp.exists():
        import shutil
        shutil.copy(str(concat_tmp), str(out_path))


def run_video_job(title, scenes, voice, fmt="vertical", channel="bsg"):
    global current_job
    try:
        current_job["running"] = True
        current_job["output"]  = None
        current_job["error"]   = None

        # Always Shorts/Reels — landscape removed
        vid_w, vid_h = VERT_WIDTH, VERT_HEIGHT   # 1080 x 1920

        ch_label = CHANNEL_STYLES.get(channel, CHANNEL_STYLES["bsg"])["label"]
        emit(f"📺 Channel: {ch_label}")
        emit(f"📖 Building: {title}")
        emit(f"📐 Format: 📱 Shorts 9:16 (1080×1920)")
        emit(f"🎬 Scenes: {len(scenes)}\n")

        clip_paths = []
        for i, scene in enumerate(scenes):
            emit(f"── Scene {i+1} of {len(scenes)} ──────────────")
            emit(f"  🎨 Generating image {i+1}...")

            raw_img   = TEMP_DIR / f"scene_{i:02d}_raw.jpg"
            final_img = TEMP_DIR / f"scene_{i:02d}_final.jpg"
            audio     = TEMP_DIR / f"scene_{i:02d}_audio.mp3"
            clip      = TEMP_DIR / f"scene_{i:02d}_clip.mp4"

            generate_image(scene["image_prompt"], raw_img, i, width=vid_w, height=vid_h, channel=channel)
            emit(f"  ✅ Image {i+1} saved")

            emit(f"  🎙️ Generating narration...")
            word_timings = generate_audio(scene["narration"], audio, voice)
            has_captions = bool(word_timings)
            if has_captions:
                emit(f"  ✨ Word timing captured — animated captions active")

            emit(f"  📝 Adding image overlay...")
            add_text_overlay(raw_img, scene["narration"], final_img,
                             width=vid_w, height=vid_h, channel=channel,
                             animated_captions=has_captions)

            emit(f"  🎬 Assembling clip...")
            create_scene_clip(final_img, audio, clip, scene_num=i,
                              width=vid_w, height=vid_h,
                              word_timings=word_timings, channel=channel)
            clip_paths.append(clip)

            emit(f"  ✅ Scene {i+1} complete!\n")

        emit("── Assembling final video ──────────────")
        emit("  🎵 Mixing background music...")
        safe       = title.replace(" ", "_").replace("'", "").replace(":", "").replace("-", "_")
        output_dir = CHANNEL_OUTPUT.get(channel, CHANNEL_OUTPUT["bsg"])
        out        = output_dir / f"{safe}.mp4"
        concatenate_clips(clip_paths, out)

        current_job["output"] = str(out)
        emit_done(out)

    except Exception as e:
        current_job["error"] = str(e)
        emit_error(e)
    finally:
        current_job["running"] = False


# ══════════════════════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/generate", methods=["POST"])
def generate():
    if current_job["running"]:
        return jsonify({"error": "A video is already generating. Please wait."}), 400

    data    = request.json
    title   = data.get("title", "My Video").strip()
    scenes  = data.get("scenes", [])
    voice   = data.get("voice", "en-US-JennyNeural")
    fmt     = data.get("format", "vertical")    # "landscape" or "vertical"
    channel = data.get("channel", "bsg")        # "bsg" or "tmf"

    if not title:
        return jsonify({"error": "Please enter a video title."}), 400
    if len(scenes) < 1:
        return jsonify({"error": "Please add at least one scene."}), 400

    # Clear queue
    while not progress_queue.empty():
        try: progress_queue.get_nowait()
        except: pass

    thread = threading.Thread(target=run_video_job, args=(title, scenes, voice, fmt, channel), daemon=True)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/stream")
def stream():
    def event_stream():
        while True:
            try:
                item = progress_queue.get(timeout=30)
                yield f"data: {json.dumps(item)}\n\n"
                if "done" in item or "error" in item:
                    break
            except queue.Empty:
                yield "data: {\"ping\": true}\n\n"
    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/generate-script", methods=["POST"])
def generate_script():
    """
    Generate a full video script from a topic using GPT-4o.
    Accepts: { topic, channel, num_scenes }
    Returns: { script: { title, scenes: [{narration, image_prompt}] } }
    """
    data    = request.get_json()
    topic   = (data.get("topic") or "").strip()
    channel = data.get("channel", "bsg")
    n       = max(4, min(10, int(data.get("num_scenes", 7))))

    if not topic:
        return jsonify({"error": "Please enter a topic."}), 400

    api_key = get_openai_key()
    if not api_key:
        return jsonify({"error": "OpenAI API key required for script generation. Add it in Settings."}), 400

    # Channel-specific instructions
    if channel == "tmf":
        style_guide = (
            "Dark psychology / human behavior educational content for adults. "
            "Tone: calm, analytical, slightly unsettling. "
            "Image prompts MUST be atmospheric and symbolic — NO faces, NO people, NO portraits. "
            "Use objects, environments, shadows, hands (no face), silhouettes, abstract compositions. "
            "Examples of valid image prompts: burning money on a desk, broken clock on dark floor, "
            "empty interrogation chair under single light, heavy chains on concrete, "
            "cracked mirror reflection, locked door in dark corridor, pair of hands gripping a phone. "
            "Style: black and white / heavily desaturated film noir, high contrast, photorealistic."
        )
    else:
        style_guide = (
            "Bible story / children's educational content for families with young kids. "
            "Tone: warm, wonder-filled, simple, encouraging. "
            "Image prompts should be colorful, cheerful storybook illustration style. "
            "\n*** CRITICAL FOR ENGAGEMENT: ***\n"
            "Scene 1 MUST be a dramatic hook that stops scrolling. Start with a question or stunning visual, not exposition. "
            "Example: Don't open with 'Once upon a time...' — open with 'He was FACING CERTAIN DEATH. Then...' "
            "Scene 1 image: Make it VISUALLY STRIKING — bold colors, dramatic moment, something that makes people stop scrolling."
        )

    system_prompt = f"""You are a short-form video script writer optimized for YouTube Shorts (60 seconds).
CRITICAL: First 3 seconds determine if viewers keep watching. Hook them IMMEDIATELY.

Channel style: {style_guide}

Output ONLY valid JSON in this exact format:
{{
  "title": "Short punchy video title (under 60 chars)",
  "scenes": [
    {{
      "narration": "1-3 sentences of spoken narration. Keep it punchy and engaging.",
      "image_prompt": "Vivid scene description for AI image generation. Be specific about what and who is shown."
    }}
  ]
}}

Rules:
- Exactly {n} scenes
- SCENE 1 (0-2 sec): HOOK FIRST. Create curiosity or show something visually stunning. Don't explain — intrigue.
- Each narration: 20-40 words, conversational, hook-driven
- Pacing: Build momentum. Don't waste time. Each scene should reveal something new.
- Each image_prompt: specific, visual, cinematic — NOT abstract. For scene 1, make it ATTENTION-GRABBING.
- No markdown, no explanation, ONLY the JSON object"""

    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Write a {n}-scene script about: {topic}"}
            ],
            max_tokens=2000,
            temperature=0.8,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        script = json.loads(raw.strip())
        return jsonify({"script": script})
    except Exception as e:
        return jsonify({"error": f"Script generation failed: {str(e)[:120]}"}), 500


@app.route("/job-status")
def job_status():
    """Return current video generation job status."""
    return jsonify({
        "running": current_job.get("running", False),
        "output":  current_job.get("output"),
        "error":   current_job.get("error"),
    })


@app.route("/videos")
def list_videos():
    all_vids = []
    for ch, folder in CHANNEL_OUTPUT.items():
        for v in folder.glob("*.mp4"):
            all_vids.append({"name": v.name, "path": str(v), "channel": ch})
    all_vids.sort(key=lambda x: os.path.getmtime(x["path"]), reverse=True)
    return jsonify(all_vids)


@app.route("/video/<path:filename>")
def serve_video(filename):
    # Search all channel output folders for the file
    for folder in CHANNEL_OUTPUT.values():
        candidate = folder / filename
        if candidate.exists():
            return send_file(candidate)
    return "Video not found", 404


@app.route("/voices")
def list_voices():
    return jsonify([
        {"id": "en-US-JennyNeural",    "label": "Jenny — warm female (default)"},
        {"id": "en-US-AriaNeural",     "label": "Aria — soft female"},
        {"id": "en-US-MichelleNeural", "label": "Michelle — friendly female"},
        {"id": "en-US-GuyNeural",      "label": "Guy — calm male"},
        {"id": "en-US-DavisNeural",    "label": "Davis — deep male"},
    ])

@app.route("/voice-status")
def voice_status():
    return jsonify({
        "has_voice_file":  has_voice_file(),
        "has_xtts":        has_xtts(),
        "ready":           has_voice_file() and has_xtts(),
        "has_fal":         bool(get_fal_key()),
        "has_openai":      bool(get_openai_key()),
        "has_elevenlabs":  bool(get_elevenlabs_key()),
    })


@app.route("/save-config", methods=["POST"])
def save_config():
    """Save API keys to config.json from the Settings panel."""
    data = request.get_json() or {}
    try:
        cfg = {}
        if CONFIG_FILE.exists():
            try:
                cfg = json.loads(CONFIG_FILE.read_text())
            except Exception:
                cfg = {}
        if "openai_key" in data and data["openai_key"].strip():
            cfg["openai_api_key"] = data["openai_key"].strip()
        if "elevenlabs_key" in data and data["elevenlabs_key"].strip():
            cfg["elevenlabs_api_key"] = data["elevenlabs_key"].strip()
        if "fal_key" in data and data["fal_key"].strip():
            cfg["fal_api_key"] = data["fal_key"].strip()
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
#  YOUTUBE UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

YT_SECRETS_FILE = BASE_DIR / "youtube_client_secrets.json"
YT_SCOPES       = ["https://www.googleapis.com/auth/youtube.upload",
                   "https://www.googleapis.com/auth/youtube"]

# Each channel has its own token file — so BSG and TMF can be different YouTube accounts
YT_TOKEN_FILES = {
    "bsg": BASE_DIR / "youtube_token_bsg.json",
    "tmf": BASE_DIR / "youtube_token_tmf.json",
}

# Store active OAuth flow objects between /youtube-connect and /youtube-callback
# (needed to preserve the PKCE code_verifier across the redirect)
_yt_flows = {}

def _yt_libs_available():
    """Return True if the Google API libraries are installed."""
    try:
        import googleapiclient  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
        return True
    except ImportError:
        return False


def _load_yt_credentials(channel="bsg"):
    """Return valid Google credentials for the given channel, or None."""
    token_file = YT_TOKEN_FILES.get(channel)
    if not token_file or not token_file.exists():
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(str(token_file), YT_SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())
        return creds if creds.valid else None
    except Exception:
        return None


@app.route("/youtube-status")
def youtube_status():
    """Check library install, secrets file, and per-channel connection status."""
    libs_ok    = _yt_libs_available()
    secrets_ok = YT_SECRETS_FILE.exists()
    return jsonify({
        "libs_installed": libs_ok,
        "secrets_file":   secrets_ok,
        "bsg_connected":  _load_yt_credentials("bsg") is not None if libs_ok else False,
        "tmf_connected":  _load_yt_credentials("tmf") is not None if libs_ok else False,
    })


@app.route("/youtube-connect")
def youtube_connect():
    """Start the OAuth2 flow for a specific channel — ?channel=bsg or ?channel=tmf."""
    channel = request.args.get("channel", "bsg")
    if channel not in ("bsg", "tmf"):
        return jsonify({"error": "Invalid channel."}), 400
    if not _yt_libs_available():
        return jsonify({"error": "Google libraries not installed. Run: pip3 install google-api-python-client google-auth-httplib2 google-auth-oauthlib"}), 400
    if not YT_SECRETS_FILE.exists():
        return jsonify({"error": "youtube_client_secrets.json not found in project folder. Download it from Google Cloud Console."}), 400
    try:
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_secrets_file(
            str(YT_SECRETS_FILE),
            scopes=YT_SCOPES,
            redirect_uri=f"http://localhost:5002/youtube-callback?channel={channel}"
        )
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
        # Store the flow so the callback can reuse it (preserves PKCE code_verifier)
        _yt_flows[channel] = flow
        return jsonify({"auth_url": auth_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/youtube-callback")
def youtube_callback():
    """Handle OAuth2 callback — saves token to the correct channel token file."""
    code    = request.args.get("code")
    channel = request.args.get("channel", "bsg")
    if not code:
        return "<h2>❌ No code received. Try connecting again.</h2>", 400
    token_file = YT_TOKEN_FILES.get(channel)
    if not token_file:
        return "<h2>❌ Unknown channel.</h2>", 400
    try:
        # Reuse the stored flow (contains the PKCE code_verifier from the connect step)
        flow = _yt_flows.get(channel)
        if flow is None:
            # Fallback: rebuild flow without PKCE if session was lost
            from google_auth_oauthlib.flow import Flow
            flow = Flow.from_client_secrets_file(
                str(YT_SECRETS_FILE),
                scopes=YT_SCOPES,
                redirect_uri=f"http://localhost:5002/youtube-callback?channel={channel}"
            )
        flow.fetch_token(code=code)
        creds = flow.credentials
        token_file.write_text(creds.to_json())
        _yt_flows.pop(channel, None)   # Clean up stored flow
        label = "Bible Story Garden" if channel == "bsg" else "The Mind Files"
        return f"""<html><body style="font-family:sans-serif;padding:40px;background:#FAF4EC;">
            <h2 style="color:#2D6A4F;">✅ {label} Connected!</h2>
            <p style="margin-top:12px;color:#444;">Your YouTube channel is now linked. You can close this tab and return to the Video Studio.</p>
            <script>setTimeout(()=>window.close(),3000);</script>
            </body></html>"""
    except Exception as e:
        return f"<h2>❌ Error: {e}</h2>", 500


@app.route("/youtube-upload", methods=["POST"])
def youtube_upload():
    """Upload a video to the correct YouTube channel based on the 'channel' field."""
    if not _yt_libs_available():
        return jsonify({"error": "Google libraries not installed. Run: pip3 install google-api-python-client google-auth-httplib2 google-auth-oauthlib"}), 400

    data    = request.get_json()
    channel = data.get("channel", "bsg")

    creds = _load_yt_credentials(channel)
    if not creds:
        label = "Bible Story Garden" if channel == "bsg" else "The Mind Files"
        return jsonify({"error": f"{label} YouTube channel is not connected. Go to Settings → YouTube Auto-Post and connect it first."}), 401

    video_path  = data.get("video_path", "")
    title       = data.get("title", "My Video")
    description = data.get("description", "")
    tags        = [t.strip() for t in data.get("tags", "").split(",") if t.strip()]
    privacy     = data.get("privacy", "private")

    # Find the video file in the channel's output folder
    vid_file = None
    for folder in CHANNEL_OUTPUT.values():
        candidate = folder / video_path
        if candidate.exists():
            vid_file = candidate
            break
    if not vid_file:
        return jsonify({"error": f"Video file not found: {video_path}"}), 404

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title":       title[:100],
                "description": description,
                "tags":        tags[:30],
                "categoryId":  "27",   # Education
            },
            "status": {
                "privacyStatus":          privacy,
                "selfDeclaredMadeForKids": channel == "bsg",
            }
        }

        media = MediaFileUpload(str(vid_file), chunksize=-1, resumable=True,
                                mimetype="video/mp4")
        request_obj = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            _, response = request_obj.next_chunk()

        video_id  = response["id"]
        video_url = f"https://www.youtube.com/shorts/{video_id}"
        return jsonify({"status": "uploaded", "video_id": video_id, "url": video_url})

    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)[:200]}"}), 500


@app.route("/youtube-disconnect", methods=["POST"])
def youtube_disconnect():
    """Remove saved YouTube token for a specific channel — ?channel=bsg or ?channel=tmf."""
    channel    = (request.get_json() or {}).get("channel", "bsg")
    token_file = YT_TOKEN_FILES.get(channel)
    if token_file and token_file.exists():
        token_file.unlink()
    return jsonify({"status": "disconnected", "channel": channel})


# ══════════════════════════════════════════════════════════════════════════════
#  HTML TEMPLATE
# ══════════════════════════════════════════════════════════════════════════════

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Video Studio — MidwestMade4U</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --sidebar-dark:  #2A1F14;
  --amber:         #C8923A;
  --amber-light:   #F5E6CC;
  --amber-dark:    #A0731F;
  --wood:          #7D5235;
  --cream:         #FAF4EC;
  --bg:            #F0E8DC;
  --card:          #FFFFFF;
  --border:        #E0D0BC;
  --text:          #2A1F14;
  --muted:         #9E8879;
  --sidebar-w:     220px;
  --header-h:      54px;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, sans-serif;
  background: var(--bg);
  color: var(--text);
  display: flex;
  min-height: 100vh;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
#sidebar {
  width: var(--sidebar-w);
  min-width: var(--sidebar-w);
  background: #FFFFFF;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0; left: 0; bottom: 0;
  z-index: 100;
  box-shadow: 2px 0 16px rgba(42,31,20,0.06);
}
.sidebar-logo-bar {
  background: var(--sidebar-dark);
  padding: 0 18px;
  height: var(--header-h);
  display: flex; align-items: center; gap: 10px; flex-shrink: 0;
}
.logo-icon { font-size: 20px; }
.logo-text { font-size: 13px; font-weight: 700; color: var(--amber); letter-spacing: 0.04em; line-height:1.2; }
.logo-sub  { font-size: 10px; color: rgba(255,255,255,0.4); letter-spacing: 0.03em; }

.sidebar-nav { flex: 1; overflow-y: auto; padding: 12px 0 24px; }
.nav-group-label {
  font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
  color: var(--muted); padding: 14px 18px 6px; text-transform: uppercase;
}
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 18px; font-size: 13px; font-weight: 500;
  color: #5A4535; cursor: pointer; border: none; background: none;
  width: 100%; text-align: left; border-left: 3px solid transparent;
  transition: all 0.15s;
}
.nav-item:hover { background: var(--amber-light); color: var(--wood); }
.nav-item.active { background: var(--amber-light); border-left-color: var(--amber); color: var(--sidebar-dark); font-weight: 700; }
.nav-icon { font-size: 15px; width: 20px; text-align: center; }
.sidebar-footer { padding: 14px 18px; border-top: 1px solid var(--border); font-size: 11px; color: var(--muted); }

/* ── Main ──────────────────────────────────────────────────────────────── */
#main { margin-left: var(--sidebar-w); flex: 1; display: flex; flex-direction: column; min-height: 100vh; }
#main-header {
  height: var(--header-h); background: var(--sidebar-dark);
  display: flex; align-items: center; padding: 0 28px; gap: 14px;
  position: sticky; top: 0; z-index: 90;
  box-shadow: 0 2px 12px rgba(0,0,0,0.18);
}
#panel-title { font-size: 15px; font-weight: 700; color: #FFF; letter-spacing: 0.02em; }
.header-badge {
  font-size: 11px; background: var(--amber); color: white;
  padding: 3px 10px; border-radius: 20px; font-weight: 700; letter-spacing: 0.06em;
}
.yt-badge {
  margin-left: auto; font-size: 11px; padding: 3px 10px; border-radius: 20px;
  font-weight: 700; background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.6);
  cursor: pointer; transition: all 0.2s;
}
.yt-badge.connected { background: #FF0000; color: white; }

/* ── Panels ─────────────────────────────────────────────────────────────── */
.panel { display: none; padding: 28px; }
.panel.active { display: block; }

/* ── Cards ──────────────────────────────────────────────────────────────── */
.card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 1px 8px rgba(42,31,20,0.05); }
.card-title { font-size: 12px; font-weight: 700; color: var(--wood); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }

/* ── Form ───────────────────────────────────────────────────────────────── */
label { font-size: 12px; color: var(--muted); display: block; margin-bottom: 5px; font-weight: 500; }
input[type=text], input[type=password], textarea, select {
  width: 100%; background: var(--cream); border: 1px solid var(--border);
  border-radius: 8px; color: var(--text); padding: 9px 13px;
  font-size: 14px; font-family: inherit; transition: border-color 0.18s;
}
input[type=text]:focus, input[type=password]:focus, textarea:focus, select:focus {
  outline: none; border-color: var(--amber); box-shadow: 0 0 0 3px rgba(200,146,58,0.12);
}
textarea { resize: vertical; min-height: 70px; }
select { cursor: pointer; }

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.btn { display: inline-flex; align-items: center; gap: 7px; padding: 10px 20px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: all 0.18s; white-space: nowrap; }
.btn-primary  { background: var(--amber); color: white; }
.btn-primary:hover  { background: var(--amber-dark); }
.btn-primary:disabled { background: #E0D0BC; color: var(--muted); cursor: not-allowed; }
.btn-secondary { background: var(--wood); color: white; }
.btn-secondary:hover { background: #6A4428; }
.btn-red { background: #cc0000; color: white; }
.btn-red:hover { background: #aa0000; }
.btn-ghost { background: transparent; border: 1px solid var(--border); color: var(--muted); padding: 8px 14px; font-size: 12px; }
.btn-ghost:hover { border-color: var(--amber); color: var(--text); background: var(--cream); }
.btn-full { width: 100%; justify-content: center; padding: 14px; font-size: 15px; border-radius: 10px; }
.btn-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 12px; }

/* ── Channel selector ────────────────────────────────────────────────────── */
.channel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.ch-btn { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 10px; border-radius: 10px; border: 2px solid var(--border); background: var(--cream); color: var(--muted); cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.18s; text-align: center; }
.ch-btn .ch-icon { font-size: 26px; }
.ch-btn .ch-sub  { font-size: 10px; font-weight: 400; color: var(--muted); }
.ch-btn:hover  { border-color: var(--amber); color: var(--text); }
.ch-btn.active { border-color: var(--amber); background: var(--amber-light); color: var(--sidebar-dark); }
.ch-btn.active .ch-sub { color: var(--wood); }

/* ── Create layout ───────────────────────────────────────────────────────── */
.create-layout { display: grid; grid-template-columns: 1fr 280px; gap: 24px; align-items: start; max-width: 1000px; }
.create-main { min-width: 0; }
.create-side { position: sticky; top: calc(var(--header-h) + 28px); }

/* ── Script collapse ─────────────────────────────────────────────────────── */
.script-toggle { display: flex; align-items: center; justify-content: space-between; cursor: pointer; user-select: none; margin-bottom: 6px; }
.script-toggle .toggle-label { font-size: 12px; font-weight: 600; color: var(--wood); }
.script-toggle .toggle-arrow { font-size: 11px; color: var(--muted); transition: transform 0.2s; }
.script-toggle.open .toggle-arrow { transform: rotate(180deg); }
#script-collapse { display: none; }
#script-collapse.open { display: block; }

/* ── Phone frame ─────────────────────────────────────────────────────────── */
.phone-device { position: relative; width: 100%; max-width: 240px; margin: 0 auto; background: #1c1c1e; border-radius: 44px; padding: 12px 9px; box-shadow: 0 0 0 1px #3a3a3c, 0 0 0 3px #111, 0 20px 60px rgba(0,0,0,0.7); }
.phone-device::before { content: ""; position: absolute; left: -3px; top: 68px; width: 3px; height: 24px; background: #2c2c2e; border-radius: 2px 0 0 2px; box-shadow: 0 32px 0 #2c2c2e, 0 56px 0 #2c2c2e; }
.phone-device::after  { content: ""; position: absolute; right: -3px; top: 86px; width: 3px; height: 38px; background: #2c2c2e; border-radius: 0 2px 2px 0; }
.phone-notch { width: 80px; height: 20px; background: #1c1c1e; border-radius: 0 0 16px 16px; margin: 0 auto 6px; display: flex; align-items: center; justify-content: center; gap: 7px; }
.phone-camera  { width: 8px; height: 8px; background: #0a0a0a; border-radius: 50%; border: 1.5px solid #2a2a2a; }
.phone-speaker { width: 32px; height: 4px; background: #111; border-radius: 2px; }
.phone-screen { border-radius: 20px; overflow: hidden; background: #111; aspect-ratio: 9/16; width: 100%; line-height: 0; }
.phone-screen video { width: 100%; height: 100%; display: block; object-fit: cover; }
.phone-bar { width: 70px; height: 4px; background: #3a3a3c; border-radius: 2px; margin: 9px auto 2px; }
.phone-placeholder { width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; background: #1a1008; color: #6A5040; font-size: 11px; text-align: center; padding: 20px; min-height: 180px; }
.phone-placeholder .ph-icon { font-size: 28px; opacity: 0.5; }
.phone-label { text-align: center; font-size: 11px; color: var(--muted); margin-top: 10px; }

/* ── Progress ─────────────────────────────────────────────────────────────── */
#progress-section { display: none; }
.progress-bar-wrap { background: #EDE3D8; border-radius: 100px; height: 6px; margin: 12px 0; overflow: hidden; }
.progress-bar { height: 100%; background: linear-gradient(90deg, var(--wood), var(--amber)); border-radius: 100px; width: 0%; transition: width 0.5s ease; }
.log-box { background: #1E1008; border: 1px solid #3A2818; border-radius: 8px; padding: 12px 14px; font-family: "SF Mono", monospace; font-size: 11px; color: #C8B8A0; max-height: 180px; overflow-y: auto; line-height: 1.8; }
.log-done { color: #6EC99A; }
.log-warn { color: var(--amber); }
.log-err  { color: #E07878; }

/* ── Output & YouTube post ───────────────────────────────────────────────── */
#output-section { display: none; }
.output-actions { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
.yt-post-row { display: flex; gap: 10px; align-items: flex-start; flex-wrap: wrap; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }
.yt-post-fields { flex: 1; min-width: 220px; }
.yt-privacy-row { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.yt-privacy-row select { width: auto; flex: 1; }
#yt-post-status { font-size: 12px; margin-top: 6px; }

/* ── Past videos ─────────────────────────────────────────────────────────── */
.video-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px; margin-top: 4px; }
.vid-card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; transition: box-shadow 0.18s; }
.vid-card:hover { box-shadow: 0 4px 20px rgba(42,31,20,0.12); }
.vid-thumb { aspect-ratio: 9/16; background: #1a1008; overflow: hidden; }
.vid-thumb video { width: 100%; height: 100%; object-fit: cover; }
.vid-info { padding: 10px 12px; }
.vid-name { font-size: 12px; font-weight: 600; color: var(--text); margin-bottom: 6px; line-height: 1.3; }
.vid-badge { display: inline-block; font-size: 9px; padding: 2px 7px; border-radius: 20px; font-weight: 700; letter-spacing: 0.05em; margin-bottom: 8px; }
.badge-bsg { background: rgba(125,82,53,0.12); color: var(--wood); }
.badge-tmf { background: rgba(200,146,58,0.18); color: var(--amber-dark); }
.vid-actions { display: flex; gap: 6px; }

/* ── Settings accordion ──────────────────────────────────────────────────── */
.accordion-item { border: 1px solid var(--border); border-radius: 10px; margin-bottom: 10px; overflow: hidden; }
.accordion-header { display: flex; align-items: center; justify-content: space-between; padding: 13px 18px; cursor: pointer; background: var(--card); font-size: 14px; font-weight: 600; color: var(--text); user-select: none; transition: background 0.15s; }
.accordion-header:hover { background: var(--cream); }
.accordion-arrow { font-size: 12px; color: var(--muted); transition: transform 0.2s; }
.accordion-header.open .accordion-arrow { transform: rotate(180deg); }
.accordion-body { display: none; padding: 18px; background: var(--cream); border-top: 1px solid var(--border); }
.accordion-body.open { display: block; }
.settings-row { margin-bottom: 14px; }
.settings-row:last-child { margin-bottom: 0; }
.info-pill { font-size: 12px; padding: 8px 14px; border-radius: 8px; background: var(--amber-light); color: var(--wood); border-left: 3px solid var(--amber); margin-top: 8px; line-height: 1.6; }
.el-notice { display: none; margin-top: 8px; font-size: 12px; padding: 8px 12px; border-radius: 6px; border-left: 3px solid var(--amber); background: #FFF8EE; color: var(--amber-dark); }

/* ── Guide ───────────────────────────────────────────────────────────────── */
.guide-step { display: flex; gap: 16px; margin-bottom: 18px; }
.step-num { width: 32px; height: 32px; min-width: 32px; background: var(--amber); color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; }
.step-text h3 { font-size: 14px; font-weight: 700; margin-bottom: 4px; }
.step-text p  { font-size: 13px; color: var(--muted); line-height: 1.6; }

@media (max-width: 900px) {
  :root { --sidebar-w: 0px; }
  #sidebar { display: none; }
  #main { margin-left: 0; }
  .create-layout { grid-template-columns: 1fr; }
  .create-side { position: static; }
}
</style>
</head>
<body>

<!-- ═══ SIDEBAR ═══════════════════════════════════════════════════════════ -->
<div id="sidebar">
  <div class="sidebar-logo-bar">
    <div class="logo-icon">🎬</div>
    <div>
      <div class="logo-text">MidwestMade4U</div>
      <div class="logo-sub">VIDEO STUDIO</div>
    </div>
  </div>
  <nav class="sidebar-nav">
    <div class="nav-group-label">Create</div>
    <button class="nav-item active" id="nav-create"   onclick="showPanel('create')"><span class="nav-icon">✏️</span> Create Video</button>
    <button class="nav-item"        id="nav-past"     onclick="showPanel('past')"><span class="nav-icon">📁</span> View Videos</button>
    <div class="nav-group-label">Manage</div>
    <button class="nav-item"        id="nav-settings" onclick="showPanel('settings')"><span class="nav-icon">⚙️</span> Settings</button>
    <div class="nav-group-label">Info</div>
    <button class="nav-item"        id="nav-guide"    onclick="showPanel('guide')"><span class="nav-icon">📖</span> How It Works</button>
  </nav>
  <div class="sidebar-footer">📱 All videos: 9:16 Reels format</div>
</div>

<!-- ═══ MAIN ══════════════════════════════════════════════════════════════ -->
<div id="main">
  <div id="main-header">
    <div id="panel-title">Create Video</div>
    <div class="header-badge" id="channel-badge">THE MIND FILES</div>
    <div class="yt-badge" id="yt-header-badge" onclick="showPanel('settings')">YouTube: checking...</div>
  </div>

  <!-- ─── CREATE PANEL ─────────────────────────────────────────────────── -->
  <div class="panel active" id="panel-create">
    <div class="create-layout">

      <!-- Left: forms -->
      <div class="create-main">

        <!-- Channel -->
        <div class="card">
          <div class="card-title">📺 Channel</div>
          <div class="channel-grid">
            <button class="ch-btn" id="ch-bsg" onclick="setChannel('bsg')">
              <span class="ch-icon">✝️</span>
              <span>Bible Story Garden</span>
              <span class="ch-sub">Kids · Colorful Storybook</span>
            </button>
            <button class="ch-btn active" id="ch-tmf" onclick="setChannel('tmf')">
              <span class="ch-icon">🧠</span>
              <span>The Mind Files</span>
              <span class="ch-sub">Psychology · Dark Cinema</span>
            </button>
          </div>
        </div>

        <!-- Topic + one-click generate -->
        <div class="card">
          <div class="card-title">✨ Describe Your Video</div>
          <p style="font-size:12px;color:var(--muted);margin-bottom:12px;">Type what the video is about — or paste the topic from your Excel file. AI handles the rest.</p>
          <label>Topic / description</label>
          <textarea id="topic-input" rows="3" placeholder="e.g. Jonah and the Whale — Jonah runs from God, gets swallowed by a whale, and learns obedience

Or shorter: Why You Can't Leave a Toxic Relationship"></textarea>
          <div style="display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap;">
            <div>
              <label style="margin-bottom:3px;">Scenes</label>
              <select id="num-scenes-select" style="height:36px;padding:0 10px;width:72px;">
                <option value="5">5</option>
                <option value="6">6</option>
                <option value="7" selected>7</option>
                <option value="8">8</option>
                <option value="9">9</option>
              </select>
            </div>
            <div style="flex:1;">
              <label style="margin-bottom:3px;">Voice</label>
              <select id="voice-select" style="height:36px;">
                <optgroup label="⭐ ElevenLabs Premium (add key in Settings to unlock)">
                  <option value="el_sarah">Sarah — warm female ✨</option>
                  <option value="el_rachel">Rachel — calm female ✨</option>
                  <option value="el_adam">Adam — deep male ✨</option>
                  <option value="el_josh">Josh — deep male ✨</option>
                </optgroup>
                <optgroup label="Free Voices (Microsoft)">
                  <option value="en-US-MichelleNeural" selected>Michelle — friendly female</option>
                  <option value="en-US-JennyNeural">Jenny — warm female</option>
                  <option value="en-US-AriaNeural">Aria — soft female</option>
                  <option value="en-US-GuyNeural">Guy — calm male</option>
                  <option value="en-US-DavisNeural">Davis — deep male</option>
                </optgroup>
                <optgroup label="Voice Clone">
                  <option value="my_voice" id="my-voice-option">🎤 My Voice Clone (needs setup)</option>
                </optgroup>
              </select>
            </div>
          </div>
          <div class="el-notice" id="el-notice">✨ ElevenLabs voices require an API key — add yours in Settings.</div>
        </div>

        <!-- Collapsible: review/edit script -->
        <div class="card" id="script-card" style="display:none;">
          <div class="script-toggle open" id="script-toggle" onclick="toggleScript()">
            <span class="toggle-label">📋 Review / Edit Script (optional)</span>
            <span class="toggle-arrow">▼</span>
          </div>
          <div id="script-collapse" class="open">
            <p style="font-size:11px;color:var(--muted);margin-bottom:8px;">The AI-generated script is shown below. You can edit narration or image prompts before generating.</p>
            <textarea id="script-input" style="min-height:200px;font-family:'SF Mono',monospace;font-size:11px;line-height:1.6;"></textarea>
          </div>
        </div>

        <!-- Generate buttons -->
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;">
          <button class="btn btn-secondary" id="gen-script-btn" onclick="generateScript(false)" style="flex:1;">
            ✨ Preview Script First
          </button>
          <button class="btn btn-primary btn-full" id="generate-btn" onclick="generateScript(true)" style="flex:2;">
            🎬 Generate Video
          </button>
        </div>
        <div id="gen-status" style="font-size:12px;color:var(--muted);margin-bottom:8px;"></div>

        <!-- Progress -->
        <div class="card" id="progress-section" style="margin-top:4px;">
          <div class="card-title">⏳ Generating...</div>
          <div class="progress-bar-wrap"><div class="progress-bar" id="progress-bar"></div></div>
          <div class="log-box" id="log-box"></div>
        </div>

        <!-- Output -->
        <div class="card" id="output-section" style="margin-top:4px;">
          <div class="card-title">✅ Video Ready!</div>
          <div id="video-wrap"></div>
          <div class="output-actions">
            <a id="download-link" class="btn btn-secondary" download>⬇️ Download MP4</a>
            <button class="btn btn-ghost" onclick="makeAnother()">🔄 New Video</button>
          </div>
          <!-- YouTube post section -->
          <div class="yt-post-row" id="yt-post-row" style="display:none;">
            <div class="yt-post-fields">
              <div class="card-title" style="margin-bottom:10px;">🔴 Post to YouTube</div>
              <div class="settings-row">
                <label>Video Title (for YouTube)</label>
                <input type="text" id="yt-title-input" placeholder="Auto-filled from your script..." maxlength="100" />
              </div>
              <div class="settings-row">
                <label>Description (optional — paste from Excel Col D)</label>
                <textarea id="yt-desc-input" rows="3" placeholder="Optional description..."></textarea>
              </div>
              <div class="settings-row">
                <label>Tags (optional — paste from Excel Col E, comma-separated)</label>
                <input type="text" id="yt-tags-input" placeholder="tag1, tag2, tag3..." />
              </div>
              <div class="yt-privacy-row">
                <label style="margin:0;white-space:nowrap;">Privacy:</label>
                <select id="yt-privacy">
                  <option value="private">🔒 Private (review before posting)</option>
                  <option value="unlisted">🔗 Unlisted</option>
                  <option value="public">🌍 Public</option>
                </select>
                <button class="btn btn-red" id="yt-post-btn" onclick="postToYouTube()">🚀 Post Now</button>
              </div>
              <div id="yt-post-status"></div>
            </div>
          </div>
          <div id="yt-connect-prompt" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);font-size:12px;color:var(--muted);">
            <a onclick="showPanel('settings')" style="color:var(--amber);cursor:pointer;font-weight:600;">⚙️ Connect YouTube in Settings</a> to enable one-click posting.
          </div>
        </div>

      </div><!-- /create-main -->

      <!-- Right: phone preview -->
      <div class="create-side">
        <div class="card">
          <div class="card-title">📱 Preview</div>
          <div class="phone-device">
            <div class="phone-notch">
              <div class="phone-speaker"></div>
              <div class="phone-camera"></div>
            </div>
            <div class="phone-screen" id="side-phone-screen">
              <div class="phone-placeholder">
                <div class="ph-icon">🎬</div>
                <div>Your video<br>appears here</div>
              </div>
            </div>
            <div class="phone-bar"></div>
          </div>
          <div class="phone-label">9:16 · Shorts / Reels</div>
        </div>
      </div>

    </div><!-- /create-layout -->
  </div><!-- /panel-create -->

  <!-- ─── PAST VIDEOS ──────────────────────────────────────────────────── -->
  <div class="panel" id="panel-past">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
      <div>
        <h2 style="font-size:18px;font-weight:700;">Past Videos</h2>
        <p style="font-size:13px;color:var(--muted);margin-top:4px;">All generated videos — play, download, or post to YouTube.</p>
      </div>
      <button class="btn btn-ghost" onclick="loadHistory()">🔄 Refresh</button>
    </div>
    <div id="history-list"><p style="color:var(--muted);font-size:13px;">Loading videos...</p></div>
  </div>

  <!-- ─── SETTINGS ─────────────────────────────────────────────────────── -->
  <div class="panel" id="panel-settings">
    <div style="margin-bottom:20px;">
      <h2 style="font-size:18px;font-weight:700;">Settings</h2>
      <p style="font-size:13px;color:var(--muted);margin-top:4px;">API keys, YouTube connection, and preferences.</p>
    </div>

    <!-- API Keys -->
    <div class="accordion-item">
      <div class="accordion-header open" onclick="toggleAccordion(this)">
        <span>🔑 API Keys</span><span class="accordion-arrow">▼</span>
      </div>
      <div class="accordion-body open">
        <!-- fal.ai — primary image engine -->
        <div class="settings-row" style="border:2px solid var(--amber);border-radius:10px;padding:14px;background:var(--amber-light);">
          <label style="color:var(--sidebar-dark);font-size:13px;font-weight:700;">🎨 fal.ai API Key <span style="background:var(--amber);color:white;font-size:10px;padding:2px 8px;border-radius:20px;margin-left:6px;font-weight:700;">PRIMARY IMAGE ENGINE</span></label>
          <div style="font-size:11px;color:var(--wood);margin-bottom:8px;margin-top:4px;">Flux Pro — best quality images at ~40% less cost than DALL-E. <strong>Recommended.</strong></div>
          <div style="display:flex;gap:8px;">
            <input type="password" id="fal-key-input" placeholder="Your fal.ai key..." />
            <button class="btn btn-primary" onclick="saveKeys()">Save</button>
          </div>
          <div style="margin-top:6px;font-size:11px;color:var(--muted);">Get free key (includes credits): <a href="https://fal.ai/dashboard/keys" target="_blank" style="color:var(--amber);font-weight:600;">fal.ai/dashboard/keys</a></div>
          <div id="fal-key-status" style="font-size:11px;margin-top:4px;"></div>
        </div>
        <div class="settings-row">
          <label>OpenAI API Key <span style="color:var(--muted);font-weight:400;">(GPT script writing + DALL-E backup images)</span></label>
          <div style="display:flex;gap:8px;">
            <input type="password" id="openai-key-input" placeholder="sk-..." />
            <button class="btn btn-secondary" onclick="saveKeys()">Save</button>
          </div>
          <div style="margin-top:5px;font-size:11px;color:var(--muted);">Get key: <a href="https://platform.openai.com/api-keys" target="_blank" style="color:var(--amber);">platform.openai.com/api-keys</a></div>
        </div>
        <div class="settings-row">
          <label>ElevenLabs API Key <span style="color:var(--muted);font-weight:400;">(premium voices — optional)</span></label>
          <div style="display:flex;gap:8px;">
            <input type="password" id="elevenlabs-key-input" placeholder="Your ElevenLabs key..." />
            <button class="btn btn-secondary" onclick="saveKeys()">Save</button>
          </div>
          <div style="margin-top:5px;font-size:11px;color:var(--muted);">Get key: <a href="https://elevenlabs.io/app/settings/api-keys" target="_blank" style="color:var(--amber);">elevenlabs.io → Profile (bottom-left) → API Keys</a></div>
        </div>
        <div id="save-status" style="font-size:12px;color:var(--wood);display:none;"></div>
      </div>
    </div>

    <!-- YouTube -->
    <div class="accordion-item">
      <div class="accordion-header open" onclick="toggleAccordion(this)">
        <span>🔴 YouTube Auto-Post</span><span class="accordion-arrow">▼</span>
      </div>
      <div class="accordion-body open">
        <div class="info-pill" style="margin-bottom:16px;">
          <strong>One-time setup (5 min):</strong><br>
          1. In Terminal: <code style="background:rgba(0,0,0,0.08);padding:2px 6px;border-radius:4px;">pip3 install google-api-python-client google-auth-httplib2 google-auth-oauthlib</code><br>
          2. Go to <a href="https://console.cloud.google.com" target="_blank" style="color:var(--amber);">console.cloud.google.com</a> → create a project → enable YouTube Data API v3<br>
          3. Create OAuth 2.0 credentials (type: Desktop app) → download as <strong>youtube_client_secrets.json</strong><br>
          4. Drop that file into your <strong>Youtube Channels Project</strong> folder<br>
          5. Connect each channel below — you sign in separately for each so BSG and TMF post to the correct account
        </div>

        <!-- BSG row -->
        <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:rgba(125,82,53,0.06);border-radius:8px;margin-bottom:10px;border:1px solid var(--border);">
          <div>
            <div style="font-weight:700;font-size:13px;">✝️ Bible Story Garden</div>
            <div id="yt-bsg-status-text" style="font-size:11px;color:var(--muted);margin-top:2px;">Checking...</div>
          </div>
          <div style="display:flex;gap:8px;">
            <button class="btn btn-red" id="yt-bsg-connect-btn" onclick="connectYouTube('bsg')" style="font-size:12px;padding:7px 14px;">Connect</button>
            <button class="btn btn-ghost" id="yt-bsg-disconnect-btn" style="font-size:12px;padding:7px 12px;display:none;" onclick="disconnectYouTube('bsg')">Disconnect</button>
          </div>
        </div>

        <!-- TMF row -->
        <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:rgba(200,146,58,0.06);border-radius:8px;margin-bottom:10px;border:1px solid var(--border);">
          <div>
            <div style="font-weight:700;font-size:13px;">🧠 The Mind Files</div>
            <div id="yt-tmf-status-text" style="font-size:11px;color:var(--muted);margin-top:2px;">Checking...</div>
          </div>
          <div style="display:flex;gap:8px;">
            <button class="btn btn-red" id="yt-tmf-connect-btn" onclick="connectYouTube('tmf')" style="font-size:12px;padding:7px 14px;">Connect</button>
            <button class="btn btn-ghost" id="yt-tmf-disconnect-btn" style="font-size:12px;padding:7px 12px;display:none;" onclick="disconnectYouTube('tmf')">Disconnect</button>
          </div>
        </div>

        <div id="yt-connect-status" style="font-size:12px;margin-top:6px;color:var(--muted);"></div>
      </div>
    </div>

    <!-- Visual Style -->
    <div class="accordion-item">
      <div class="accordion-header" onclick="toggleAccordion(this)">
        <span>🎨 Visual Style</span><span class="accordion-arrow">▼</span>
      </div>
      <div class="accordion-body">
        <div class="info-pill">
          <strong>BSG:</strong> Colorful storybook illustration · warm &amp; cheerful · child-safe · amber caption accent<br>
          <strong>TMF:</strong> Black &amp; white film noir · atmospheric objects, NO faces · yellow caption accent
        </div>
      </div>
    </div>

    <!-- Audio -->
    <div class="accordion-item">
      <div class="accordion-header" onclick="toggleAccordion(this)">
        <span>🎵 Background Music</span><span class="accordion-arrow">▼</span>
      </div>
      <div class="accordion-body">
        <div class="info-pill">
          Drop MP3 files into the <strong>bsg_music/</strong> folder in your project directory. They'll be auto-mixed into BSG videos at low volume.
        </div>
      </div>
    </div>

  </div><!-- /panel-settings -->

  <!-- ─── HOW IT WORKS ──────────────────────────────────────────────────── -->
  <div class="panel" id="panel-guide">
    <h2 style="font-size:18px;font-weight:700;margin-bottom:20px;">How It Works</h2>
    <div class="card" style="max-width:680px;">
      <div class="card-title">Creating a Video</div>
      <div class="guide-step"><div class="step-num">1</div><div class="step-text"><h3>Choose your channel</h3><p>Bible Story Garden (colorful kids stories) or The Mind Files (dark psychology for adults).</p></div></div>
      <div class="guide-step"><div class="step-num">2</div><div class="step-text"><h3>Type or paste your topic</h3><p>Copy the <strong>Video Topic</strong> from Column C of your Excel file, or just type a description of what you want.</p></div></div>
      <div class="guide-step"><div class="step-num">3</div><div class="step-text"><h3>Preview or go straight to video</h3><p>Click <strong>Preview Script First</strong> to review the AI-written narration before generating. Or click <strong>Generate Video</strong> to do everything in one shot.</p></div></div>
      <div class="guide-step"><div class="step-num">4</div><div class="step-text"><h3>Post to YouTube</h3><p>Once the video is done, click <strong>Post to YouTube</strong>. Paste the description and tags from your Excel file. Set privacy to Private first so you can review before going public.</p></div></div>
    </div>
    <div class="card" style="max-width:680px;">
      <div class="card-title">Where to Find Things</div>
      <p style="font-size:13px;line-height:2;color:var(--text);">
        📹 <strong>Finished videos:</strong> BSG_Output/ and TMF_Output/<br>
        📊 <strong>YouTube metadata:</strong> BSG_Channel/YouTube_Metadata/YouTube_Metadata.xlsx<br>
        🔑 <strong>API keys:</strong> Settings → API Keys<br>
        🔴 <strong>YouTube connection:</strong> Settings → YouTube Auto-Post
      </p>
    </div>
  </div>

</div><!-- /main -->

<script>
// ════════════════════════════════════════════════════════════
// Panel nav
// ════════════════════════════════════════════════════════════
const PANEL_TITLES = { create:"Create Video", past:"Past Videos", settings:"Settings", guide:"How It Works" };

function showPanel(name) {
  ["create","past","settings","guide"].forEach(p => {
    document.getElementById("panel-" + p).classList.toggle("active", p === name);
    const n = document.getElementById("nav-" + p);
    if (n) n.classList.toggle("active", p === name);
  });
  document.getElementById("panel-title").textContent = PANEL_TITLES[name] || name;
  if (name === "past") loadHistory();
}

// ════════════════════════════════════════════════════════════
// Channel
// ════════════════════════════════════════════════════════════
let selectedChannel = "tmf";
let lastVideoFilename = "";
let lastVideoTitle    = "";

function setChannel(ch) {
  selectedChannel = ch;
  document.getElementById("ch-bsg").classList.toggle("active", ch === "bsg");
  document.getElementById("ch-tmf").classList.toggle("active", ch === "tmf");
  document.getElementById("channel-badge").textContent = ch === "bsg" ? "BIBLE STORY GARDEN" : "THE MIND FILES";
}

// ════════════════════════════════════════════════════════════
// Script toggle
// ════════════════════════════════════════════════════════════
function toggleScript() {
  const toggle = document.getElementById("script-toggle");
  const body   = document.getElementById("script-collapse");
  toggle.classList.toggle("open");
  body.classList.toggle("open");
}

// ════════════════════════════════════════════════════════════
// Generate Script (and optionally go straight to video)
// ════════════════════════════════════════════════════════════
let totalScenes = 0, completedScenes = 0;

async function generateScript(andCreateVideo) {
  const topic  = document.getElementById("topic-input").value.trim();
  const n      = document.getElementById("num-scenes-select").value;
  const status = document.getElementById("gen-status");

  if (!topic) { alert("Please describe your video topic first."); return; }

  const genBtn    = document.getElementById("generate-btn");
  const scriptBtn = document.getElementById("gen-script-btn");

  genBtn.disabled    = true;
  scriptBtn.disabled = true;
  genBtn.textContent = andCreateVideo ? "⏳ Writing script..." : "⏳ Generating...";
  status.textContent = "✍️ AI is writing your script...";
  status.style.color = "var(--muted)";

  try {
    const res  = await fetch("/generate-script", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ topic, channel: selectedChannel, num_scenes: parseInt(n) })
    });
    const data = await res.json();

    if (data.error) {
      status.textContent = "❌ " + data.error;
      status.style.color = "#E07878";
      genBtn.disabled = false; scriptBtn.disabled = false;
      genBtn.textContent = "🎬 Generate Video";
      return;
    }

    const script = data.script;
    const json   = JSON.stringify(script, null, 2);
    document.getElementById("script-input").value = json;
    document.getElementById("script-card").style.display = "block";
    lastVideoTitle = script.title || topic.slice(0, 80);
    document.getElementById("yt-title-input").value = lastVideoTitle.slice(0, 100);
    status.textContent = "✅ Script ready (" + script.scenes.length + " scenes)";
    status.style.color = "var(--wood)";

    if (andCreateVideo) {
      status.textContent = "✅ Script ready — starting video...";
      await startGeneration(script);
    } else {
      genBtn.disabled    = false;
      scriptBtn.disabled = false;
      genBtn.textContent = "🎬 Generate Video";
      // Show script for review
      const toggle = document.getElementById("script-toggle");
      const body   = document.getElementById("script-collapse");
      toggle.classList.add("open");
      body.classList.add("open");
    }
  } catch(e) {
    status.textContent = "❌ " + e;
    status.style.color = "#E07878";
    genBtn.disabled = false; scriptBtn.disabled = false;
    genBtn.textContent = "🎬 Generate Video";
  }
}

// ════════════════════════════════════════════════════════════
// Start video generation (from script object or from textarea)
// ════════════════════════════════════════════════════════════
async function startGeneration(scriptObj) {
  let data = scriptObj;

  // If called directly (Generate Video clicked with existing script)
  if (!data) {
    const raw = document.getElementById("script-input").value.trim();
    if (!raw) {
      // No existing script — generate first then video
      generateScript(true);
      return;
    }
    try { data = JSON.parse(raw); }
    catch(e) { alert("Script JSON is invalid. Try generating it again."); return; }
  }

  const voice   = document.getElementById("voice-select").value;
  const channel = selectedChannel;
  const title   = data.title || "Untitled";
  const scenes  = data.scenes || [];

  if (!scenes.length) { alert("No scenes found."); return; }

  totalScenes = scenes.length; completedScenes = 0;
  lastVideoTitle = title;
  document.getElementById("yt-title-input").value = title.slice(0, 100);

  const genBtn = document.getElementById("generate-btn");
  genBtn.disabled    = true;
  genBtn.textContent = "⏳ Generating...";

  document.getElementById("progress-section").style.display = "block";
  document.getElementById("output-section").style.display   = "none";
  document.getElementById("log-box").innerHTML = "";
  document.getElementById("progress-bar").style.width = "5%";
  document.getElementById("progress-section").scrollIntoView({ behavior:"smooth", block:"start" });

  try {
    const res = await fetch("/generate", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ title, scenes, voice, format:"vertical", channel })
    });
    const result = await res.json();
    if (result.error) { alert(result.error); resetBtn(); return; }
    listenToProgress();
  } catch(e) {
    alert("Failed to start: " + e);
    resetBtn();
  }
}

function listenToProgress() {
  const es  = new EventSource("/stream");
  const log = document.getElementById("log-box");
  const bar = document.getElementById("progress-bar");

  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.ping) return;
    if (data.msg) {
      const line = document.createElement("div");
      const m    = data.msg;
      if      (m.includes("✅") || m.includes("complete")) line.className = "log-done";
      else if (m.includes("⚠️") || m.includes("failed"))   line.className = "log-warn";
      else if (m.includes("error"))                          line.className = "log-err";
      line.textContent = m;
      log.appendChild(line);
      log.scrollTop = log.scrollHeight;
      if (m.includes("Scene") && m.includes("complete")) {
        completedScenes++;
        bar.style.width = (5 + Math.round((completedScenes / totalScenes) * 85)) + "%";
      }
    }
    if (data.done)  { es.close(); bar.style.width = "100%"; showOutput(data.path); resetBtn(); }
    if (data.error) { es.close(); log.innerHTML += '<div class="log-err">❌ ' + data.error + '</div>'; resetBtn(); }
  };
  es.onerror = () => { es.close(); log.innerHTML += '<div class="log-warn">Connection lost.</div>'; resetBtn(); };
}

function showOutput(videoPath) {
  const filename = videoPath.split("/").pop();
  const videoUrl = "/video/" + filename;
  lastVideoFilename = filename;

  document.getElementById("download-link").href     = videoUrl;
  document.getElementById("download-link").download = filename;
  document.getElementById("side-phone-screen").innerHTML = '<video src="' + videoUrl + '" controls playsinline></video>';
  document.getElementById("video-wrap").innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;margin:8px 0;">
      <div class="phone-device" style="max-width:190px;">
        <div class="phone-notch"><div class="phone-speaker"></div><div class="phone-camera"></div></div>
        <div class="phone-screen"><video src="${videoUrl}" controls playsinline></video></div>
        <div class="phone-bar"></div>
      </div>
      <div class="phone-label">📱 Ready for upload</div>
    </div>`;

  document.getElementById("output-section").style.display = "block";
  // Show YouTube post section based on connection status
  checkYouTubeStatus(true);
  document.getElementById("output-section").scrollIntoView({ behavior:"smooth", block:"start" });
  loadHistory();
}

function resetBtn() {
  const btn = document.getElementById("generate-btn");
  btn.disabled    = false;
  btn.textContent = "🎬 Generate Video";
  document.getElementById("gen-script-btn").disabled = false;
}

function makeAnother() {
  document.getElementById("output-section").style.display   = "none";
  document.getElementById("progress-section").style.display = "none";
  document.getElementById("topic-input").value = "";
  document.getElementById("script-card").style.display = "none";
  document.getElementById("gen-status").textContent = "";
  window.scrollTo({ top:0, behavior:"smooth" });
}

// ════════════════════════════════════════════════════════════
// Past videos
// ════════════════════════════════════════════════════════════
async function loadHistory() {
  try {
    const res  = await fetch("/videos");
    const vids = await res.json();
    const list = document.getElementById("history-list");
    if (!vids.length) { list.innerHTML = '<p style="color:var(--muted);font-size:13px;">No videos yet — create your first one!</p>'; return; }
    list.innerHTML = '<div class="video-grid">' +
      vids.slice(0, 24).map(v => {
        const name  = v.name.replace(/\.mp4$/, "").replace(/_/g, " ");
        const ch    = v.channel || "bsg";
        const badge = ch === "tmf" ? '<span class="vid-badge badge-tmf">MIND FILES</span>' : '<span class="vid-badge badge-bsg">BIBLE STORY</span>';
        const url   = "/video/" + v.name;
        return `<div class="vid-card">
          <div class="vid-thumb"><video src="${url}" muted preload="metadata"></video></div>
          <div class="vid-info">${badge}<div class="vid-name">${name}</div>
          <div class="vid-actions">
            <a href="${url}" target="_blank" class="btn btn-ghost" style="flex:1;justify-content:center;font-size:11px;">▶ Play</a>
            <a href="${url}" download="${v.name}" class="btn btn-ghost" style="padding:8px 9px;font-size:11px;">⬇</a>
          </div></div></div>`;
      }).join("") + '</div>';
  } catch(e) { document.getElementById("history-list").innerHTML = '<p style="color:#E07878;font-size:13px;">Error loading videos.</p>'; }
}

// ════════════════════════════════════════════════════════════
// Settings accordion
// ════════════════════════════════════════════════════════════
function toggleAccordion(header) {
  const body = header.nextElementSibling;
  const open = body.classList.contains("open");
  header.classList.toggle("open", !open);
  body.classList.toggle("open", !open);
}

// ════════════════════════════════════════════════════════════
// API key save
// ════════════════════════════════════════════════════════════
async function saveKeys() {
  const fal        = document.getElementById("fal-key-input").value.trim();
  const openai     = document.getElementById("openai-key-input").value.trim();
  const elevenlabs = document.getElementById("elevenlabs-key-input").value.trim();
  const status     = document.getElementById("save-status");
  if (!fal && !openai && !elevenlabs) { status.textContent = "Enter at least one key."; status.style.color="#E07878"; status.style.display="block"; return; }
  try {
    const res  = await fetch("/save-config", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ fal_key:fal, openai_key:openai, elevenlabs_key:elevenlabs }) });
    const data = await res.json();
    if (!data.error) {
      status.textContent = "✅ Saved! Restart the app to apply.";
      status.style.color = "var(--wood)";
      if (fal) { const fs = document.getElementById("fal-key-status"); if(fs){ fs.textContent="✅ fal.ai key saved — Flux Pro is now your image engine"; fs.style.color="var(--wood)"; } }
      checkVoiceStatus();
    } else {
      status.textContent = "❌ " + data.error;
      status.style.color = "#E07878";
    }
    status.style.display = "block";
  } catch(e) { status.textContent = "❌ " + e; status.style.color = "#E07878"; status.style.display="block"; }
}

// ════════════════════════════════════════════════════════════
// YouTube — per-channel connection
// ════════════════════════════════════════════════════════════
let ytStatus = { bsg_connected: false, tmf_connected: false };

async function checkYouTubeStatus(showPostSection) {
  try {
    const res  = await fetch("/youtube-status");
    const data = await res.json();
    ytStatus = data;

    const badge = document.getElementById("yt-header-badge");
    const cs    = document.getElementById("yt-connect-status");

    // Header badge — reflects whichever channels are connected
    if (!data.libs_installed) {
      badge.textContent = "YouTube: install libs";
      badge.classList.remove("connected");
    } else if (!data.secrets_file) {
      badge.textContent = "YouTube: needs setup";
      badge.classList.remove("connected");
    } else if (data.bsg_connected && data.tmf_connected) {
      badge.textContent = "✅ Both channels live";
      badge.classList.add("connected");
    } else if (data.bsg_connected || data.tmf_connected) {
      badge.textContent = "✅ 1 channel connected";
      badge.classList.add("connected");
    } else {
      badge.textContent = "YouTube: not connected";
      badge.classList.remove("connected");
    }

    // Update BSG row in Settings
    const bsgTxt   = document.getElementById("yt-bsg-status-text");
    const bsgCBtn  = document.getElementById("yt-bsg-connect-btn");
    const bsgDBtn  = document.getElementById("yt-bsg-disconnect-btn");
    if (bsgTxt) {
      if (!data.libs_installed) {
        bsgTxt.textContent = "⚠️ Libraries not installed — see setup steps above";
      } else if (!data.secrets_file) {
        bsgTxt.textContent = "⚠️ youtube_client_secrets.json not found";
      } else if (data.bsg_connected) {
        bsgTxt.textContent = "✅ Connected — ready to post";
        bsgTxt.style.color = "#2D6A4F";
        if (bsgCBtn) bsgCBtn.textContent = "Reconnect";
        if (bsgDBtn) bsgDBtn.style.display = "inline-flex";
      } else {
        bsgTxt.textContent = "Not connected — click Connect to sign in";
        bsgTxt.style.color = "var(--muted)";
        if (bsgCBtn) bsgCBtn.textContent = "Connect";
        if (bsgDBtn) bsgDBtn.style.display = "none";
      }
    }

    // Update TMF row in Settings
    const tmfTxt   = document.getElementById("yt-tmf-status-text");
    const tmfCBtn  = document.getElementById("yt-tmf-connect-btn");
    const tmfDBtn  = document.getElementById("yt-tmf-disconnect-btn");
    if (tmfTxt) {
      if (!data.libs_installed) {
        tmfTxt.textContent = "⚠️ Libraries not installed — see setup steps above";
      } else if (!data.secrets_file) {
        tmfTxt.textContent = "⚠️ youtube_client_secrets.json not found";
      } else if (data.tmf_connected) {
        tmfTxt.textContent = "✅ Connected — ready to post";
        tmfTxt.style.color = "#8B6914";
        if (tmfCBtn) tmfCBtn.textContent = "Reconnect";
        if (tmfDBtn) tmfDBtn.style.display = "inline-flex";
      } else {
        tmfTxt.textContent = "Not connected — click Connect to sign in";
        tmfTxt.style.color = "var(--muted)";
        if (tmfCBtn) tmfCBtn.textContent = "Connect";
        if (tmfDBtn) tmfDBtn.style.display = "none";
      }
    }

    // Show/hide post section in output based on current channel
    if (showPostSection) {
      const ch         = selectedChannel;
      const isConn     = ch === "bsg" ? data.bsg_connected : data.tmf_connected;
      const postRow    = document.getElementById("yt-post-row");
      const connectPrm = document.getElementById("yt-connect-prompt");
      if (isConn) {
        postRow.style.display    = "flex";
        connectPrm.style.display = "none";
      } else {
        postRow.style.display    = "none";
        connectPrm.style.display = "block";
      }
    }
  } catch(e) {}
}

async function connectYouTube(channel) {
  const cs   = document.getElementById("yt-connect-status");
  const cBtn = document.getElementById("yt-" + channel + "-connect-btn");
  if (cBtn) { cBtn.disabled = true; cBtn.textContent = "⏳ Opening..."; }
  if (cs)   cs.textContent = "";

  try {
    const res  = await fetch("/youtube-connect?channel=" + channel);
    const data = await res.json();
    if (data.error) {
      if (cs) { cs.textContent = "❌ " + data.error; cs.style.color = "#E07878"; }
      if (cBtn) { cBtn.disabled = false; cBtn.textContent = "Connect"; }
      return;
    }
    if (cs) { cs.textContent = "Google sign-in opened — sign in with the correct account, then return here."; cs.style.color = "var(--muted)"; }
    window.open(data.auth_url, "_blank", "width=600,height=700");
    if (cBtn) cBtn.textContent = "⏳ Waiting for sign-in...";

    // Poll until the token file is saved
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts++;
      const r = await fetch("/youtube-status");
      const d = await r.json();
      const connected = channel === "bsg" ? d.bsg_connected : d.tmf_connected;
      if (connected) {
        clearInterval(poll);
        if (cBtn) cBtn.disabled = false;
        checkYouTubeStatus(false);
        if (cs) { cs.textContent = "✅ Connected!"; cs.style.color = "var(--wood)"; }
      } else if (attempts > 60) {
        clearInterval(poll);
        if (cBtn) { cBtn.disabled = false; cBtn.textContent = "Connect"; }
        if (cs) cs.textContent = "Timed out — try again.";
      }
    }, 3000);
  } catch(e) {
    if (cs) { cs.textContent = "❌ " + e; cs.style.color = "#E07878"; }
    if (cBtn) { cBtn.disabled = false; cBtn.textContent = "Connect"; }
  }
}

async function disconnectYouTube(channel) {
  const label = channel === "bsg" ? "Bible Story Garden" : "The Mind Files";
  if (!confirm("Disconnect " + label + " from YouTube? You'll need to sign in again to post.")) return;
  await fetch("/youtube-disconnect", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({channel}) });
  checkYouTubeStatus(false);
}

// ════════════════════════════════════════════════════════════
// YouTube post
// ════════════════════════════════════════════════════════════
async function postToYouTube() {
  if (!lastVideoFilename) { alert("No video to post."); return; }
  const title   = document.getElementById("yt-title-input").value.trim() || lastVideoTitle;
  const desc    = document.getElementById("yt-desc-input").value.trim();
  const tags    = document.getElementById("yt-tags-input").value.trim();
  const privacy = document.getElementById("yt-privacy").value;
  const status  = document.getElementById("yt-post-status");
  const btn     = document.getElementById("yt-post-btn");

  if (!title) { alert("Add a title for the YouTube video."); return; }

  btn.disabled = true;
  btn.textContent = "⏳ Uploading...";
  status.textContent = "Uploading to YouTube — this may take 1–3 minutes...";
  status.style.color = "var(--muted)";

  try {
    const res  = await fetch("/youtube-upload", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        video_path: lastVideoFilename,
        title, description: desc, tags,
        privacy, channel: selectedChannel
      })
    });
    const data = await res.json();
    if (data.error) {
      status.textContent = "❌ " + data.error;
      status.style.color = "#E07878";
    } else {
      status.innerHTML = '✅ Posted! <a href="' + data.url + '" target="_blank" style="color:var(--amber);font-weight:700;">View on YouTube →</a>';
      status.style.color = "var(--wood)";
    }
  } catch(e) {
    status.textContent = "❌ " + e;
    status.style.color = "#E07878";
  } finally {
    btn.disabled = false; btn.textContent = "🚀 Post Now";
  }
}

// ════════════════════════════════════════════════════════════
// Voice status
// ════════════════════════════════════════════════════════════
async function checkVoiceStatus() {
  try {
    const res  = await fetch("/voice-status");
    const data = await res.json();
    const opt  = document.getElementById("my-voice-option");
    if (data.ready)                              opt.textContent = "🎤 My Voice Clone ✅";
    else if (data.has_voice_file && !data.has_xtts) opt.textContent = "🎤 My Voice Clone (needs pip3 install TTS)";
    else                                          opt.textContent = "🎤 My Voice Clone (needs setup)";
    if (data.has_elevenlabs) document.querySelectorAll("#voice-select optgroup")[0].label = "⭐ ElevenLabs Premium — Active ✅";
    if (data.has_fal)        { const el = document.getElementById("fal-key-input");        if (el && !el.value) { el.placeholder = "••••••••••• (key saved — Flux Pro active ✅)"; } const fs = document.getElementById("fal-key-status"); if(fs){ fs.textContent="✅ Flux Pro active — images cost ~$0.05 each"; fs.style.color="var(--wood)"; } }
    if (data.has_openai)     { const el = document.getElementById("openai-key-input");     if (el && !el.value) el.placeholder = "••••••••••• (key saved)"; }
    if (data.has_elevenlabs) { const el = document.getElementById("elevenlabs-key-input"); if (el && !el.value) el.placeholder = "••••••••••• (key saved)"; }
  } catch(e) {}
}

document.addEventListener("DOMContentLoaded", () => {
  const vs = document.getElementById("voice-select");
  if (vs) vs.addEventListener("change", function() {
    document.getElementById("el-notice").style.display = this.value.startsWith("el_") ? "block" : "none";
  });
});

// ════════════════════════════════════════════════════════════
// Init
// ════════════════════════════════════════════════════════════
checkVoiceStatus();
checkYouTubeStatus(false);
loadHistory();
</script>
</body>
</html>
"""

# ══════════════════════════════════════════════════════════════════════════════
#  STARTUP
# ══════════════════════════════════════════════════════════════════════════════

def check_deps():
    try:
        import edge_tts
    except ImportError:
        print("❌  Missing: edge-tts — run:  pip3 install edge-tts")
        sys.exit(1)
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌  Missing: ffmpeg — run:  brew install ffmpeg")
        sys.exit(1)
    try:
        import openai
    except ImportError:
        print("📦  Installing openai library...")
        subprocess.run([sys.executable, "-m", "pip", "install", "openai"], check=True)
        print("✅  openai installed")

    if get_openai_key():
        print("✅  OpenAI API key loaded — DALL-E 3 image generation active")
    else:
        print("⚠️  No OpenAI key found — using free backup image service")

    if get_elevenlabs_key():
        print("✅  ElevenLabs API key loaded — premium voices active")
    else:
        print("ℹ️  No ElevenLabs key — using free Microsoft voices (add key to unlock premium)")


if __name__ == "__main__":
    check_deps()
    print("\n╔══════════════════════════════════════════╗")
    print("║     MidwestMade4U Video Studio           ║")
    print("╚══════════════════════════════════════════╝")

    # Detect if running in CI (GitHub Actions)
    in_ci = bool(os.getenv("GITHUB_ACTIONS"))

    if in_ci:
        print("\n🤖  Running in CI mode (GitHub Actions)")
        print("   Flask server starting (no browser)\n")
    else:
        print("\n✅  Starting... opening Chrome now.")
        print("   Keep this window open while you work.\n")

        # Prevent Mac from sleeping while the app is running
        try:
            subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
            print("☕  Sleep prevention active (Mac won't sleep while app is running)\n")
        except Exception:
            pass  # Non-Mac system, just skip it

        # Open browser after short delay (not in CI)
        threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5002")).start()

    app.run(host="0.0.0.0", port=5002, debug=False, threaded=True)
