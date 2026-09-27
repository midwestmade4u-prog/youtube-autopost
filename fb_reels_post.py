"""
fb_reels_post.py -- Publish the newest MZ video to a Facebook Page as a REEL.

Why this exists (Sep 26 2026): fb_yt_crosspost.py uploads through /me/videos,
which creates an ordinary Page video post. Vertical videos posted that way sit
in the Page feed and are shown mostly to existing followers. Reels go through
/{page-id}/video_reels and are the surface Facebook's recommendation engine
pushes to non-followers -- the only FB surface where a new page can get reach,
and the format the Content Monetization program pays on.

Flow (Meta Reels Publishing API):
  1. POST /{page}/video_reels  upload_phase=start           -> video_id, upload_url
  2. POST https://rupload.facebook.com/video-upload/v25.0/{video_id}
         headers: Authorization: OAuth <token>, offset: 0, file_size: <bytes>
         body: raw mp4 bytes
  3. POST /{page}/video_reels  upload_phase=finish video_state=PUBLISHED
         description=<caption>

Constraints enforced here:
  * Reels must be 3-90 s. MZ narration runs 68-94 s plus a ~5 s spoken CTA, so a
    minority of videos overshoot. Those are time-compressed (video + audio) by
    the minimal factor that fits under REEL_MAX_SEC; anything needing more than
    MAX_SPEEDUP is skipped as a Reel and falls back to a feed video.
  * The YouTube variant (no end card) is used, never the TT/IG variants whose
    end cards point at YouTube -- Meta reduces distribution for content that
    looks lifted from another platform.
  * Caption: one hook sentence + <=5 hashtags. Meta flags >5 hashtags and
    ALL-CAPS/keyword-stuffed captions as spam signals.

Env vars:
  FB_PAGE_ACCESS_TOKEN  Page token with pages_manage_posts, pages_read_engagement, pages_show_list
  FB_PAGE_ID            numeric Page id (required for video_reels; /me is not accepted)
  FB_POST_LOG           e.g. mz_post_log.json (title/description/hashtags of newest post)
  FB_VIDEO_PATH         explicit mp4 path (set by the workflow's find step)
  FB_REELS_DRY_RUN=1    do everything except call Facebook
  FB_FALLBACK_FEED=1    on Reel failure, fall back to the legacy /me/videos post (default 1)

Exit codes: 0 on success or graceful skip; 1 on hard failure (so the workflow's
continue-on-error still shows red in the step log).
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

GRAPH        = "https://graph.facebook.com/v25.0"
RUPLOAD      = "https://rupload.facebook.com/video-upload/v25.0"
REEL_MAX_SEC = 89.0      # hard API limit is 90; leave headroom for container rounding
MAX_SPEEDUP  = 1.12      # >12% faster starts to sound wrong for a documentary voice
MAX_HASHTAGS = 5
PUBLISH_POLL_SEC   = 8
PUBLISH_POLL_TRIES = 15  # ~2 minutes for processing

PAGE_TOKEN   = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
PAGE_ID      = os.environ.get("FB_PAGE_ID", "").strip()
POST_LOG     = os.environ.get("FB_POST_LOG", "mz_post_log.json")
EXPLICIT     = os.environ.get("FB_VIDEO_PATH", "").strip()
DRY_RUN      = os.environ.get("FB_REELS_DRY_RUN", "0") == "1"
FALLBACK     = os.environ.get("FB_FALLBACK_FEED", "1") == "1"


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


# ── Inputs ────────────────────────────────────────────────────────────────────

def newest_post() -> dict:
    try:
        data = json.loads(Path(POST_LOG).read_text())
        posts = data if isinstance(data, list) else data.get("posts", [])
        return posts[-1] if posts else {}
    except Exception as e:  # noqa: BLE001
        log(f"Warning: could not read {POST_LOG}: {e}")
        return {}


def find_video() -> Path | None:
    if EXPLICIT and os.path.exists(EXPLICIT):
        return Path(EXPLICIT)
    cands = glob.glob("*_Output/**/*.mp4", recursive=True)
    return Path(max(cands, key=os.path.getmtime)) if cands else None


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def fit_to_reel_length(src: Path, work: Path) -> Path | None:
    """Return a path <= REEL_MAX_SEC, time-compressing if needed. None if it can't fit."""
    dur = ffprobe_duration(src)
    log(f"Duration: {dur:.1f}s (Reel max {REEL_MAX_SEC:.0f}s)")
    if dur <= REEL_MAX_SEC:
        return src
    factor = dur / REEL_MAX_SEC
    if factor > MAX_SPEEDUP:
        log(f"Needs {factor:.2f}x speed-up (> {MAX_SPEEDUP}x cap) -- not eligible as a Reel")
        return None
    out = work / (src.stem + "_reel.mp4")
    log(f"Compressing {factor:.3f}x to fit Reel limit")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-filter_complex", f"[0:v]setpts=PTS/{factor:.5f}[v];[0:a]atempo={factor:.5f}[a]",
         "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
         "-movflags", "+faststart", str(out)],
        check=True,
    )
    log(f"Compressed duration: {ffprobe_duration(out):.1f}s")
    return out


# ── Caption ───────────────────────────────────────────────────────────────────

# Per-channel caption branding. Keyed by the post log's "channel" field
# (mz / tmf / bsg) with a fallback keyed off the log filename. Sep 27 2026:
# the first TMF Reel went out with MZ's tagline and #MinuteZero -- this fixes it.
CHANNEL_BRAND = {
    "mz":  {"tagline": "The moment it all broke. New one every day.",
            "tag": "#MinuteZero",
            "fill": ["#businesshistory", "#corporatehistory", "#truestory"]},
    "tmf": {"tagline": "Why your mind does what it does. New one every day.",
            "tag": "#TheMindFiles",
            "fill": ["#psychology", "#humanbehavior", "#selfawareness"]},
    "bsg": {"tagline": "Bible stories, told simply. New one every day.",
            "tag": "#BibleStoryGarden",
            "fill": ["#biblestories", "#faith", "#scripture"]},
}

def _channel_key(post: dict) -> str:
    ch = (post.get("channel") or "").lower().strip()
    if ch in CHANNEL_BRAND:
        return ch
    for k in CHANNEL_BRAND:
        if k in POST_LOG.lower():
            return k
    return "mz"


def build_caption(post: dict) -> str:
    brand = CHANNEL_BRAND[_channel_key(post)]
    title = (post.get("title") or "").strip()
    desc  = (post.get("description") or "").strip()
    tags  = (post.get("hashtags") or "").split()

    # First sentence of the description is the hook; drop the YouTube-flavoured
    # tail ("Follow Minute Zero for more...") which reads as cross-post boilerplate.
    hook = re.split(r"(?<=[.!?])\s+", desc)[0] if desc else ""
    hook = hook if 20 <= len(hook) <= 220 else ""

    # Drop platform-specific tags, keep the topical ones, cap at 5, add the brand.
    drop = {"#shorts", "#one_bad_day", "#unknown_failure", "#near_death", "#reels", "#fyp"}
    tags = [t for t in tags if t.lower() not in drop and t.lower() != brand["tag"].lower()]
    if not tags:
        tags = list(brand["fill"])
    tags = ([brand["tag"]] + tags)[:MAX_HASHTAGS]

    parts = [title]
    if hook and hook.lower() != title.lower():
        parts.append(hook)
    parts.append(brand["tagline"])
    parts.append(" ".join(tags))
    return "\n\n".join(p for p in parts if p)


# ── Facebook calls ────────────────────────────────────────────────────────────

def graph_post(path: str, **data) -> dict:
    data["access_token"] = PAGE_TOKEN
    r = requests.post(f"{GRAPH}/{path}", data=data, timeout=60)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text}
    if not r.ok or "error" in body:
        raise RuntimeError(f"{path}: {r.status_code} {json.dumps(body)[:400]}")
    return body


def publish_reel(video: Path, caption: str) -> str:
    size = video.stat().st_size
    log(f"Reel upload: {video.name} ({size // 1024 // 1024} MB)")

    init = graph_post(f"{PAGE_ID}/video_reels", upload_phase="start")
    video_id = init["video_id"]
    log(f"video_id={video_id}")

    with open(video, "rb") as fh:
        r = requests.post(
            f"{RUPLOAD}/{video_id}",
            headers={"Authorization": f"OAuth {PAGE_TOKEN}",
                     "offset": "0", "file_size": str(size)},
            data=fh, timeout=600,
        )
    if not r.ok or not r.json().get("success"):
        raise RuntimeError(f"rupload: {r.status_code} {r.text[:400]}")
    log("Bytes uploaded")

    graph_post(f"{PAGE_ID}/video_reels", upload_phase="finish",
               video_state="PUBLISHED", video_id=video_id, description=caption)

    # Processing is async; poll status so the workflow log shows the real outcome.
    for _ in range(PUBLISH_POLL_TRIES):
        st = requests.get(f"{GRAPH}/{video_id}",
                          params={"fields": "status", "access_token": PAGE_TOKEN},
                          timeout=30).json().get("status", {})
        phase = st.get("video_status", "?")
        pub   = (st.get("publishing_phase") or {}).get("status", "?")
        log(f"status: video={phase} publishing={pub}")
        if pub == "complete" or phase == "ready":
            break
        if phase == "error" or pub == "error":
            raise RuntimeError(f"processing error: {json.dumps(st)[:400]}")
        time.sleep(PUBLISH_POLL_SEC)
    return video_id


def publish_feed_video_fallback(video: Path, title: str, caption: str) -> str:
    log("Falling back to legacy feed video post (/me/videos)")
    with open(video, "rb") as fh:
        r = requests.post(f"{GRAPH}/me/videos",
                          data={"title": title, "description": caption,
                                "published": "true", "access_token": PAGE_TOKEN},
                          files={"source": (video.name, fh, "video/mp4")}, timeout=300)
    body = r.json() if r.ok else {}
    if not body.get("id"):
        raise RuntimeError(f"feed fallback failed: {r.status_code} {r.text[:300]}")
    return body["id"]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    if not PAGE_TOKEN or not PAGE_ID:
        print("Missing FB_PAGE_ACCESS_TOKEN or FB_PAGE_ID -- skipping")
        return 0 if DRY_RUN else 1

    video = find_video()
    if not video:
        print("No MZ video found -- skipping FB post")
        return 0

    post    = newest_post()
    title   = (post.get("title") or "New video").strip()
    caption = build_caption(post)
    print(f"Facebook Reel for page {PAGE_ID}: {title}")
    log("Caption:\n" + "\n".join("    " + l for l in caption.splitlines()))

    work = Path(tempfile.mkdtemp(prefix="fbreel_"))
    try:
        reel_video = fit_to_reel_length(video, work)
        if DRY_RUN:
            log(f"DRY RUN -- would publish {'Reel' if reel_video else 'feed video'} from "
                f"{reel_video or video}")
            return 0
        if reel_video is not None:
            try:
                vid = publish_reel(reel_video, caption)
                print(f"FB Reel published: video_id={vid}")
                return 0
            except Exception as e:  # noqa: BLE001
                log(f"Reel publish failed: {e}")
                if not FALLBACK:
                    return 1
        vid = publish_feed_video_fallback(video, title, caption)
        print(f"FB feed video published (fallback): id={vid}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"FB upload failed: {e}")
        return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
