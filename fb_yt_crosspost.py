"""
fb_crosspost.py -- Upload a video natively to a Facebook Page.

Uses /me/videos (with Page Access Token, me = the page).
Works with pages_manage_posts + pages_read_engagement.

Required env vars:
  FB_PAGE_ACCESS_TOKEN  -- Page Access Token
  FB_PAGE_ID            -- Facebook Page ID (used for logging only)
  FB_TRIGGER_GLOB       -- glob pattern e.g. "auto_trigger_tmf_*.json"

Optional env vars:
  FB_VIDEO_PATH         -- explicit video file path (set by workflow find step)
"""

import glob
import json
import os
import sys
import requests

PAGE_TOKEN    = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
PAGE_ID       = os.environ.get("FB_PAGE_ID", "")   # for logging
TRIGGER_GLOB  = os.environ.get("FB_TRIGGER_GLOB", "auto_trigger_*.json")
EXPLICIT_PATH = os.environ.get("FB_VIDEO_PATH", "").strip()

if not PAGE_TOKEN:
    print("Missing FB_PAGE_ACCESS_TOKEN")
    sys.exit(1)

# ── Get title from NEWEST trigger file (sort by mtime, not name) ───────────────
title = "New video"
trigger_video = None
trigger_files = sorted(glob.glob(TRIGGER_GLOB), key=os.path.getmtime, reverse=True)
if trigger_files:
    try:
        trigger = json.loads(open(trigger_files[0]).read())
        title = (
            trigger.get("title") or
            (trigger.get("script") or {}).get("title") or
            "New video"
        )
        trigger_video = (
            trigger.get("tt_path") or
            trigger.get("ig_path") or
            trigger.get("master_path") or
            trigger.get("yt_path")
        )
        print(f"  Trigger: {trigger_files[0]}, title: {title}")
    except Exception as e:
        print(f"  Warning: could not read trigger file: {e}")

# ── Find video file ────────────────────────────────────────────────────────────
video_path = None
if EXPLICIT_PATH and os.path.exists(EXPLICIT_PATH):
    video_path = EXPLICIT_PATH
    print(f"  Using FB_VIDEO_PATH: {video_path}")
elif trigger_video and os.path.exists(str(trigger_video)):
    video_path = trigger_video
    print(f"  Using trigger path: {video_path}")
else:
    candidates = (
        glob.glob("TMF_Output/*.mp4") +
        glob.glob("MZ_Output/**/*.mp4", recursive=True) +
        glob.glob("*.mp4")
    )
    if candidates:
        video_path = max(candidates, key=os.path.getmtime)
        print(f"  Found via glob: {video_path}")

if not video_path or not os.path.exists(str(video_path)):
    print("No video file found — skipping FB post")
    sys.exit(0)

file_size = os.path.getsize(video_path)
print(f"Uploading to Facebook page {PAGE_ID}: {title}")
print(f"  File: {video_path} ({file_size // 1024 // 1024} MB)")

# ── Upload via /me/videos (Page Access Token → me = the page) ─────────────────
with open(video_path, "rb") as f:
    resp = requests.post(
        "https://graph.facebook.com/v25.0/me/videos",
        data={
            "title":        title,
            "description":  title,
            "published":    "true",
            "access_token": PAGE_TOKEN,
        },
        files={"source": (os.path.basename(video_path), f, "video/mp4")},
        timeout=300,
    )

if resp.ok and resp.json().get("id"):
    print(f"FB video published: id={resp.json()['id']}")
else:
    print(f"FB upload failed: {resp.status_code} {resp.text}")
    sys.exit(1)
