#!/usr/bin/env python3
"""
render_qc.py -- pre-upload quality gate for rendered videos.

WHY THIS EXISTS
---------------
Aug 23 2026: two Minute Zero Shorts shipped broken and burned real
distribution before anyone noticed.

  "The Tweet That Killed Vine"              470 views @  4% retention
  "The $10,000 Letter That Killed
   Western Union"                40s (vs a 76-104s norm) @ 16% retention

Nothing in the pipeline failed. The renders completed, the uploads
succeeded, YouTube pushed them to real viewers, and the videos were
unwatchable. Roughly 1 in 14 uploads was landing this way.

Every one of those is detectable from the file itself in under a second.

DESIGN NOTE -- two severities, deliberately
-------------------------------------------
This runs unattended. A gate that blocks good uploads is worse than no
gate at all, so the checks are split:

  FAIL  -- unambiguously broken. Blocks the upload.
           (no audio stream, silent audio, A/V drift, dead final frame,
            truncated file, duration outside what the platform accepts)

  WARN  -- suspicious but plausible. Uploads anyway, logs loudly.
           (duration outside the channel's normal band, very quiet audio)

Western Union at 40s would WARN, not FAIL -- a short video is odd, not
broken. Vine at 4% retention would have FAILed on its audio.

Set QC_STRICT=1 to promote every warning to a failure.
Set QC_DISABLE=1 to bypass the gate entirely (logs a loud banner).

USAGE
-----
    from render_qc import enforce, QCError

    try:
        enforce(video_path, channel="mz", kind="short")
    except QCError as e:
        print(e)
        sys.exit(1)

Or non-raising, if you want to decide yourself:

    report = qc_video(video_path, channel="mz", kind="short")
    print(report.summary())
    if not report.ok:
        ...

Standalone:
    python3 render_qc.py path/to/video.mp4 --channel mz --kind short
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------- thresholds

# Hard limits. Outside these the file is broken or unpostable -> FAIL.
HARD_DURATION = {
    "short": (20.0, 180.0),     # YouTube Shorts cap is 180s
    "long":  (240.0, 3600.0),
}

# Per-channel normal bands, measured from the Jul 26 - Aug 23 2026 export.
# Outside these -> WARN. Widen if a deliberate format change makes one noisy.
EXPECTED_DURATION = {
    ("tmf", "short"): (40.0, 100.0),
    ("bsg", "short"): (40.0, 110.0),
    ("mz",  "short"): (65.0, 115.0),
    ("tmf", "long"):  (420.0, 900.0),
    ("bsg", "long"):  (360.0, 900.0),
    ("mz",  "long"):  (420.0, 900.0),
}

MIN_BYTES = {"short": 2 * 1024 * 1024, "long": 5 * 1024 * 1024}

SILENT_PEAK_DBFS = -45.0    # max_volume at or below this = no usable audio
QUIET_MEAN_DBFS  = -35.0    # mean_volume below this = suspiciously quiet
MAX_AV_DRIFT_S   = 2.0      # audio/video duration mismatch
FLAT_FRAME_STDDEV = 3.0     # final-frame pixel stddev below this = solid colour

FFPROBE_TIMEOUT = 60
FFMPEG_TIMEOUT  = 120


class QCError(RuntimeError):
    """Raised by enforce() when a video fails the gate."""


class QCReport:
    def __init__(self, path: Path, channel: str, kind: str):
        self.path = Path(path)
        self.channel = channel
        self.kind = kind
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.skipped: list[str] = []
        self.info: dict = {}

    @property
    def ok(self) -> bool:
        return not self.failures

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def warn(self, msg: str) -> None:
        # QC_STRICT turns every warning into a hard failure.
        if os.getenv("QC_STRICT") == "1":
            self.failures.append(f"{msg}  [promoted by QC_STRICT]")
        else:
            self.warnings.append(msg)

    def skip(self, msg: str) -> None:
        self.skipped.append(msg)

    def summary(self) -> str:
        head = "PASS" if self.ok else "FAIL"
        lines = [f"[QC {head}] {self.path.name}  ({self.channel}/{self.kind})"]
        if self.info:
            bits = []
            for k in ("duration_s", "audio_duration_s", "size_mb",
                      "peak_dbfs", "mean_dbfs", "final_frame_stddev"):
                if k in self.info and self.info[k] is not None:
                    bits.append(f"{k}={self.info[k]}")
            if bits:
                lines.append("         " + "  ".join(bits))
        for f in self.failures:
            lines.append(f"  FAIL   {f}")
        for w in self.warnings:
            lines.append(f"  WARN   {w}")
        for s in self.skipped:
            lines.append(f"  skip   {s}")
        return "\n".join(lines)


# ------------------------------------------------------------------ helpers

def _ffprobe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, timeout=FFPROBE_TIMEOUT,
    )
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout or "{}")


def _volume_stats(path: Path) -> tuple[float | None, float | None]:
    """Return (mean_dBFS, peak_dBFS) via ffmpeg volumedetect. None if unreadable."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=FFMPEG_TIMEOUT,
    )
    blob = out.stderr or ""
    mean = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", blob)
    peak = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", blob)
    return (float(mean.group(1)) if mean else None,
            float(peak.group(1)) if peak else None)


def _final_frame_stddev(path: Path, duration: float) -> float | None:
    """
    Pixel stddev of a frame near the end. A solid black/white frame means the
    encode was cut short. Returns None if the check can't run (never fails
    the video on a tooling gap).
    """
    try:
        from PIL import Image, ImageStat  # noqa: WPS433
    except ImportError:
        return None

    seek = max(0.0, duration - 0.4)
    with tempfile.TemporaryDirectory() as td:
        frame = Path(td) / "final.png"
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-y",
             "-ss", f"{seek:.3f}", "-i", str(path),
             "-frames:v", "1", str(frame)],
            capture_output=True, text=True, timeout=FFMPEG_TIMEOUT,
        )
        if out.returncode != 0 or not frame.exists():
            return None
        with Image.open(frame) as im:
            stat = ImageStat.Stat(im.convert("L"))
            return round(stat.stddev[0], 2)


# --------------------------------------------------------------------- gate

def qc_video(path, channel: str, kind: str = "short") -> QCReport:
    """Inspect a rendered file and report what's wrong with it. Never raises."""
    channel = (channel or "").lower()
    kind = (kind or "short").lower()
    rep = QCReport(path, channel, kind)
    p = rep.path

    if os.getenv("QC_DISABLE") == "1":
        rep.skip("QC_DISABLE=1 -- gate bypassed entirely")
        return rep

    # --- file exists and isn't a stub -------------------------------------
    if not p.exists():
        rep.fail(f"file does not exist: {p}")
        return rep

    size = p.stat().st_size
    rep.info["size_mb"] = round(size / 1024 / 1024, 2)
    floor = MIN_BYTES.get(kind, MIN_BYTES["short"])
    if size < floor:
        rep.fail(
            f"file is {rep.info['size_mb']} MB, below the "
            f"{floor // 1024 // 1024} MB floor -- encode almost certainly failed"
        )
        return rep  # nothing below this point is meaningful

    # --- probe ------------------------------------------------------------
    try:
        meta = _ffprobe(p)
    except Exception as e:  # noqa: BLE001
        rep.fail(f"unreadable by ffprobe -- corrupt container? ({e})")
        return rep

    streams = meta.get("streams", [])
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    astreams = [s for s in streams if s.get("codec_type") == "audio"]

    if not vstreams:
        rep.fail("no video stream")
    if not astreams:
        rep.fail("no audio stream -- the video is silent")

    try:
        duration = float(meta.get("format", {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    rep.info["duration_s"] = round(duration, 2)

    if duration <= 0:
        rep.fail("container reports zero duration")
        return rep

    # --- duration: hard band FAILs, channel band WARNs --------------------
    hard_lo, hard_hi = HARD_DURATION.get(kind, HARD_DURATION["short"])
    if duration < hard_lo:
        rep.fail(f"duration {duration:.1f}s is below the {hard_lo:.0f}s hard floor "
                 f"-- render was truncated")
    elif duration > hard_hi:
        rep.fail(f"duration {duration:.1f}s exceeds the {hard_hi:.0f}s hard ceiling "
                 f"for a {kind}")
    else:
        band = EXPECTED_DURATION.get((channel, kind))
        if band and not (band[0] <= duration <= band[1]):
            rep.warn(
                f"duration {duration:.1f}s is outside {channel}'s normal "
                f"{band[0]:.0f}-{band[1]:.0f}s band -- check the script length"
            )

    # --- audio/video drift ------------------------------------------------
    if astreams:
        adur = astreams[0].get("duration")
        try:
            adur = float(adur) if adur is not None else None
        except (TypeError, ValueError):
            adur = None
        if adur is None:
            rep.skip("audio stream reports no duration -- drift check skipped")
        else:
            rep.info["audio_duration_s"] = round(adur, 2)
            drift = abs(adur - duration)
            if drift > MAX_AV_DRIFT_S:
                rep.fail(
                    f"audio is {adur:.1f}s but video is {duration:.1f}s "
                    f"({drift:.1f}s drift) -- narration and picture are out of sync"
                )

    # --- silent / quiet audio --------------------------------------------
    if astreams:
        try:
            mean_db, peak_db = _volume_stats(p)
        except Exception as e:  # noqa: BLE001
            mean_db = peak_db = None
            rep.skip(f"volume analysis failed ({e}) -- loudness check skipped")
        rep.info["mean_dbfs"] = mean_db
        rep.info["peak_dbfs"] = peak_db
        if peak_db is None:
            rep.skip("could not read peak volume -- silence check skipped")
        elif peak_db <= SILENT_PEAK_DBFS:
            rep.fail(
                f"audio peaks at {peak_db} dBFS -- effectively silent. "
                f"TTS produced no sound, or the mux dropped the narration"
            )
        elif mean_db is not None and mean_db < QUIET_MEAN_DBFS:
            rep.warn(f"audio averages {mean_db} dBFS -- unusually quiet")

    # --- dead final frame -------------------------------------------------
    if vstreams:
        try:
            stddev = _final_frame_stddev(p, duration)
        except Exception as e:  # noqa: BLE001
            stddev = None
            rep.skip(f"final-frame check failed ({e})")
        rep.info["final_frame_stddev"] = stddev
        if stddev is None:
            rep.skip("final-frame check unavailable (Pillow missing or seek failed)")
        elif stddev < FLAT_FRAME_STDDEV:
            rep.fail(
                f"final frame is a solid colour (stddev {stddev}) "
                f"-- the encode was cut short"
            )

    return rep


def enforce(path, channel: str, kind: str = "short", *, verbose: bool = True) -> QCReport:
    """
    Run the gate and raise QCError if the file is broken.
    Drop this in immediately before any upload call.
    """
    rep = qc_video(path, channel, kind)
    if verbose:
        print(rep.summary(), flush=True)
    if not rep.ok:
        raise QCError(
            f"Refusing to upload {rep.path.name} -- "
            f"{len(rep.failures)} QC failure(s):\n  - "
            + "\n  - ".join(rep.failures)
        )
    return rep


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Pre-upload video quality gate.")
    ap.add_argument("video", help="path to the rendered file")
    ap.add_argument("--channel", default="", help="tmf | bsg | mz")
    ap.add_argument("--kind", default="short", choices=["short", "long"])
    args = ap.parse_args()

    rep = qc_video(args.video, args.channel, args.kind)
    print(rep.summary())
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
