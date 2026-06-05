"""
fb_crosspost.py -- Upload a video as a native Facebook Reel to a Page.

Reads the most recent auto_trigger_*.json to find the rendered video file,
then uploads it directly to the FB Reels API (no YouTube link, no redirect).

Required env vars:
  FB_PAGE_ACCESS_TOKEN  -- Page Access Token
  FB_PAGE_ID            -- Facebook Page ID
  FB_TRIGGER_GLOB       -- glob pattern to find trigger file, e.g. "auto_trigger_mz_*.json"
"""

import glob
import json
import os
import sys
import time
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
title   = trigger.get("title", "")
# Prefer TikTok (vertical 9:16) variant for Reels; fall back to master
video_path = trigger.get("tt_path") or trigger.get("ig_path") or trigger.get("master_path") or trigger.get("yt_path")

if not video_path or not os.path.exists(video_path):
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
video_id  = d1.get("video_id")
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
else:
    # FB sometimes returns success=false initially but still publishes (async processing)
    print(f"Publish response: {r3.status_code} {r3.text}")
    if r3.status_code in (200, 201):
        print("  (May still be processing — check page in a few minutes)")
    else:
        sys.exit(1)
