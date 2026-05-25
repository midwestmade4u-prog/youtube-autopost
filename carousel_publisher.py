"""
Agent 2 — ChannelStack IG Carousel Publisher
Reads carousel_output.json, renders 10 slide images with Pillow,
uploads to imgbb, posts as IG carousel via Meta Graph API,
logs to post_log.json.
"""

import json
import os
import sys
import time
import base64
import random
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime

INPUT_FILE = "carousel_output.json"
POST_LOG = "post_log.json"
BACKGROUNDS_DIR = "backgrounds"

IG_USER_ID = os.environ["IG_USER_ID"]
IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
IMGBB_API_KEY = os.environ["IMGBB_API_KEY"]

SLIDE_W, SLIDE_H = 1080, 1080

# ── Brand colors ─────────────────────────────────────────────────────────────
ACCENT_COLOR = (255, 200, 0)     # yellow accent
TEXT_COLOR = (255, 255, 255)     # white
SUBTEXT_COLOR = (200, 200, 200)  # light gray
BRAND_TAG = "@channelstack"

# ── Load data ────────────────────────────────────────────────────────────────
def load_carousel():
    with open(INPUT_FILE) as f:
        return json.load(f)

def load_post_log():
    if not os.path.exists(POST_LOG):
        return []
    with open(POST_LOG) as f:
        return json.load(f)

def save_post_log(log):
    with open(POST_LOG, "w") as f:
        json.dump(log, f, indent=2)

# ── Background loader ─────────────────────────────────────────────────────────
def get_backgrounds():
    if not os.path.exists(BACKGROUNDS_DIR):
        return []
    files = [f for f in os.listdir(BACKGROUNDS_DIR) if f.endswith(('.jpg', '.png'))]
    return sorted(files)

def load_background(bg_file):
    """Load a background, resize to 1080x1080, darken for text readability."""
    path = os.path.join(BACKGROUNDS_DIR, bg_file)
    img = Image.open(path).convert("RGB")
    img = img.resize((SLIDE_W, SLIDE_H), Image.LANCZOS)
    # Darken background so text pops
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(0.45)
    return img

def make_fallback_background():
    """Plain dark background if no backgrounds folder found."""
    return Image.new("RGB", (SLIDE_W, SLIDE_H), (10, 10, 10))

# ── Font loader ───────────────────────────────────────────────────────────────
def get_font(size, bold=False):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# ── Text wrapping ─────────────────────────────────────────────────────────────
def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

# ── Draw text shadow for readability ─────────────────────────────────────────
def draw_text_with_shadow(draw, x, y, text, font, fill, shadow_color=(0, 0, 0), offset=3):
    draw.text((x + offset, y + offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)

# ── Draw a single slide ───────────────────────────────────────────────────────
def render_slide(slide_num, text, bg_file, total_slides=10):
    # Load background
    if bg_file:
        img = load_background(bg_file)
    else:
        img = make_fallback_background()

    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle([(0, 0), (SLIDE_W, 8)], fill=ACCENT_COLOR)

    # Slide counter (top right)
    counter_font = get_font(28)
    counter_text = f"{slide_num} / {total_slides}"
    draw.text((SLIDE_W - 130, 28), counter_text, font=counter_font, fill=SUBTEXT_COLOR)

    # Brand tag (top left)
    brand_font = get_font(28, bold=True)
    draw.text((40, 28), BRAND_TAG, font=brand_font, fill=ACCENT_COLOR)

    # Main text — centered
    if slide_num == 1:
        main_font = get_font(60, bold=True)
        padding = 80
    elif slide_num == 10:
        main_font = get_font(52, bold=True)
        padding = 80
    else:
        main_font = get_font(50, bold=False)
        padding = 80

    max_text_width = SLIDE_W - (padding * 2)
    lines = wrap_text(draw, text, main_font, max_text_width)

    line_height = main_font.size + 20
    total_text_height = len(lines) * line_height
    y_start = (SLIDE_H - total_text_height) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=main_font)
        line_width = bbox[2] - bbox[0]
        x = (SLIDE_W - line_width) // 2
        y = y_start + i * line_height

        if slide_num == 1 and i == 0:
            draw_text_with_shadow(draw, x, y, line, main_font, ACCENT_COLOR)
        elif slide_num == 10:
            draw_text_with_shadow(draw, x, y, line, main_font, ACCENT_COLOR)
        else:
            draw_text_with_shadow(draw, x, y, line, main_font, TEXT_COLOR)

    # Bottom accent bar
    draw.rectangle([(0, SLIDE_H - 8), (SLIDE_W, SLIDE_H)], fill=ACCENT_COLOR)

    return img

# ── Upload image to imgbb ─────────────────────────────────────────────────────
def upload_to_imgbb(img, slide_num):
    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    image_data = base64.b64encode(buf.read()).decode("utf-8")

    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": IMGBB_API_KEY,
            "image": image_data,
            "name": f"channelstack_slide_{slide_num}_{int(time.time())}",
        }
    )
    result = resp.json()
    if not result.get("success"):
        print(f"imgbb upload failed for slide {slide_num}: {result}")
        sys.exit(1)

    url = result["data"]["url"]
    print(f"  Slide {slide_num} uploaded: {url}")
    return url

# ── Create IG child media container ──────────────────────────────────────────
def create_ig_child(image_url):
    resp = requests.post(
        f"https://graph.instagram.com/v25.0/{IG_USER_ID}/media",
        params={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": IG_ACCESS_TOKEN,
        }
    )
    data = resp.json()
    if "id" not in data:
        print(f"ERROR creating child container: {data}")
        sys.exit(1)
    return data["id"]

# ── Create IG carousel container ─────────────────────────────────────────────
def create_ig_carousel(children_ids, caption):
    resp = requests.post(
        f"https://graph.instagram.com/v25.0/{IG_USER_ID}/media",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
            "access_token": IG_ACCESS_TOKEN,
        }
    )
    data = resp.json()
    if "id" not in data:
        print(f"ERROR creating carousel container: {data}")
        sys.exit(1)
    return data["id"]

# ── Publish IG carousel ───────────────────────────────────────────────────────
def publish_ig_carousel(carousel_id):
    resp = requests.post(
        f"https://graph.instagram.com/v25.0/{IG_USER_ID}/media_publish",
        params={
            "creation_id": carousel_id,
            "access_token": IG_ACCESS_TOKEN,
        }
    )
    data = resp.json()
    if "id" not in data:
        err = data.get("error", {})
        # Meta 24h publish rate limit (code 4 / subcode 2207051)
        # Not a code bug — exits 0 so the workflow stays green and no email fires.
        # The next scheduled run will retry automatically.
        if err.get("code") == 4 and err.get("error_subcode") == 2207051:
            print(f"IG RATE LIMIT (24h block) — will retry on next scheduled run. No action needed.")
            print(f"  Detail: {err.get('error_user_msg', err.get('message', ''))}")
            sys.exit(0)
        print(f"ERROR publishing carousel: {data}")
        sys.exit(1)
    return data["id"]

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=== Agent 2: ChannelStack Carousel Publisher ===\n")

    data = load_carousel()
    carousel = data["carousel"]
    slides = carousel["slides"]
    caption = carousel["caption"]
    topic_id = data["topic_id"]

    print(f"Topic: {data['topic_title']}")
    print(f"Title: {carousel['title']}")
    print(f"Slides: {len(slides)}\n")

    # Pick background — rotate through available backgrounds based on topic_id
    backgrounds = get_backgrounds()
    if backgrounds:
        bg_file = backgrounds[topic_id % len(backgrounds)]
        print(f"Background: {bg_file}")
    else:
        bg_file = None
        print("Background: fallback (no backgrounds folder)")

    # Step 1: Render slides
    print("\nStep 1: Rendering slide images...")
    images = []
    for slide in slides:
        img = render_slide(slide["slide"], slide["text"], bg_file, total_slides=len(slides))
        images.append(img)
        print(f"  Rendered slide {slide['slide']}")

    # Step 2: Upload to imgbb
    print("\nStep 2: Uploading images to imgbb...")
    image_urls = []
    for i, img in enumerate(images):
        url = upload_to_imgbb(img, i + 1)
        image_urls.append(url)
        time.sleep(0.5)

    # Step 3: Create IG child containers
    print("\nStep 3: Creating IG child media containers...")
    children_ids = []
    for i, url in enumerate(image_urls):
        child_id = create_ig_child(url)
        children_ids.append(child_id)
        print(f"  Child {i+1} container ID: {child_id}")
        time.sleep(1)

    # Step 4: Create carousel container
    print("\nStep 4: Creating carousel container...")
    carousel_id = create_ig_carousel(children_ids, caption)
    print(f"  Carousel container ID: {carousel_id}")

    # Step 5: Wait then publish
    print("\nStep 5: Publishing carousel...")
    time.sleep(3)
    post_id = publish_ig_carousel(carousel_id)
    print(f"  ✓ Published! Post ID: {post_id}")

    # Step 6: Log to post_log.json
    log = load_post_log()
    log.append({
        "topic_id": topic_id,
        "topic_title": data["topic_title"],
        "pillar": data["pillar"],
        "post_id": post_id,
        "carousel_id": carousel_id,
        "background": bg_file,
        "published_at": datetime.utcnow().isoformat() + "Z",
        "slide_count": len(slides),
        "image_urls": image_urls,
    })
    save_post_log(log)
    print(f"\n✓ Logged to {POST_LOG}")
    print(f"\n🎉 Carousel live on @channelstack!")
    print(f"Title: {carousel['title']}")
    print("\nAgent 2 complete.")

if __name__ == "__main__":
    main()
