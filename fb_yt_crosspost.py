"""
fb_yt_crosspost.py -- Cross-post a YouTube video to a Facebook Page as a link post.

Required env vars:
  FB_PAGE_ACCESS_TOKEN  -- Page Access Token for the target page
  FB_PAGE_ID            -- Facebook Page ID
  YT_VIDEO_ID           -- YouTube video ID (set by upload step)
  YT_VIDEO_TITLE        -- YouTube video title (set by upload step)
  YT_CHANNEL_HANDLE     -- e.g. @TheMindFilesYT (optional)
"""
import os, sys, requests

PAGE_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
PAGE_ID    = os.environ.get("FB_PAGE_ID", "")
VIDEO_ID   = os.environ.get("YT_VIDEO_ID", "")
TITLE      = os.environ.get("YT_VIDEO_TITLE", "New video")
HANDLE     = os.environ.get("YT_CHANNEL_HANDLE", "")

if not all([PAGE_TOKEN, PAGE_ID, VIDEO_ID]):
    print("Missing env vars: FB_PAGE_ACCESS_TOKEN, FB_PAGE_ID, YT_VIDEO_ID")
    sys.exit(1)

yt_url = f"https://www.youtube.com/watch?v={VIDEO_ID}"
message = f"{TITLE}\n\n{yt_url}"
if HANDLE:
    message += f"\n\nWatch on YouTube: {HANDLE}"

resp = requests.post(
    f"https://graph.facebook.com/v25.0/{PAGE_ID}/feed",
    data={"message": message, "link": yt_url, "access_token": PAGE_TOKEN},
    timeout=30,
)
if resp.ok and resp.json().get("id"):
    print(f"FB post published: {resp.json()['id']}")
else:
    print(f"FB post failed: {resp.status_code} {resp.text}")
    sys.exit(1)
