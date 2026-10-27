#!/usr/bin/env python3
"""Shared helpers for the playthrough-video-review scripts: find ffmpeg, parse and format
timecodes, read a video's duration. Stdlib only.

ffmpeg is looked up in this order, because the usual Windows failure is "no ffmpeg on PATH"
while a Python package already ships one:
  1. $FFMPEG (an explicit path wins)
  2. `ffmpeg` on PATH
  3. imageio_ffmpeg.get_ffmpeg_exe()   (pip install imageio-ffmpeg)
"""
import os
import re
import shutil
import subprocess
import sys


def find_ffmpeg():
    exe = os.environ.get("FFMPEG")
    if exe and os.path.isfile(exe):
        return exe
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    sys.exit("FAIL: no ffmpeg. Set $FFMPEG, put ffmpeg on PATH, or `pip install imageio-ffmpeg`.")


def run_ffmpeg(args, quiet=True):
    """Run ffmpeg with `args`; return (returncode, stderr)."""
    cmd = [find_ffmpeg(), "-hide_banner", "-y"] + (["-loglevel", "error"] if quiet else []) + list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stderr


def duration(video):
    """Seconds, read from ffmpeg's own banner (no ffprobe needed; imageio_ffmpeg ships none)."""
    p = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", video],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def parse_tc(text):
    """'83.5', '1:23.5', '0:01:23.5' -> 83.5 seconds."""
    parts = str(text).strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"bad timecode {text!r}")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    if total < 0:
        raise ValueError(f"negative timecode {text!r}")
    return total


def fmt_tc(seconds, sep=":"):
    """83.5 -> '01:23.5' (sep='m' gives a filename-safe '01m23.5')."""
    m, s = divmod(max(0.0, seconds), 60)
    return f"{int(m):02d}{sep}{s:04.1f}"
