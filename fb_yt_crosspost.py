"""
fb_crosspost.py -- Upload a video as a native Facebook Reel to a Page.

Finds the rendered video file, then uploads it directly to the FB Reels API.
Works for both TMF (video in working dir as *.mp4) and MZ (path in trigger JSON).

Required env vars:
  FB_PAGE_ACCESS_TOKEN  -- Page Access Token
  FB_PAGE_ID            -- Facebook Page ID
  FB_TRIGGER_GLOB       -- glob pattern e.g. "auto_trigger_mz_*.json"
"""

import glob
import json
import os
import sys
import requests

PAGE_TOKEN   = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
PAGE_ID      = os.environ.get("FB_PAGE_ID", "")
TRIGGER_GLOB = os.environ.get("FB_TRIGGER_GLOB", "auto_trigger_*.json")

if not all([PAGE_TOKEN, PAGE_ID]):
    print("Missing FB_PAGE_ACCESS_TOKEN or FB_PAGE_ID")
    sys.exit(1)

# ── Find most recent trigger file ─────────────────────────────────────────────
trigger_files = sorted(glob.glob(TRIGGER_GLOB))
if not trigger_files:
    print(f"No trigger files found matching '{TRIGGER_GLOB}' — skipping FB Reel")
    sys.exit(0)

trigger = json.loads(open(trigger_files[-1]).read())
title   = trigger.get("title") or (trigger.get("script") or {}).get("title") or "New video"

# ── Find video file ────────────────────────────────────────────────────────────
# Try trigger file paths first (MZ writes these), then fall back to newest .mp4 (TMF)
video_path = (
    trigger.get("tt_path") or
    trigger.get("ig_path") or
    trigger.get("master_path") or
    trigger.get("yt_path")
)

if not video_path or not os.path.exists(str(video_path)):
    # TMF: video is named after the title in the working directory
    mp4_files = sorted(glob.glob("*.mp4"), key=os.path.getmtime, reverse=True)
    if mp4_files:
        video_path = mp4_files[0]
        print(f"  Using newest .mp4 in working dir: {video_path}")
    else:
        print("No .mp4 file found — skipping FB Reel")
        sys.exit(0)

if not os.path.exists(video_path):
    print(f"Video file not found: {video_path} — skipping FB Reel")
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
