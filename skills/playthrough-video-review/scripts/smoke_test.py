#!/usr/bin/env python3
"""Prove contact_sheet.py, extract_moment.py and encode_share.py both work and FAIL.

Builds a synthetic 10 s video in which every second is a different solid colour, so the
right frame for any timecode is known exactly. Then asserts that each contact-sheet cell
shows the colour of the second its label claims, that extract_moment returns the colour at
its --at, and that the share encode lands under its cap. The colour check is itself shown
to fail on a labelling off by one second — otherwise "every cell matched" could be a check
that matches anything.

    python scripts/smoke_test.py      # SMOKE: ALL PASS, exit 0 — or the failing cases, exit 1

Requires Pillow and ffmpeg (FFMPEG env / PATH / imageio_ffmpeg).
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _media import run_ffmpeg  # noqa: E402

from PIL import Image  # noqa: E402

COLOURS = [(220, 30, 30), (30, 200, 30), (30, 30, 220), (230, 230, 30), (30, 220, 220),
           (220, 30, 220), (240, 240, 240), (20, 20, 20), (240, 130, 20), (130, 20, 240)]
FPS = 10
TOL = 45  # yuv420p + x264 shift a flat colour by well under this; neighbours differ by >150


def close(a, b):
    return all(abs(x - y) <= TOL for x, y in zip(a, b))


def run(script, *args):
    p = subprocess.run([sys.executable, os.path.join(HERE, script), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def make_video(td):
    frames = os.path.join(td, "src")
    os.makedirs(frames)
    for i in range(len(COLOURS) * FPS):
        Image.new("RGB", (320, 240), COLOURS[i // FPS]).save(os.path.join(frames, f"{i:04d}.png"))
    video = os.path.join(td, "run.mp4")
    rc, err = run_ffmpeg(["-framerate", str(FPS), "-i", os.path.join(frames, "%04d.png"),
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", str(FPS), video])
    if rc:
        sys.exit(f"SMOKE: could not build the test video: {err}")
    return video


def cell_mismatches(sheet_dir, grid_cols, grid_rows, width, shift=0):
    """Cells whose centre colour is not COLOURS[label second + shift]."""
    index = json.load(open(os.path.join(sheet_dir, "index.json"), encoding="utf-8"))
    bad = []
    for name, cells in index.items():
        im = Image.open(os.path.join(sheet_dir, name)).convert("RGB")
        th = im.height // grid_rows  # a sheet keeps its full grid height even when part-filled
        for cell, t in cells:
            x = (cell % grid_cols) * width + width // 2
            y = (cell // grid_cols) * th + th // 2 + 9
            want_i = int(t + 0.001) + shift
            want = COLOURS[want_i] if 0 <= want_i < len(COLOURS) else (-999, -999, -999)
            if not close(im.getpixel((x, y)), want):
                bad.append((name, cell, t))
    return bad


def main():
    fails = []

    def check(name, cond, out=""):
        print(("  PASS  " if cond else "  FAIL  ") + name)
        if not cond:
            fails.append((name, out))

    with tempfile.TemporaryDirectory() as td:
        video = make_video(td)

        sheets = os.path.join(td, "sheets")
        rc, out = run("contact_sheet.py", video, "--every", 1, "--grid", "3x2", "--width", 160, "--out", sheets)
        check("contact_sheet exits 0 on a real video", rc == 0, out)
        index = json.load(open(os.path.join(sheets, "index.json"), encoding="utf-8")) if rc == 0 else {}
        times = [t for cells in index.values() for _, t in cells]
        check("10 s at --every 1 gives 10 frames over 2 sheets of 3x2",
              len(index) == 2 and len(times) == 10, out)
        check("labels are seconds 0..9 in order", times == [float(i) for i in range(10)], str(times))
        bad = cell_mismatches(sheets, 3, 2, 160) if index else ["no index"]
        check("every cell shows the colour of the second its label claims", not bad, str(bad))
        shifted = cell_mismatches(sheets, 3, 2, 160, shift=1) if index else []
        check("...and that colour check FAILS on labels off by one second", len(shifted) == len(times), str(shifted))

        sub = os.path.join(td, "sub")
        rc, out = run("contact_sheet.py", video, "--start", "0:04", "--end", "0:07", "--every", 1,
                      "--grid", "4x4", "--width", 160, "--out", sub)
        sub_t = [t for c in json.load(open(os.path.join(sub, "index.json"))).values() for _, t in c] if rc == 0 else []
        check("--start/--end labels absolute video time (4,5,6)", sub_t[:3] == [4.0, 5.0, 6.0], str(sub_t))
        check("--start window cells match their colours", rc == 0 and not cell_mismatches(sub, 4, 4, 160), out)

        rc, out = run("contact_sheet.py", os.path.join(td, "src"), "--every", 0.1, "--grid", "10x10",
                      "--width", 32, "--out", os.path.join(td, "dirsheets"))
        check("frame-directory mode: 100 frames -> 1 sheet", rc == 0 and "100 frames" in out, out)

        rc, out = run("contact_sheet.py", os.path.join(td, "missing.mp4"), "--out", os.path.join(td, "x"))
        check("contact_sheet on a missing file exits 1", rc == 1 and "FAIL" in out, out)
        rc, out = run("contact_sheet.py", video, "--start", 60, "--out", os.path.join(td, "y"))
        check("contact_sheet with --start past the end exits 1", rc == 1, out)

        mom = os.path.join(td, "moment")
        rc, out = run("extract_moment.py", video, "--at", "0:05.5", "--window", 0, "--out", mom)
        files = sorted(os.listdir(mom)) if os.path.isdir(mom) else []
        check("extract_moment --window 0 writes exactly one frame", rc == 0 and len(files) == 1, out)
        if files:
            px = Image.open(os.path.join(mom, files[0])).convert("RGB").getpixel((160, 120))
            check("that frame is the colour of second 5 (full size 320x240)",
                  close(px, COLOURS[5]) and Image.open(os.path.join(mom, files[0])).size == (320, 240), str(px))
        mom2 = os.path.join(td, "moment2")
        rc, out = run("extract_moment.py", video, "--at", 3, "--window", 0.5, "--fps", 10, "--out", mom2)
        n = len(os.listdir(mom2)) if os.path.isdir(mom2) else 0
        check("extract_moment window 0.5 at 10 fps gives ~10 frames named by timecode",
              rc == 0 and 9 <= n <= 11 and "moment_00m02.5.png" in os.listdir(mom2), out)
        rc, out = run("extract_moment.py", video, "--at", "1:00", "--out", os.path.join(td, "z"))
        check("extract_moment past the end exits 1", rc == 1 and "past the end" in out, out)

        share = os.path.join(td, "share.mp4")
        rc, out = run("encode_share.py", video, "--out", share, "--size-mb", 0.1, "--width", 320, "--fps", 10)
        check("encode_share exits 0 and writes the file", rc == 0 and os.path.isfile(share), out)
        if os.path.isfile(share):
            check("share file is under its 0.1 MB cap (+10%)", os.path.getsize(share) <= 0.11 * 1024 * 1024,
                  str(os.path.getsize(share)))
        rc, out = run("encode_share.py", video, "--out", os.path.join(td, "lapse.mp4"), "--speed", 5,
                      "--size-mb", 0.1, "--width", 320, "--fps", 10)
        check("encode_share --speed 5 reports a 2 s time-lapse", rc == 0 and ", 2.0s," in out, out)
        rc, out = run("encode_share.py", os.path.join(td, "missing.mp4"), "--out", share)
        check("encode_share on a missing file exits 1", rc == 1, out)

    if fails:
        print(f"SMOKE: {len(fails)} FAILED; first: {fails[0][0]}")
        print(fails[0][1][-1500:])
        return 1
    print("SMOKE: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
