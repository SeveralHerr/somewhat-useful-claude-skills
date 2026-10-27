#!/usr/bin/env python3
"""Pull full-size frames around one timecode, to confirm a finding before calling it a bug.

Why a script: contact-sheet thumbnails lie in two repeatable ways — adjacent cells fake
"doubled" art, and similar rooms/fights get confused for each other. The fix is always the
same: re-extract that moment at native resolution, a few frames either side, and look again.

    python extract_moment.py run.mp4 --at 1:23.5                   # 1 s either side at 10 fps
    python extract_moment.py run.mp4 --at 83.5 --window 0.5 --fps 30 --out moment/

Writes moment_<mm>m<ss.s>.png per frame (named by its own timecode). Exits 1 when the
timecode is past the end of the video or nothing could be extracted.
Requires ffmpeg only (see _media.py).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _media import duration, fmt_tc, parse_tc, run_ffmpeg  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("video")
    ap.add_argument("--at", required=True, help="timecode: 83.5, 1:23.5 or 0:01:23.5")
    ap.add_argument("--window", type=float, default=1.0, help="seconds either side (default 1; 0 = one frame)")
    ap.add_argument("--fps", type=float, default=10.0, help="frames per second inside the window (default 10)")
    ap.add_argument("--out", default="moment", help="output directory")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.video):
        print(f"FAIL: {a.video} does not exist")
        return 1
    at = parse_tc(a.at)
    dur = duration(a.video)
    if dur is not None and at > dur:
        print(f"FAIL: --at {fmt_tc(at)} is past the end of the video ({fmt_tc(dur)})")
        return 1
    start = max(0.0, at - a.window)
    os.makedirs(a.out, exist_ok=True)
    tmp = os.path.join(a.out, "_raw_%05d.png")
    if a.window <= 0:
        args = ["-ss", str(at), "-i", a.video, "-frames:v", "1", tmp]
        step = 0.0
    else:
        args = ["-ss", str(start), "-i", a.video, "-t", str(at + a.window - start),
                "-vf", f"fps={a.fps}", tmp]
        step = 1.0 / a.fps
    rc, err = run_ffmpeg(args)
    raw = sorted(f for f in os.listdir(a.out) if f.startswith("_raw_"))
    if not raw:
        print(f"FAIL: nothing extracted at {fmt_tc(at)}: {err.strip()[-300:]}")
        return 1
    base = at if a.window <= 0 else start
    for i, f in enumerate(raw):
        dst = os.path.join(a.out, f"moment_{fmt_tc(base + i * step, 'm')}.png")
        os.replace(os.path.join(a.out, f), dst)
        print(dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
