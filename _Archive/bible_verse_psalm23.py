#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║         Bible Story Garden — Video Maker v1.0           ║
║         Psalm 23: The Lord Is My Shepherd               ║
╚══════════════════════════════════════════════════════════╝

Requirements (run once to install):
    pip install edge-tts requests Pillow

Also requires FFmpeg:
    Mac:     brew install ffmpeg
    Windows: https://ffmpeg.org/download.html

Usage:
    python3 bible_verse_psalm23.py
"""

import asyncio
import os
import sys
import time
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── Brand Colors ─────────────────────────────────────────────────────────────
GREEN  = (29,  158, 117)
GOLD   = (239, 159,  39)
CREAM  = (250, 238, 218)
DARK   = (20,   60,  40)

# ── Video Settings ────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1280, 720
FPS = 24
VOICE = "en-US-JennyNeural"   # Warm, trustworthy Microsoft neural voice

# ── Folders ───────────────────────────────────────────────────────────────────
TEMP_DIR   = Path("bsg_temp_psalm23")
OUTPUT_DIR = Path("bsg_output")


# ══════════════════════════════════════════════════════════════════════════════
#  PSALM 23 — THE LORD IS MY SHEPHERD
# ══════════════════════════════════════════════════════════════════════════════

VIDEO_TITLE = "Psalm 23 - The Lord Is My Shepherd"

SCENES = [
    {
        "narration": "The Lord is my shepherd. That means you are never lost. Never forgotten. Never alone.",
        "image_prompt": "Kind gentle shepherd in white robes standing on a sunny golden hillside, fluffy white sheep gathered around him, rays of warm sunlight, children's bible storybook illustration, bright cheerful colors, hopeful peaceful mood"
    },
    {
        "narration": "He gives you rest in green meadows. Peace beside quiet, sparkling streams.",
        "image_prompt": "Beautiful bright green meadow with a sparkling blue stream, fluffy white sheep resting peacefully in soft grass, colorful wildflowers, puffy white clouds, bright cheerful bible storybook illustration, warm golden light"
    },
    {
        "narration": "When your soul is tired... He finds you. He restores you. He brings you back.",
        "image_prompt": "Kind shepherd gently lifting a small lost lamb, warm golden light surrounding them, soft green hills in background, tender and loving moment, bright colorful children's bible illustration, warm cheerful art style"
    },
    {
        "narration": "Even in your darkest moments — when fear feels bigger than faith — He walks right beside you.",
        "image_prompt": "A small child walking through a shadowy valley, a glowing gentle shepherd figure right beside them with a warm comforting light, darkness turning to soft gold where the shepherd walks, bright hopeful bible storybook illustration"
    },
    {
        "narration": "His love is your shield. His presence is your comfort. You don't have to be afraid.",
        "image_prompt": "Shepherd's large warm gentle hand holding a small child's hand, soft golden glow, bright colorful cheerful bible storybook illustration, love and protection, warm family-friendly art"
    },
    {
        "narration": "He prepares good things for you — even when life feels hard. Your cup is overflowing.",
        "image_prompt": "Beautiful golden table set in a sunny garden full of fruits, flowers, and food, bright cheerful colors, warm sunlight streaming through trees, joyful abundant feast, colorful bible storybook illustration"
    },
    {
        "narration": "Goodness. Love. Following you every single day of your life. And you will live in the house of the Lord... forever.",
        "image_prompt": "Happy family together in a beautiful sunlit meadow, shepherd watching over them with outstretched arms, magnificent rainbow arching overhead, God's golden light shining down, bright colorful joyful bible storybook illustration, peaceful and hopeful"
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE GENERATION  (Pollinations.ai — free, no API key needed)
# ══════════════════════════════════════════════════════════════════════════════

def generate_image(prompt: str, output_path: Path, scene_num: int) -> bool:
    """Download an AI-generated image from Pollinations.ai."""

    styled = (
        f"bright colorful animated children's bible storybook illustration, "
        f"warm family friendly art, vibrant cheerful colors, "
        f"{prompt}, "
        f"no text, no words, clean illustration"
    )

    encoded = urllib.parse.quote(styled)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={WIDTH}&height={HEIGHT}&seed={scene_num * 42}&nologo=true"

    print(f"  🎨 Generating image {scene_num + 1}...")

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BibleStoryGarden/1.0"})
            with urllib.request.urlopen(req, timeout=60) as response:
                data = response.read()
            with open(output_path, "wb") as f:
                f.write(data)
            print(f"  ✅ Image {scene_num + 1} saved.")
            return True
        except Exception as e:
            print(f"  ⚠️  Attempt {attempt + 1} failed: {e}")
            time.sleep(3)

    print(f"  📋 Using placeholder image for scene {scene_num + 1}")
    _make_placeholder(output_path, scene_num)
    return False


def _make_placeholder(path: Path, scene_num: int):
    """Create a simple branded placeholder if image generation fails."""
    img = Image.new("RGB", (WIDTH, HEIGHT), GREEN)
    draw = ImageDraw.Draw(img)

    for i in range(HEIGHT):
        ratio = i / HEIGHT
        r = int(GREEN[0] * (1 - ratio * 0.3))
        g = int(GREEN[1] * (1 - ratio * 0.2))
        b = int(GREEN[2] * (1 - ratio * 0.1))
        draw.line([(0, i), (WIDTH, i)], fill=(max(0, r), max(0, g), max(0, b)))

    cx, cy = WIDTH // 2, HEIGHT // 2 - 40
    draw.rectangle([cx - 15, cy - 80, cx + 15, cy + 80], fill=CREAM)
    draw.rectangle([cx - 60, cy - 15, cx + 60, cy + 15], fill=CREAM)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except:
        font = ImageFont.load_default()
    draw.text((cx, cy + 120), f"Scene {scene_num + 1}", fill=GOLD, font=font, anchor="mm")

    img.save(path)


# ══════════════════════════════════════════════════════════════════════════════
#  TEXT OVERLAY
# ══════════════════════════════════════════════════════════════════════════════

def add_text_overlay(image_path: Path, text: str, output_path: Path):
    """Add a semi-transparent narration bar at the bottom of the image."""
    img = Image.open(image_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    bar_height = 180
    bar_y = HEIGHT - bar_height
    for i in range(bar_height):
        alpha = int(200 * (i / bar_height))
        draw.line([(0, bar_y + i), (WIDTH, bar_y + i)], fill=(0, 30, 15, alpha))

    draw.rectangle([0, bar_y, WIDTH, bar_y + 4], fill=(*GOLD, 200))

    try:
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_text  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      34)
    except:
        font_brand = ImageFont.load_default()
        font_text  = font_brand

    draw.text((WIDTH - 20, 20), "Bible Story Garden", fill=(*CREAM, 180), font=font_brand, anchor="rt")

    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font_text)
        if bbox[2] - bbox[0] > WIDTH - 80:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    line_height = 44
    total_h = len(lines) * line_height
    start_y = bar_y + (bar_height - total_h) // 2

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        draw.text((WIDTH // 2 + 2, y + 2), line, fill=(0, 0, 0, 180), font=font_text, anchor="mt")
        draw.text((WIDTH // 2, y), line, fill=(*CREAM, 255), font=font_text, anchor="mt")

    result = Image.alpha_composite(img, overlay).convert("RGB")
    result.save(output_path)


# ══════════════════════════════════════════════════════════════════════════════
#  VOICEOVER GENERATION
# ══════════════════════════════════════════════════════════════════════════════

async def generate_audio_async(text: str, output_path: Path):
    """Generate narration audio using Edge TTS."""
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(output_path))


def generate_audio(text: str, output_path: Path):
    asyncio.run(generate_audio_async(text, output_path))


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except:
        return 5.0


# ══════════════════════════════════════════════════════════════════════════════
#  VIDEO ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════

def create_scene_clip(image_path: Path, audio_path: Path, output_path: Path):
    """Combine one image + one audio file into a video clip."""
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-vf", f"scale={WIDTH}:{HEIGHT}",
        str(output_path)
    ], capture_output=True)


def concatenate_clips(clip_paths: list, output_path: Path):
    """Join all scene clips into the final video."""
    list_file = TEMP_DIR / "clips.txt"
    with open(list_file, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{clip.resolve()}'\n")

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(output_path)
    ], capture_output=True)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║     Bible Story Garden — Video Maker     ║")
    print("╚══════════════════════════════════════════╝\n")
    print(f"📖 Building: {VIDEO_TITLE}")
    print(f"🎬 Scenes: {len(SCENES)}\n")

    TEMP_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    clip_paths = []

    for i, scene in enumerate(SCENES):
        print(f"── Scene {i + 1} of {len(SCENES)} ─────────────────────────")

        raw_img   = TEMP_DIR / f"scene_{i:02d}_raw.jpg"
        final_img = TEMP_DIR / f"scene_{i:02d}_final.jpg"
        audio     = TEMP_DIR / f"scene_{i:02d}_audio.mp3"
        clip      = TEMP_DIR / f"scene_{i:02d}_clip.mp4"

        generate_image(scene["image_prompt"], raw_img, i)

        print(f"  📝 Adding text overlay...")
        add_text_overlay(raw_img, scene["narration"], final_img)

        print(f"  🎙️  Generating narration...")
        generate_audio(scene["narration"], audio)

        print(f"  🎬 Assembling clip...")
        create_scene_clip(final_img, audio, clip)
        clip_paths.append(clip)

        print(f"  ✅ Scene {i + 1} complete!\n")

    safe_title = VIDEO_TITLE.replace(" ", "_").replace("'", "").replace(":", "")
    output_file = OUTPUT_DIR / f"{safe_title}.mp4"

    print("── Assembling final video ──────────────────")
    concatenate_clips(clip_paths, output_file)

    print(f"\n✅ Done! Your video is ready:")
    print(f"   📁 {output_file.resolve()}\n")
    print("Next: Upload to YouTube Studio and schedule for 7:00 PM CST!\n")


if __name__ == "__main__":
    try:
        import edge_tts
    except ImportError:
        print("❌ Missing: edge-tts")
        print("   Run: pip install edge-tts\n")
        sys.exit(1)

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Missing: FFmpeg")
        print("   Mac: brew install ffmpeg")
        print("   Windows: https://ffmpeg.org/download.html\n")
        sys.exit(1)

    main()
