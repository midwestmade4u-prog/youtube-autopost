"""
fb_crosspost.py -- Upload a video as a native Facebook Reel to a Page.

Works for TMF (uses FB_VIDEO_PATH env var set by workflow find step) and
MZ (path in trigger JSON tt_path field).

Required env vars:
  FB_PAGE_ACCESS_TOKEN  -- Page Access Token
  FB_PAGE_ID            -- Facebook Page ID
  FB_TRIGGER_GLOB       -- glob pattern e.g. "auto_trigger_mz_*.json"

Optional env vars:
  FB_VIDEO_PATH         -- explicit video file path (set by workflow find step)
"""

import glob
import json
import os
import sys
import requests

PAGE_TOKEN    = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
PAGE_ID       = os.environ.get("FB_PAGE_ID", "")
TRIGGER_GLOB  = os.environ.get("FB_TRIGGER_GLOB", "auto_trigger_*.json")
EXPLICIT_PATH = os.environ.get("FB_VIDEO_PATH", "").strip()

if not all([PAGE_TOKEN, PAGE_ID]):
    print("Missing FB_PAGE_ACCESS_TOKEN or FB_PAGE_ID")
    sys.exit(1)

# ── Get title from trigger file ────────────────────────────────────────────────
title = "New video"
trigger_files = sorted(glob.glob(TRIGGER_GLOB))
if trigger_files:
    try:
        trigger = json.loads(open(trigger_files[-1]).read())
        title = (
            trigger.get("title") or
            (trigger.get("script") or {}).get("title") or
            "New video"
        )
        # Also try trigger paths (MZ writes these)
        trigger_video = (
            trigger.get("tt_path") or
            trigger.get("ig_path") or
            trigger.get("master_path") or
            trigger.get("yt_path")
        )
    except Exception:
        trigger_video = None
else:
    trigger_video = None

# ── Find video file ────────────────────────────────────────────────────────────
# Priority: explicit path from workflow → trigger file path → newest mp4 anywhere
video_path = None

if EXPLICIT_PATH and os.path.exists(EXPLICIT_PATH):
    video_path = EXPLICIT_PATH
    print(f"  Using FB_VIDEO_PATH: {video_path}")
elif trigger_video and os.path.exists(str(trigger_video)):
    video_path = trigger_video
    print(f"  Using trigger file path: {video_path}")
else:
    # Search common locations
    search_patterns = [
        "*.mp4",
        "TMF_Output/**/*.mp4",
        "MZ_Output/**/*.mp4",
        "/tmp/*.mp4",
    ]
    candidates = []
    for pat in search_patterns:
        candidates += glob.glob(pat, recursive=True)
    if candidates:
        video_path = max(candidates, key=os.path.getmtime)
        print(f"  Found via glob: {video_path}")

if not video_path or not os.path.exists(str(video_path)):
    print(f"No video file found (FB_VIDEO_PATH={EXPLICIT_PATH!r}) — skipping FB Reel")
    sys.exit(0)

file_size = os.path.getsize(video_path)
print(f"Uploading Reel: {title}")
print(f"  File : {video_path} ({file_size // 1024 // 1024} MB)")

BASE = "https://graph.facebook.com/v25.0"

# ── Step 1: Initialize upload session ─────────────────────────────────────────
r1 = requests.post(
    f"{BASE}/{PAGE_ID}/video_reels",
    data={"upload_phase": "start", "access_token": PAGE_TOKEN},
    timeout=30,
)
if not r1.ok:
    print(f"Start failed: {r1.status_code} {r1.text}")
    sys.exit(1)

d1 = r1.json()
video_id   = d1.get("video_id")
upload_url = d1.get("upload_url")
print(f"  Session video_id: {video_id}")

# ── Step 2: Upload video binary ────────────────────────────────────────────────
with open(video_path, "rb") as f:
    video_bytes = f.read()

r2 = requests.post(
    upload_url,
    headers={
        "Authorization": f"OAuth {PAGE_TOKEN}",
        "offset":        "0",
        "file_size":     str(file_size),
    },
    data=video_bytes,
    timeout=300,
)
if not r2.ok:
    print(f"Upload failed: {r2.status_code} {r2.text}")
    sys.exit(1)
print(f"  Binary uploaded OK")

# ── Step 3: Publish as Reel ────────────────────────────────────────────────────
r3 = requests.post(
    f"{BASE}/{PAGE_ID}/video_reels",
    data={
        "upload_phase": "finish",
        "video_id":     video_id,
        "title":        title,
        "description":  title,
        "published":    "true",
        "access_token": PAGE_TOKEN,
    },
    timeout=60,
)
if r3.ok and r3.json().get("success"):
    print(f"FB Reel published: video_id={video_id}")
elif r3.status_code in (200, 201):
    print(f"Publish response: {r3.text}")
    print("  (May still be processing — check page in a few minutes)")
else:
    print(f"Publish failed: {r3.status_code} {r3.text}")
    sys.exit(1)
