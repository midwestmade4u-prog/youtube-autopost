#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  video_mz.py — Minute Zero render pipeline                   ║
║  Pexels stock footage + edge-tts narration + ffmpeg overlay  ║
╚══════════════════════════════════════════════════════════════╝

Produces one MZ Short from a v3 script-generator JSON output.

Outputs in the destination directory (one render per video ID):
  {id}_master.mp4   — clean master, MZ watermark only (no platform marks)
  {id}_yt.mp4       — YouTube Shorts variant
  {id}_tt.mp4       — TikTok variant (end card: "Follow @minutezero on YT")
  {id}_ig.mp4       — Instagram Reels variant (end card: "More on YT")
  {id}_thumb.jpg    — Custom YT Shorts thumbnail (1080x1920)
  {id}_narration.mp3— Raw TTS narration (kept for debugging)

Design goals (per Apr 24 viral research):
  • Clean master / per-platform variants — YT won't distribute Shorts with
    TikTok or Instagram watermarks. Keep master clean, add platform branding
    only when exporting that platform's variant.
  • Visual change every ~8s — beat durations are carved to enforce this.
  • Loop design — first and last Pexels clips come from semantically paired
    queries (v3 prompt requirement), which the renderer respects by placing
    query[0] and query[-1] at the bookends.
  • No AI-generated imagery — all visuals are real Pexels stock/archival.

Usage:
    # From another script (e.g. auto_post_mz.py):
    from video_mz import render_video

    script_data = {...}   # v3 JSON output
    result = render_video(script_data, out_dir="./MZ_Output/2026-04-27")
    print(result["master_path"])

Required env vars:
    PEXELS_API_KEY    — from https://www.pexels.com/api/
    (Optionally) MZ_VOICE — edge-tts voice name, default "en-US-ChristopherNeural"

Requirements:
    pip3 install edge-tts Pillow requests --break-system-packages
    + system ffmpeg (already installed on dev and GH runner)
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ─── Configuration ──────────────────────────────────────────────────────────

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
MZ_VOICE = os.environ.get("MZ_VOICE", "en-US-ChristopherNeural")  # deep male narrator

# Per-channel Pexels clip-ID ledger. Tracks every clip ID we've already used so
# future renders skip them (prevents footage reuse across MZ videos which
# would tank novelty signals on Shorts). Path is relative to the project root
# so it persists alongside the source code; for GH Actions we'll have the
# workflow git-commit it back after each successful run.
PEXELS_LEDGER_PATH = Path(__file__).parent / "pexels_used_mz.json"

# Video output spec — 1080x1920 vertical for all platforms
VIDEO_W, VIDEO_H = 1080, 1920
FPS = 30

# Beat timing distribution (portion of total runtime, in order)
BEAT_SHARES = {
    "past_greatness": 0.15,
    "setup":          0.20,
    "minute_zero":    0.50,
    "the_fall":       0.15,
}

# Fonts — prefer bundled MZ brand font, fall back to any bold system font
FONT_CANDIDATES = [
    "/sessions/nifty-nice-volta/mnt/Youtube Channels Project/MZ_Channel/Assets/MZ_Heading.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",      # mac
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # linux
    "/Library/Fonts/Arial Bold.ttf",
]

# Brand palette (matches branding v3)
RED     = (239, 43, 61)       # #ef2b3d
BLACK   = (13, 13, 13)
WHITE   = (248, 248, 248)
CHARCOAL = (32, 32, 36)


# ─── Helpers ────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[video_mz] {msg}", flush=True)


def _pick_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _run_ffmpeg(args: list[str], label: str = "ffmpeg") -> None:
    """Run ffmpeg with sensible error surfacing."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    _log(f"{label}: {' '.join(cmd[:8])} ...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr or "")
        raise RuntimeError(f"{label} failed (exit {res.returncode})")


def _ffprobe_duration(path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip())
    except (ValueError, TypeError):
        return 0.0


def _safe_id(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title.strip())[:60].strip("_").lower()
    return f"{int(time.time())}_{slug}"


# ─── Pexels ──────────────────────────────────────────────────────────────────

def pexels_search_video(query: str, per_page: int = 25) -> list[dict]:
    """Search Pexels videos — returns list of dicts with download-ready info.

    `per_page` defaults to 25 (Pexels max-per-page-friendly) so the dedup
    ledger has plenty of unused candidates to choose from. Bumped from 5
    after observing footage reuse across MZ videos in v1.
    """
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY not set. Add to env or .env file.")
    url = "https://api.pexels.com/videos/search"
    params = {"query": query, "per_page": per_page, "orientation": "portrait"}
    r = requests.get(url, headers={"Authorization": PEXELS_API_KEY}, params=params, timeout=30)
    r.raise_for_status()
    videos = r.json().get("videos", [])
    results = []
    for v in videos:
        # Pick the best 1080x1920-ish file
        files = v.get("video_files", [])
        files.sort(key=lambda f: (abs(f.get("width", 0) - VIDEO_W) + abs(f.get("height", 0) - VIDEO_H)))
        if not files:
            continue
        results.append({
            "id": v.get("id"),
            "duration": v.get("duration", 0),
            "url": files[0].get("link"),
            "width": files[0].get("width"),
            "height": files[0].get("height"),
        })
    return results


def download_pexels_clip(url: str, out_path: Path) -> Path:
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(out_path, "wb") as fh:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            fh.write(chunk)
    return out_path


def load_used_clip_ids(ledger_path: Path = PEXELS_LEDGER_PATH) -> set[int]:
    """Load the set of Pexels clip IDs we've already used for this channel."""
    if not ledger_path.exists():
        return set()
    try:
        data = json.loads(ledger_path.read_text())
        return set(int(x) for x in data.get("used_ids", []))
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        _log(f"⚠️  Could not read ledger {ledger_path.name}: {exc}. Starting empty.")
        return set()


def save_used_clip_ids(used_ids: set[int], ledger_path: Path = PEXELS_LEDGER_PATH) -> None:
    """Persist the updated set of used clip IDs to disk."""
    payload = {
        "channel":    "mz",
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count":      len(used_ids),
        "used_ids":   sorted(used_ids),
    }
    ledger_path.write_text(json.dumps(payload, indent=2))


def pick_unused_clip(results: list[dict], slot_dur: float, used_ids: set[int]) -> dict | None:
    """
    From a list of Pexels search results, pick the first clip that:
      1. Is long enough for the slot, AND
      2. Has not already been used (id not in `used_ids`).

    If no clip satisfies both, fall back to (a) any unused clip regardless of
    duration, then (b) any long-enough clip regardless of dedup, then (c) the
    first result. Returns None only if `results` is empty.
    """
    if not results:
        return None
    # 1st choice: unused AND long enough
    for r in results:
        if r["id"] not in used_ids and r["duration"] >= slot_dur:
            return r
    # 2nd choice: unused (even if shorter — we'll loop it)
    for r in results:
        if r["id"] not in used_ids:
            return r
    # 3rd choice: long enough (ledger exhausted for this query)
    for r in results:
        if r["duration"] >= slot_dur:
            _log(f"⚠️  Ledger exhausted for query — reusing clip {r['id']}")
            return r
    # Last resort
    _log(f"⚠️  No good match — reusing clip {results[0]['id']}")
    return results[0]


# ─── Narration (edge-tts) ───────────────────────────────────────────────────

async def _edge_tts_stream_with_timings(text: str, voice: str, out_path: Path) -> list[dict]:
    """
    Stream TTS to an MP3 file *and* capture per-word timing from edge-tts'
    WordBoundary events. Microsoft TTS reports offsets in 100-nanosecond
    units, so we divide by 1e7 to get seconds.

    Returns a list of {"word", "start", "end"} dicts in playback order.
    """
    import edge_tts
    timings: list[dict] = []
    # edge-tts >= 7.0 defaults to SentenceBoundary (one event per sentence),
    # which is too coarse for karaoke captions. Opt back into per-word events.
    communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
    with open(out_path, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                dur   = chunk["duration"] / 10_000_000
                timings.append({
                    "word":  chunk["text"],
                    "start": start,
                    "end":   start + dur,
                })
    return timings


def generate_narration(script: str, out_path: Path, voice: str = MZ_VOICE) -> tuple[Path, list[dict]]:
    """
    Produce TTS narration MP3 + word-level timings from script text.

    Returns (out_path, word_timings) where word_timings is a list of
    {"word", "start", "end"} dicts. Used by build_caption_chunks() to
    produce karaoke-style captions burned into the final render.
    """
    timings = asyncio.run(_edge_tts_stream_with_timings(script, voice, out_path))
    return out_path, timings


# ─── Beat timing ────────────────────────────────────────────────────────────

def carve_beat_windows(total_sec: float) -> dict[str, tuple[float, float]]:
    """
    Return {beat_name: (start_sec, end_sec)} for a given total runtime.
    Uses BEAT_SHARES distribution in order.
    """
    windows: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for beat, share in BEAT_SHARES.items():
        length = total_sec * share
        windows[beat] = (cursor, cursor + length)
        cursor += length
    return windows


def distribute_queries_to_beats(queries: list[str], windows: dict[str, tuple[float, float]]) -> list[dict]:
    """
    Split 6–10 Pexels queries evenly across the 4 beats (in order),
    with more queries in minute_zero since it's the longest beat.
    Returns [{"query": ..., "start": ..., "end": ...}, ...].
    """
    # Weight slots per beat roughly proportional to beat share
    n = len(queries)
    weights = [BEAT_SHARES[b] for b in windows.keys()]
    beats   = list(windows.keys())

    # Rough slot allocation by weight
    raw = [n * w for w in weights]
    slots = [max(1, int(round(x))) for x in raw]
    # Force total == n
    while sum(slots) > n:
        slots[slots.index(max(slots))] -= 1
    while sum(slots) < n:
        slots[slots.index(min(slots))] += 1

    out: list[dict] = []
    qi = 0
    for beat, count in zip(beats, slots):
        b_start, b_end = windows[beat]
        slot_len = (b_end - b_start) / count
        for k in range(count):
            out.append({
                "query": queries[qi],
                "beat":  beat,
                "start": b_start + k * slot_len,
                "end":   b_start + (k + 1) * slot_len,
            })
            qi += 1
    return out


# ─── Clip rendering (trim + scale + crop to 1080x1920) ──────────────────────

def render_clip_segment(src: Path, duration: float, out: Path) -> Path:
    """Trim to `duration`, scale-crop to 1080x1920, no audio."""
    vf = (
        f"scale=w={VIDEO_W}:h={VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W}:{VIDEO_H},"
        f"fps={FPS},setsar=1"
    )
    _run_ffmpeg([
        "-i", str(src),
        "-t", f"{duration:.3f}",
        "-an",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(out),
    ], label=f"clip {out.name}")
    return out


def concat_clips(clip_paths: list[Path], out: Path) -> Path:
    """Concat clips via ffmpeg concat demuxer."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for cp in clip_paths:
            f.write(f"file '{cp.resolve()}'\n")
        list_path = f.name
    try:
        _run_ffmpeg([
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            str(out),
        ], label="concat")
    finally:
        Path(list_path).unlink(missing_ok=True)
    return out


# ─── Text overlay (Pillow PNG + ffmpeg overlay) ─────────────────────────────
# Rendered as transparent PNGs and composited via ffmpeg's `overlay` filter,
# which is always available. Avoids the drawtext filter (requires ffmpeg to be
# built with libfreetype; Homebrew's Tahoe bottle ships without it).
#
# Style: "Documentary Lower-Third" (picked 2026-04-24 from the three-option
# research pass). Oswald Bold 700, title case, white on translucent black pill
# with a red accent bar on the left, left-aligned at y ≈ 78% of the frame.
# Exemplars: RealLifeLore, ColdFusion editorial. Suits slow-burn forensics.

# Mirror list for Oswald font download — tried in order. Ends with a Linux
# fallback (DejaVu Sans Bold, present on GH Actions Ubuntu) and macOS Impact
# so the pipeline never hard-fails on font availability.
OSWALD_FONT_URLS = [
    # Google Fonts canonical variable font
    "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
    # jsdelivr mirror of the same file (different CDN, same bytes)
    "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/oswald/Oswald%5Bwght%5D.ttf",
    # Alternative naming convention some Google Fonts entries use
    "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald-VariableFont_wght.ttf",
    # github.com's /raw/ path (redirects to raw.githubusercontent but through a different route)
    "https://github.com/google/fonts/raw/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
]

# TTF file magic bytes — used to sanity-check downloads aren't HTML 404 pages
_TTF_MAGIC = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1")


def _ensure_oswald_bold() -> Path:
    """
    Return path to an Oswald TTF. Checks project Assets dir first, downloads
    from a prioritized list of CDN mirrors on first run, validates each
    response is a real TTF, and falls back to Impact (macOS) or DejaVu
    (Linux) if every mirror fails. Self-healing across dev + CI.
    """
    asset_dir = Path(__file__).resolve().parent / "MZ_Channel" / "Assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    dest = asset_dir / "Oswald.ttf"
    if dest.exists() and dest.stat().st_size > 50_000:
        return dest

    for url in OSWALD_FONT_URLS:
        try:
            _log(f"fetching Oswald from {url.split('//', 1)[1][:50]}...")
            r = requests.get(url, timeout=30, allow_redirects=True)
            r.raise_for_status()
            if r.content[:4] in _TTF_MAGIC:
                dest.write_bytes(r.content)
                _log(f"cached Oswald ({len(r.content) // 1024} KB)")
                return dest
            _log(f"  → response not a TTF ({len(r.content)} bytes), trying next mirror")
        except Exception as exc:
            _log(f"  → {type(exc).__name__}: {str(exc)[:80]}")
            continue

    # All mirrors failed — fall back to a locally-installed condensed bold font
    for fallback in (
        "/System/Library/Fonts/Supplemental/Impact.ttf",       # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux / GH runner
    ):
        fp = Path(fallback)
        if fp.exists():
            _log(f"Oswald download failed — falling back to {fp.name}")
            return fp
    raise RuntimeError("Could not obtain Oswald or any fallback font")


def _title_case_cue(text: str) -> str:
    """Cue text often arrives ALL-CAPS — normalize to title case for Option B style."""
    return text.title() if text.isupper() else text


def render_cue_png(
    text: str,
    out_path: Path,
    sub_text: str | None = None,
) -> Path:
    """
    Render a single on-screen text cue as a 1080x1920 transparent PNG.

    Style (Documentary Lower-Third):
      - Oswald Bold 700, title case
      - White text on a translucent black pill (~65% opacity)
      - 12px red accent bar running down the left edge of the pill
      - Pill left-aligned (60px from left edge), centered at y ≈ 78%
      - Optional sub_text renders beneath in smaller size, all-caps with
        wide letter-spacing (e.g. "PARIS · 7:50 A.M.") — acts as a
        documentary-style secondary label.
    """
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    oswald_path = str(_ensure_oswald_bold())
    main_font = ImageFont.truetype(oswald_path, 88)
    sub_font  = ImageFont.truetype(oswald_path, 38)
    # If Oswald variable font, pin weight axis to Bold (700) / Medium (500).
    # Silently no-ops for static TTFs or Pillow < 9.1.
    try:
        main_font.set_variation_by_axes([700])
    except Exception:
        pass
    try:
        sub_font.set_variation_by_axes([500])
    except Exception:
        pass

    main_txt = _title_case_cue(text)
    sub_txt  = sub_text.upper() if sub_text else None

    # Measure
    mb = d.textbbox((0, 0), main_txt, font=main_font)
    main_w, main_h = mb[2] - mb[0], mb[3] - mb[1]
    if sub_txt:
        sb = d.textbbox((0, 0), sub_txt, font=sub_font)
        sub_w, sub_h = sb[2] - sb[0], sb[3] - sb[1]
        sub_gap = 14
    else:
        sb = None
        sub_w = sub_h = sub_gap = 0

    # Pill sizing
    pad_left  = 42   # extra room for the red accent bar
    pad_right = 34
    pad_top   = 26
    pad_bot   = 28
    content_w = max(main_w, sub_w)
    content_h = main_h + sub_gap + sub_h if sub_txt else main_h
    pill_w = content_w + pad_left + pad_right
    pill_h = content_h + pad_top + pad_bot

    # Pill position: left-aligned, centered on y=78%
    pill_x = 60
    pill_y = int(VIDEO_H * 0.78) - pill_h // 2

    # Translucent black pill (~65% opacity)
    d.rectangle(
        [(pill_x, pill_y), (pill_x + pill_w, pill_y + pill_h)],
        fill=(0, 0, 0, 166),
    )
    # Red accent bar down the left edge (12px — visually matches 3px at mockup scale)
    accent_w = 12
    d.rectangle(
        [(pill_x, pill_y), (pill_x + accent_w, pill_y + pill_h)],
        fill=RED,
    )

    # Main text, left-aligned inside pill (compensate for bbox top padding)
    text_x = pill_x + pad_left
    text_y = pill_y + pad_top - mb[1]
    d.text((text_x, text_y), main_txt, font=main_font, fill=WHITE)

    # Sub text beneath (wider letter-spacing faked via tracking)
    if sub_txt and sb:
        sub_x = pill_x + pad_left
        sub_y = pill_y + pad_top + main_h + sub_gap - sb[1]
        # Pillow doesn't have native letter-spacing — draw char-by-char w/ tracking
        cursor = sub_x
        for ch in sub_txt:
            d.text((cursor, sub_y), ch, font=sub_font, fill=(230, 230, 230, 220))
            ch_bbox = d.textbbox((0, 0), ch, font=sub_font)
            cursor += (ch_bbox[2] - ch_bbox[0]) + 5  # 5px tracking

    img.save(out_path, "PNG")
    return out_path


def build_cue_overlays(
    cues: list[dict],
    windows: dict[str, tuple[float, float]],
    work: Path,
) -> list[dict]:
    """
    Render each cue to a PNG and return [{"png": Path, "t_in", "t_out"}, ...].
    For cues on the same beat, split the beat window evenly. Cue dicts may
    optionally include a "sub" field for the documentary sub-line.
    """
    by_beat: dict[str, list[dict]] = {}
    for c in cues:
        by_beat.setdefault(c["beat"], []).append(c)

    overlays: list[dict] = []
    idx = 0
    for beat, beat_cues in by_beat.items():
        b_start, b_end = windows.get(beat, (0.0, 0.0))
        slot_len = (b_end - b_start) / len(beat_cues)
        for i, c in enumerate(beat_cues):
            t_in  = b_start + i * slot_len
            t_out = b_start + (i + 1) * slot_len - 0.1
            png = work / f"cue_{idx:02d}.png"
            render_cue_png(c["text"], png, sub_text=c.get("sub"))
            overlays.append({"png": png, "t_in": t_in, "t_out": t_out})
            idx += 1
    return overlays


def apply_cue_overlays(src: Path, overlays: list[dict], out: Path) -> Path:
    """
    Composite each cue PNG onto `src` with its timing window via ffmpeg's
    `overlay` filter. Chains overlays sequentially in a filter_complex.
    """
    if not overlays:
        shutil.copy(src, out)
        return out

    inputs: list[str] = ["-i", str(src)]
    for ov in overlays:
        inputs += ["-i", str(ov["png"])]

    parts: list[str] = []
    prev = "0:v"
    for i, ov in enumerate(overlays, start=1):
        label = "vout" if i == len(overlays) else f"v{i}"
        parts.append(
            f"[{prev}][{i}:v]overlay=0:0:"
            f"enable='between(t,{ov['t_in']:.2f},{ov['t_out']:.2f})'"
            f"[{label}]"
        )
        prev = label
    filter_complex = ";".join(parts)

    _run_ffmpeg([
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        str(out),
    ], label="overlay_cues")
    return out


# ─── Karaoke captions (full-narration burn-in) ──────────────────────────────
# Why captions, not sparse cues:
#   ~85% of Shorts/Reels/TikTok views happen on mute. Sparse editorial cue
#   overlays (5-7 per video) leave the muted majority unable to follow the
#   story. Word-by-word burned-in captions are the #1 retention pattern on
#   short-form vertical video — every viral creator (MrBeast, Hormozi,
#   Modern MBA, etc.) uses them, and the third-party tools that automate
#   them (Submagic, Opus Clip, CapCut auto-captions) are now industry
#   standard. Retention is the #1 ranking signal for Shorts, so this is
#   directly tied to algorithmic distribution.
#
# Style follows the dominant viral-Shorts convention:
#   - 2-3 words per on-screen chunk (mobile readable in <0.5s)
#   - Oswald Bold 700, ALL CAPS, ~120px
#   - White fill with heavy black stroke (no pill background)
#   - Centered horizontally, positioned slightly below center vertically
#   - Each chunk runs until the next one starts (no gaps, no flicker)


def build_caption_chunks(
    word_timings: list[dict],
    max_words: int = 3,
    max_dur: float = 1.4,
) -> list[dict]:
    """
    Group raw edge-tts word timings into 2-3 word caption chunks.

    Heuristics:
      - Up to `max_words` per chunk OR `max_dur` seconds, whichever first.
      - Each chunk's end is bumped to the next chunk's start so the caption
        track has zero gaps (less flicker, smoother to read on mute).
      - Final chunk's end stays as the last word's spoken end-time.

    Returns: [{"text", "start", "end"}, ...]
    """
    if not word_timings:
        return []

    chunks: list[dict] = []
    cur: list[dict] = []

    for w in word_timings:
        cur.append(w)
        cur_dur = cur[-1]["end"] - cur[0]["start"]
        if len(cur) >= max_words or cur_dur >= max_dur:
            chunks.append({
                "text":  " ".join(cw["word"] for cw in cur),
                "start": cur[0]["start"],
                "end":   cur[-1]["end"],
            })
            cur = []

    if cur:
        chunks.append({
            "text":  " ".join(cw["word"] for cw in cur),
            "start": cur[0]["start"],
            "end":   cur[-1]["end"],
        })

    # Stretch each chunk to butt up against the next — no flicker gaps
    for i in range(len(chunks) - 1):
        chunks[i]["end"] = chunks[i + 1]["start"]

    return chunks


def render_caption_png(text: str, out_path: Path) -> Path:
    """
    Render a single karaoke-style caption chunk as a 1080x1920 transparent
    PNG. White Oswald Bold with a heavy black stroke for legibility on any
    background (no pill, no background). Centered horizontally, positioned
    at y ≈ 62% of the frame (just below center, optimal for phone reading).
    """
    img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    oswald_path = str(_ensure_oswald_bold())
    font = ImageFont.truetype(oswald_path, 120)
    try:
        font.set_variation_by_axes([700])
    except Exception:
        pass

    txt = text.strip().upper()  # ALL CAPS — viral-native, max impact

    # Auto-wrap: prefer 1 line, allow up to 2. Width budget ~86% of frame.
    max_line_w = int(VIDEO_W * 0.86)
    words = txt.split()
    lines: list[str] = []
    line = ""
    for w in words:
        candidate = (line + " " + w).strip() if line else w
        bbox = d.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] > max_line_w and line:
            lines.append(line)
            line = w
        else:
            line = candidate
    if line:
        lines.append(line)
    lines = lines[:2]

    line_h = 140
    total_h = line_h * len(lines)
    y_start = int(VIDEO_H * 0.62) - total_h // 2

    stroke_w = 10
    for i, ln in enumerate(lines):
        bbox = d.textbbox((0, 0), ln, font=font)
        tw = bbox[2] - bbox[0]
        x = (VIDEO_W - tw) // 2
        # Compensate for bbox top-padding so baseline lands consistently
        y = y_start + i * line_h - bbox[1]
        d.text(
            (x, y),
            ln,
            font=font,
            fill=WHITE,
            stroke_width=stroke_w,
            stroke_fill=BLACK,
        )

    img.save(out_path, "PNG")
    return out_path


def build_caption_overlays(chunks: list[dict], work: Path) -> list[dict]:
    """
    Render each caption chunk to a PNG and return a list of overlay specs
    in the format apply_cue_overlays() expects: {"png", "t_in", "t_out"}.
    """
    overlays: list[dict] = []
    for i, ch in enumerate(chunks):
        png = work / f"cap_{i:03d}.png"
        render_caption_png(ch["text"], png)
        overlays.append({
            "png":   png,
            "t_in":  ch["start"],
            "t_out": ch["end"],
        })
    return overlays


# ─── Watermark ──────────────────────────────────────────────────────────────

WATERMARK_PATH = Path("/sessions/nifty-nice-volta/mnt/Youtube Channels Project/MinuteZero_Watermark.png")


def apply_watermark(src: Path, out: Path) -> Path:
    """Overlay MZ watermark bottom-right, ~15% of video width."""
    if not WATERMARK_PATH.exists():
        shutil.copy(src, out)
        return out
    _run_ffmpeg([
        "-i", str(src),
        "-i", str(WATERMARK_PATH),
        "-filter_complex",
        f"[1:v]scale={int(VIDEO_W*0.22)}:-1[wm];"
        f"[0:v][wm]overlay=W-w-40:H-h-140:format=auto",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(out),
    ], label="watermark")
    return out


# ─── End cards (platform-specific) ──────────────────────────────────────────

def build_end_card(text: str, out_path: Path, duration: float = 3.0) -> Path:
    """Render a 3-second end card with white-on-black text. Returns mp4 path."""
    img = Image.new("RGB", (VIDEO_W, VIDEO_H), BLACK)
    d = ImageDraw.Draw(img)
    font = _pick_font(96)
    lines = text.upper().split("\n")
    line_h = 130
    total_h = line_h * len(lines)
    y_start = (VIDEO_H - total_h) // 2
    for i, line in enumerate(lines):
        bbox = d.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        d.text(((VIDEO_W - tw) // 2, y_start + i * line_h), line, font=font, fill=WHITE)
    # accent bar
    d.rectangle([(VIDEO_W // 2 - 120, y_start - 32), (VIDEO_W // 2 + 120, y_start - 24)], fill=RED)

    tmp_img = out_path.with_suffix(".png")
    img.save(tmp_img, "PNG")
    _run_ffmpeg([
        "-loop", "1",
        "-i", str(tmp_img),
        "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-vf", f"fps={FPS}",
        str(out_path),
    ], label="end_card")
    tmp_img.unlink(missing_ok=True)
    return out_path


def append_end_card(master: Path, end_card: Path, out: Path) -> Path:
    """Concat master + end card. Keep audio from master; end card is silent."""
    # Build silent audio for end card matching its duration
    ec_dur = _ffprobe_duration(end_card)
    silent_audio = end_card.with_suffix(".silent.m4a")
    _run_ffmpeg([
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", f"{ec_dur:.3f}",
        "-c:a", "aac", "-b:a", "128k",
        str(silent_audio),
    ], label="silent_audio")
    end_card_with_audio = end_card.with_suffix(".wa.mp4")
    _run_ffmpeg([
        "-i", str(end_card),
        "-i", str(silent_audio),
        "-c:v", "copy", "-c:a", "copy",
        "-shortest",
        str(end_card_with_audio),
    ], label="end_card+audio")

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(f"file '{master.resolve()}'\n")
        f.write(f"file '{end_card_with_audio.resolve()}'\n")
        list_path = f.name
    try:
        _run_ffmpeg([
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            str(out),
        ], label="append_end_card")
    finally:
        Path(list_path).unlink(missing_ok=True)
        silent_audio.unlink(missing_ok=True)
        end_card_with_audio.unlink(missing_ok=True)
    return out


# ─── Thumbnail (custom YT Shorts thumb) ─────────────────────────────────────

def render_thumbnail(thumbnail_text: str, first_clip: Path, out: Path) -> Path:
    """
    Grab the first frame of the first clip as a background, overlay
    thumbnail_text in MZ brand style.
    """
    # Extract first frame
    frame = out.with_suffix(".frame.jpg")
    _run_ffmpeg([
        "-i", str(first_clip),
        "-vframes", "1",
        "-vf", f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,crop={VIDEO_W}:{VIDEO_H}",
        str(frame),
    ], label="thumb_frame")

    img = Image.open(frame).convert("RGB")
    # Darken
    overlay = Image.new("RGB", img.size, BLACK)
    img = Image.blend(img, overlay, alpha=0.45)

    d = ImageDraw.Draw(img)
    # Main punch text, ALL CAPS, up to 3 lines
    words = thumbnail_text.upper().split()
    lines: list[str] = []
    line = ""
    for w in words:
        if len(line) + len(w) > 14 and line:
            lines.append(line.strip())
            line = w + " "
        else:
            line += w + " "
    if line.strip():
        lines.append(line.strip())
    lines = lines[:3]

    font = _pick_font(180)
    line_h = 210
    total_h = line_h * len(lines)
    y_start = (VIDEO_H - total_h) // 2
    for i, ln in enumerate(lines):
        bbox = d.textbbox((0, 0), ln, font=font)
        tw = bbox[2] - bbox[0]
        x = (VIDEO_W - tw) // 2
        y = y_start + i * line_h
        # Stroke
        for ox, oy in ((-4, 0), (4, 0), (0, -4), (0, 4)):
            d.text((x + ox, y + oy), ln, font=font, fill=BLACK)
        d.text((x, y), ln, font=font, fill=WHITE)

    # Red accent bar
    d.rectangle([(VIDEO_W // 2 - 160, y_start - 48), (VIDEO_W // 2 + 160, y_start - 36)], fill=RED)

    img.save(out, "JPEG", quality=92)
    frame.unlink(missing_ok=True)
    return out


# ─── Main pipeline ──────────────────────────────────────────────────────────

def render_video(script_data: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    """
    Full MZ render pipeline.

    Args:
      script_data: v3 JSON output from the script generator.
      out_dir:     directory to write the final files.

    Returns:
      {"master_path": ..., "yt_path": ..., "tt_path": ...,
       "ig_path": ..., "thumb_path": ..., "narration_path": ...}
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    vid_id = _safe_id(script_data["title"])
    work = out_dir / f"_{vid_id}_work"
    work.mkdir(exist_ok=True)

    script     = script_data["script"]
    queries    = script_data["pexels_search_queries"]
    cues       = script_data.get("onscreen_text_cues", [])
    target_dur = float(script_data.get("target_duration_sec", 75))
    thumb_text = script_data.get("thumbnail_text", script_data.get("title", ""))

    # 1. Narration (captures word-level timings for karaoke captions)
    narration = out_dir / f"{vid_id}_narration.mp3"
    _log("generating narration ...")
    narration, word_timings = generate_narration(script, narration)
    actual_dur = _ffprobe_duration(narration)
    _log(f"narration duration: {actual_dur:.1f}s (target {target_dur:.0f}s), {len(word_timings)} words timed")

    # 2. Carve beats + distribute queries
    windows = carve_beat_windows(actual_dur)
    slot_plan = distribute_queries_to_beats(queries, windows)
    _log(f"beat windows: {windows}")
    _log(f"{len(slot_plan)} visual slots planned")

    # 3. Pexels fetch + trim per slot
    #    Dedup: load the channel's used-clip ledger so we never re-pull a clip
    #    we've already shipped in a prior MZ video. New IDs are queued in
    #    `newly_used` and committed to the ledger only after the whole render
    #    pipeline finishes (so a mid-render crash doesn't poison the ledger).
    used_ids: set[int] = load_used_clip_ids()
    newly_used: set[int] = set()
    _log(f"loaded clip ledger: {len(used_ids)} previously-used IDs")

    clip_paths: list[Path] = []
    for i, slot in enumerate(slot_plan):
        slot_dur = slot["end"] - slot["start"]
        _log(f"[{i+1}/{len(slot_plan)}] '{slot['query']}' ({slot_dur:.1f}s)")
        results = pexels_search_video(slot["query"], per_page=25)
        if not results:
            # Fallback: reuse the previous clip if search was empty
            if clip_paths:
                clip_paths.append(clip_paths[-1])
                continue
            raise RuntimeError(f"Pexels returned nothing for '{slot['query']}'")
        src_mp4 = work / f"src_{i:02d}.mp4"
        # Pick a clip that's (a) unused and (b) long enough — fallbacks inside.
        # Treat any clip we've picked earlier in *this* render as also "used"
        # so we don't double-pull within a single video either.
        chosen = pick_unused_clip(results, slot_dur, used_ids | newly_used)
        newly_used.add(chosen["id"])
        download_pexels_clip(chosen["url"], src_mp4)
        out_clip = work / f"seg_{i:02d}.mp4"
        render_clip_segment(src_mp4, slot_dur, out_clip)
        clip_paths.append(out_clip)

    # 4. Concat silent video
    silent_video = work / "silent.mp4"
    concat_clips(clip_paths, silent_video)

    # 5. Add narration audio
    av_mixed = work / "av_mixed.mp4"
    _run_ffmpeg([
        "-i", str(silent_video),
        "-i", str(narration),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(av_mixed),
    ], label="av_mux")

    # 6. Burn in karaoke-style full captions from narration word timings.
    #    ~85% of Shorts views happen on mute, so full captions (not sparse
    #    editorial cues) are required to hold a muted audience. Retention
    #    is the #1 ranking signal for Shorts, so this is also algorithmic.
    #    The legacy `cues` field from script_data is intentionally ignored
    #    here — left unused so we can layer it back as documentary stamps
    #    if A/B testing ever calls for it.
    caption_chunks = build_caption_chunks(word_timings, max_words=3, max_dur=1.4)
    _log(f"{len(caption_chunks)} caption chunks ({len(word_timings)} words)")
    if caption_chunks:
        overlays  = build_caption_overlays(caption_chunks, work)
        captioned = work / "captioned.mp4"
        apply_cue_overlays(av_mixed, overlays, captioned)
    else:
        captioned = av_mixed

    # 7. Watermark (MZ corner) → clean master
    master = out_dir / f"{vid_id}_master.mp4"
    apply_watermark(captioned, master)
    _log(f"master: {master}")

    # 8. Per-platform variants
    yt_path = out_dir / f"{vid_id}_yt.mp4"
    shutil.copy(master, yt_path)  # YT = master (only MZ corner, no end card)

    tt_path = out_dir / f"{vid_id}_tt.mp4"
    ec_tt = work / "endcard_tt.mp4"
    build_end_card("FOLLOW\n@MINUTEZERO\nON YT", ec_tt)
    append_end_card(master, ec_tt, tt_path)

    ig_path = out_dir / f"{vid_id}_ig.mp4"
    ec_ig = work / "endcard_ig.mp4"
    build_end_card("MORE ON\nYOUTUBE", ec_ig)
    append_end_card(master, ec_ig, ig_path)

    # 9. Thumbnail
    thumb_path = out_dir / f"{vid_id}_thumb.jpg"
    render_thumbnail(thumb_text, clip_paths[0], thumb_path)

    # 10. Cleanup work dir (keep if debugging)
    if os.environ.get("MZ_KEEP_WORK") != "1":
        shutil.rmtree(work, ignore_errors=True)

    # 11. Commit clip IDs to dedup ledger — only after the full render
    #     succeeded, so a mid-render crash doesn't poison the ledger with
    #     IDs from clips that never actually shipped.
    save_used_clip_ids(used_ids | newly_used)
    _log(f"ledger updated: +{len(newly_used)} new IDs (total {len(used_ids | newly_used)})")

    return {
        "id":             vid_id,
        "master_path":    str(master),
        "yt_path":        str(yt_path),
        "tt_path":        str(tt_path),
        "ig_path":        str(ig_path),
        "thumb_path":     str(thumb_path),
        "narration_path": str(narration),
    }


# ─── CLI entry point ────────────────────────────────────────────────────────

def _cli() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Render a Minute Zero Short from a v3 script JSON.")
    p.add_argument("--script-json", required=True, help="Path to v3 JSON file.")
    p.add_argument("--out-dir", required=True, help="Output directory.")
    args = p.parse_args()

    script_data = json.loads(Path(args.script_json).read_text())
    result = render_video(script_data, args.out_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
