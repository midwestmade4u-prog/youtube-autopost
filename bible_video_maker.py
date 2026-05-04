#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║         Bible Story Garden — Video Maker v1.0           ║
║  Generates animated Bible story videos using free tools  ║
╚══════════════════════════════════════════════════════════╝

Requirements (run once to install):
    pip install edge-tts requests Pillow

Also requires FFmpeg:
    Mac:     brew install ffmpeg
    Windows: https://ffmpeg.org/download.html

Usage:
    python3 bible_video_maker.py
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
TEMP_DIR   = Path("bsg_temp")
OUTPUT_DIR = Path("bsg_output")


# ══════════════════════════════════════════════════════════════════════════════
#  DEFINE YOUR VIDEO HERE
#  Each scene = one image + one piece of narration spoken aloud
# ══════════════════════════════════════════════════════════════════════════════

VIDEO_TITLE = "Noahs Ark"

SCENES = [
    {
        "narration": "God looked at the world... and His heart broke. People had forgotten how to love each other. But there was one man who still listened.",
        "image_prompt": "Noah standing on a hillside at golden sunset, wise kind old man with white beard, bright colorful bible storybook illustration, warm lighting, children's book art style"
    },
    {
        "narration": "His name was Noah. And God trusted him with an impossible task — build a giant boat. Not near the ocean. In the middle of dry land.",
        "image_prompt": "Noah beginning to build a massive wooden ark on dry land, cheerful sunny day, bright colorful animated bible illustration, animals watching curiously in the background"
    },
    {
        "narration": "People laughed at Noah. They thought he was foolish. But Noah kept building, day after day, trusting what he could not yet see.",
        "image_prompt": "Noah hammering the ark with a big smile while townspeople point and laugh, bright colorful storybook illustration, Noah looking calm and determined, warm cheerful colors"
    },
    {
        "narration": "Then came the animals — two by two — lions and lambs, elephants and doves, giraffes and butterflies — walking right to Noah's door.",
        "image_prompt": "Pairs of colorful animals marching happily toward Noah's ark, bright rainbow colors, cheerful children's storybook illustration, elephants giraffes lions doves butterflies, joyful sunny scene"
    },
    {
        "narration": "The rain began. For forty days the water rose. But inside the ark, every creature was warm, safe, and cared for.",
        "image_prompt": "Noah's ark floating peacefully on calm blue water during gentle rain, warm golden light glowing from windows, animals visible inside looking cozy, colorful bible storybook art, hopeful mood"
    },
    {
        "narration": "When the waters finally fell, a dove returned carrying a green leaf. Land was near. Hope had arrived.",
        "image_prompt": "White dove flying gracefully with a green olive branch toward Noah's ark, soft sunrise colors beginning to appear, bright colorful bible illustration, peaceful and hopeful atmosphere"
    },
    {
        "narration": "God painted the sky with a rainbow — His promise to never forget His people. And He never has. Not then. Not now. Not ever.",
        "image_prompt": "Noah and his family standing joyfully on the ark deck looking at a magnificent rainbow over calm water, animals gathered around them, bright colorful storybook illustration, warm golden light, beautiful and peaceful"
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE GENERATION  (Pollinations.ai — free, no API key needed)
# ══════════════════════════════════════════════════════════════════════════════

def generate_image(prompt: str, output_path: Path, scene_num: int) -> bool:
    """Download an AI-generated image from Pollinations.ai."""

    # Add style prefix for consistent Bible Story Garden look
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

    # Fallback: create a simple colored placeholder
    print(f"  📋 Using placeholder image for scene {scene_num + 1}")
    _make_placeholder(output_path, scene_num)
    return False


def _make_placeholder(path: Path, scene_num: int):
    """Create a simple branded placeholder if image generation fails."""
    img = Image.new("RGB", (WIDTH, HEIGHT), GREEN)
    draw = ImageDraw.Draw(img)

    # Gradient effect
    for i in range(HEIGHT):
        ratio = i / HEIGHT
        r = int(GREEN[0] * (1 - ratio * 0.3))
        g = int(GREEN[1] * (1 - ratio * 0.2))
        b = int(GREEN[2] * (1 - ratio * 0.1))
        draw.line([(0, i), (WIDTH, i)], fill=(max(0, r), max(0, g), max(0, b)))

    # Cross symbol
    cx, cy = WIDTH // 2, HEIGHT // 2 - 40
    draw.rectangle([cx - 15, cy - 80, cx + 15, cy + 80], fill=CREAM)
    draw.rectangle([cx - 60, cy - 15, cx + 60, cy + 15], fill=CREAM)

    # Scene number
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except:
        font = ImageFont.load_default()
    draw.text((cx, cy + 120), f"Scene {scene_num + 1}", fill=GOLD, font=font, anchor="mm")

    img.save(path)


# ══════════════════════════════════════════════════════════════════════════════
#  TEXT OVERLAY  (adds narration text bar at bottom of each image)
# ══════════════════════════════════════════════════════════════════════════════

def add_text_overlay(image_path: Path, text: str, output_path: Path):
    """Add a semi-transparent narration bar at the bottom of the image."""
    img = Image.open(image_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Dark gradient bar at bottom
    bar_height = 180
    bar_y = HEIGHT - bar_height
    for i in range(bar_height):
        alpha = int(200 * (i / bar_height))
        draw.line([(0, bar_y + i), (WIDTH, bar_y + i)], fill=(0, 30, 15, alpha))

    # Gold top border on bar
    draw.rectangle([0, bar_y, WIDTH, bar_y + 4], fill=(*GOLD, 200))

    # Bible Story Garden watermark top-right
    try:
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_text  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      34)
    except:
        font_brand = ImageFont.load_default()
        font_text  = font_brand

    draw.text((WIDTH - 20, 20), "Bible Story Garden", fill=(*CREAM, 180), font=font_brand, anchor="rt")

    # Narration text — word wrap
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

    # Draw text lines centered
    line_height = 44
    total_h = len(lines) * line_height
    start_y = bar_y + (bar_height - total_h) // 2

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        # Shadow
        draw.text((WIDTH // 2 + 2, y + 2), line, fill=(0, 0, 0, 180), font=font_text, anchor="mt")
        # Text
        draw.text((WIDTH // 2, y), line, fill=(*CREAM, 255), font=font_text, anchor="mt")

    # Composite and save
    result = Image.alpha_composite(img, overlay).convert("RGB")
    result.save(output_path)


# ══════════════════════════════════════════════════════════════════════════════
#  VOICEOVER GENERATION  (Edge TTS — Microsoft neural voices, free)
# ══════════════════════════════════════════════════════════════════════════════

async def generate_audio_async(text: str, output_path: Path):
    """Generate narration audio using Edge TTS."""
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(output_path))


def generate_audio(text: str, output_path: Path):
    asyncio.run(generate_audio_async(text, output_path))


def get_audio_duration(audio_path: Path) -> float:
    """Get duration of an audio file using FFprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except:
        return 5.0  # fallback


# ══════════════════════════════════════════════════════════════════════════════
#  VIDEO ASSEMBLY  (FFmpeg)
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

    # Create folders
    TEMP_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    clip_paths = []

    for i, scene in enumerate(SCENES):
        print(f"── Scene {i + 1} of {len(SCENES)} ─────────────────────────")

        raw_img   = TEMP_DIR / f"scene_{i:02d}_raw.jpg"
        final_img = TEMP_DIR / f"scene_{i:02d}_final.jpg"
        audio     = TEMP_DIR / f"scene_{i:02d}_audio.mp3"
        clip      = TEMP_DIR / f"scene_{i:02d}_clip.mp4"

        # 1. Generate image
        generate_image(scene["image_prompt"], raw_img, i)

        # 2. Add text overlay
        print(f"  📝 Adding text overlay...")
        add_text_overlay(raw_img, scene["narration"], final_img)

        # 3. Generate audio
        print(f"  🎙️  Generating narration...")
        generate_audio(scene["narration"], audio)

        # 4. Combine into clip
        print(f"  🎬 Assembling clip...")
        create_scene_clip(final_img, audio, clip)
        clip_paths.append(clip)

        print(f"  ✅ Scene {i + 1} complete!\n")

    # 5. Concatenate all clips
    safe_title = VIDEO_TITLE.replace(" ", "_").replace("'", "")
    output_file = OUTPUT_DIR / f"{safe_title}.mp4"

    print("── Assembling final video ──────────────────")
    concatenate_clips(clip_paths, output_file)

    print(f"\n✅ Done! Your video is ready:")
    print(f"   📁 {output_file.resolve()}\n")
    print("Next: Upload to YouTube Studio and schedule for 7:00 PM CST!\n")


if __name__ == "__main__":
    # Check dependencies
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
