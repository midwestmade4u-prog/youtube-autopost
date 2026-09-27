"""
fb_longform_post.py -- Cross-post the newest long-form (landscape, 10-15 min)
video to a Facebook Page as a regular video post.

Why a feed video and not a Reel: Reels cap at 90 s and are 9:16. Long-form is
1920x1080 and 12-15 min, which is what Facebook's in-stream ads run on, so the
plain /me/videos upload is the right surface here.

Sep 27 2026 -- built DORMANT. Long-form on a zero-follower page reaches nobody
and is the format Meta's originality filter is strictest on. Turn it on per
channel once the page passes ~100 followers from Reels:
  GitHub repo -> Settings -> Variables -> FB_LONGFORM_ENABLED = "mz,tmf"

Env vars:
  FB_PAGE_ACCESS_TOKEN, FB_PAGE_ID   page token/id (same secrets as the Shorts step)
  FB_CHANNEL                         mz | tmf   (which entry list to read from auto_post_log.json)
  FB_LONGFORM_ENABLED                comma list of channels that may post; anything else = skip
  FB_VIDEO_PATH                      explicit mp4 (set by the workflow find step)
  FB_LONGFORM_DRY_RUN=1              do everything except upload
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

import requests

GRAPH = "https://graph.facebook.com/v25.0"

PAGE_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
PAGE_ID    = os.environ.get("FB_PAGE_ID", "").strip()
CHANNEL    = os.environ.get("FB_CHANNEL", "mz").strip().lower()
ENABLED    = {c.strip().lower() for c in os.environ.get("FB_LONGFORM_ENABLED", "").split(",") if c.strip()}
EXPLICIT   = os.environ.get("FB_VIDEO_PATH", "").strip()
DRY_RUN    = os.environ.get("FB_LONGFORM_DRY_RUN", "0") == "1"

BRAND = {
    "mz":  {"out": "MZ_Longform_Output",  "log_key": "mz_longform_posts",
            "yt": "https://www.youtube.com/@TheMinuteZero",
            "tagline": "The full story behind the moment it all broke.",
            "tags": "#MinuteZero #businesshistory #documentary"},
    "tmf": {"out": "TMF_Longform_Output", "log_key": "tmf_longform_posts",
            "yt": "https://www.youtube.com/@TheMindFilesYT",
            "tagline": "The full episode on why your mind does what it does.",
            "tags": "#TheMindFiles #psychology #humanbehavior"},
}


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def newest_post(key: str) -> dict:
    try:
        data = json.loads(Path("auto_post_log.json").read_text())
        posts = data.get(key, [])
        return posts[-1] if posts else {}
    except Exception as e:  # noqa: BLE001
        log(f"Warning: could not read auto_post_log.json: {e}")
        return {}


def find_video(out_dir: str) -> Path | None:
    if EXPLICIT and os.path.exists(EXPLICIT):
        return Path(EXPLICIT)
    cands = glob.glob(f"{out_dir}/**/*.mp4", recursive=True)
    return Path(max(cands, key=os.path.getmtime)) if cands else None


def build_caption(title: str, brand: dict) -> str:
    return "\n\n".join([
        title,
        brand["tagline"],
        "Daily 90-second versions in our Reels. Follow for the next one.",
        brand["tags"],
    ])


def main() -> int:
    if CHANNEL not in BRAND:
        print(f"Unknown FB_CHANNEL '{CHANNEL}' -- skipping")
        return 0
    if CHANNEL not in ENABLED:
        print(f"Long-form FB cross-post is OFF for '{CHANNEL}' "
              f"(FB_LONGFORM_ENABLED='{','.join(sorted(ENABLED)) or ''}') -- skipping")
        return 0
    if not PAGE_TOKEN or not PAGE_ID:
        print("Missing FB_PAGE_ACCESS_TOKEN or FB_PAGE_ID -- skipping")
        return 1

    brand = BRAND[CHANNEL]
    video = find_video(brand["out"])
    if not video:
        print("No long-form video found -- skipping")
        return 0

    post    = newest_post(brand["log_key"])
    title   = (post.get("title") or video.stem.replace("_", " ").title()).strip()
    caption = build_caption(title, brand)
    size_mb = video.stat().st_size // 1024 // 1024
    print(f"Facebook long-form video for page {PAGE_ID} ({CHANNEL}): {title}")
    log(f"File: {video} ({size_mb} MB)")
    log("Caption:\n" + "\n".join("    " + l for l in caption.splitlines()))

    if DRY_RUN:
        log("DRY RUN -- not uploading")
        return 0

    with open(video, "rb") as fh:
        r = requests.post(f"{GRAPH}/me/videos",
                          data={"title": title, "description": caption,
                                "published": "true", "access_token": PAGE_TOKEN},
                          files={"source": (video.name, fh, "video/mp4")},
                          timeout=1800)
    body = r.json() if r.ok else {}
    if body.get("id"):
        print(f"FB long-form video published: id={body['id']}")
        return 0
    print(f"FB upload failed: {r.status_code} {r.text[:300]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
