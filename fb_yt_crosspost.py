"""
fb_crosspost.py -- Upload a video natively to a Facebook Page.

Title read from the channel post_log (newest entry) — reliable after YT upload.
Video path from FB_VIDEO_PATH env (set by workflow find step).

Required env vars:
  FB_PAGE_ACCESS_TOKEN  -- Page Access Token (needs pages_manage_posts + pages_manage_video)
  FB_PAGE_ID            -- Facebook Page ID (for logging)
  FB_POST_LOG           -- path to post log e.g. "tmf_post_log.json"

Optional env vars:
  FB_VIDEO_PATH         -- explicit video file path (set by workflow find step)
"""

import glob, json, os, sys, requests

PAGE_TOKEN    = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
PAGE_ID       = os.environ.get("FB_PAGE_ID", "")
POST_LOG      = os.environ.get("FB_POST_LOG", "tmf_post_log.json")
EXPLICIT_PATH = os.environ.get("FB_VIDEO_PATH", "").strip()

if not PAGE_TOKEN:
    print("Missing FB_PAGE_ACCESS_TOKEN")
    sys.exit(1)

# ── Get title from post log (written by auto_post AFTER YT upload) ─────────────
title = "New video"
try:
    data = json.loads(open(POST_LOG).read())
    posts = data if isinstance(data, list) else data.get("posts", [])
    if posts:
        title = posts[-1].get("title", "New video")
        print(f"  Title from post log: {title}")
except Exception as e:
    print(f"  Warning: could not read post log {POST_LOG}: {e}")

# ── Find video file ────────────────────────────────────────────────────────────
video_path = None
if EXPLICIT_PATH and os.path.exists(EXPLICIT_PATH):
    video_path = EXPLICIT_PATH
    print(f"  Using FB_VIDEO_PATH: {video_path}")
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
print(f"Uploading to FB page {PAGE_ID}: {title}")
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
