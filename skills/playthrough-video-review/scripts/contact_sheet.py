#!/usr/bin/env python3
"""Turn a playthrough video (or a directory of frames) into timecode-labelled contact sheets.

Why a script: "extract 1 frame per 2 s, tile 4x4, label each with its time" is the same
mechanical step every review, and the label is the part that must be exact — every finding
on the approval page seeks to a timecode read off these sheets. A hand-rolled tile loop that
drops the label, or labels by index instead of time, sends the reviewer to the wrong fight.

    python contact_sheet.py run.mp4 --every 2 --grid 4x4 --out sheets/
    python contact_sheet.py frames/ --every 0.5 --out sheets/    # frame dir: frame i = i*every s
    python contact_sheet.py run.mp4 --start 60 --end 120 --every 1

Writes sheet_001.png, sheet_002.png ... and index.json ({sheet: [[cell, seconds], ...]}).
Prints one line per sheet with its time range. Exits 1 when no frame was produced.
Requires Pillow and ffmpeg (see _media.py for how ffmpeg is found).
"""
import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _media import fmt_tc, parse_tc, run_ffmpeg  # noqa: E402

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("FAIL: contact_sheet.py needs Pillow (pip install pillow)")

IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
LABEL_H = 18


def frames_from_video(video, every, width, start, end, work):
    vf = f"fps=1/{every},scale={width}:-2"
    args = ["-ss", str(start), "-i", video]
    if end is not None:
        args += ["-t", str(end - start)]
    args += ["-vf", vf, os.path.join(work, "f_%06d.png")]
    rc, err = run_ffmpeg(args)
    files = sorted(f for f in os.listdir(work) if f.startswith("f_"))
    if rc != 0 and not files:
        print(f"FAIL: ffmpeg could not read {video}: {err.strip()[-300:]}")
    # fps=1/K emits output frame n at pts n*K (nearest source frame), so the label is exact
    # to half a source frame — the same contract extract_moment.py relies on.
    return [(os.path.join(work, f), start + i * every) for i, f in enumerate(files)]


def frames_from_dir(folder, every, start):
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(IMG_EXT))
    return [(os.path.join(folder, f), start + i * every) for i, f in enumerate(files)]


def build_sheets(frames, cols, rows, width, out):
    os.makedirs(out, exist_ok=True)
    font = ImageFont.load_default()
    per = cols * rows
    index = {}
    for s in range(0, len(frames), per):
        chunk = frames[s:s + per]
        thumbs = []
        for path, t in chunk:
            im = Image.open(path).convert("RGB")
            if im.width != width:
                im = im.resize((width, max(1, round(im.height * width / im.width))))
            thumbs.append((im, t))
        th = max(im.height for im, _ in thumbs)
        sheet = Image.new("RGB", (cols * width, rows * (th + LABEL_H)), (16, 16, 16))
        draw = ImageDraw.Draw(sheet)
        for i, (im, t) in enumerate(thumbs):
            x, y = (i % cols) * width, (i // cols) * (th + LABEL_H)
            sheet.paste(im, (x, y + LABEL_H))
            draw.text((x + 4, y + 3), f"{fmt_tc(t)}  #{s + i}", fill=(255, 230, 80), font=font)
        name = f"sheet_{s // per + 1:03d}.png"
        sheet.save(os.path.join(out, name))
        index[name] = [[i, round(t, 3)] for i, (_, t) in enumerate(thumbs)]
        print(f"{os.path.join(out, name)}  {fmt_tc(chunk[0][1])} - {fmt_tc(chunk[-1][1])}  ({len(chunk)} frames)")
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, indent=1)
    return index


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src", help="video file or directory of frames")
    ap.add_argument("--every", type=float, default=2.0, help="seconds between frames (default 2)")
    ap.add_argument("--grid", default="4x4", help="COLSxROWS per sheet (default 4x4)")
    ap.add_argument("--width", type=int, default=320, help="thumbnail width px (default 320)")
    ap.add_argument("--start", default="0", help="timecode to start at")
    ap.add_argument("--end", default=None, help="timecode to stop at (video only)")
    ap.add_argument("--out", default="sheets", help="output directory")
    a = ap.parse_args(argv)

    cols, rows = (int(v) for v in a.grid.lower().split("x"))
    if a.every <= 0 or cols < 1 or rows < 1:
        ap.error("--every must be > 0 and --grid at least 1x1")
    start = parse_tc(a.start)
    end = parse_tc(a.end) if a.end else None

    with tempfile.TemporaryDirectory() as work:
        if os.path.isdir(a.src):
            frames = frames_from_dir(a.src, a.every, start)
        elif os.path.isfile(a.src):
            frames = frames_from_video(a.src, a.every, a.width, start, end, work)
        else:
            print(f"FAIL: {a.src} does not exist")
            return 1
        if not frames:
            print("FAIL: no frames produced (empty dir, unreadable video, or --start past the end)")
            return 1
        build_sheets(frames, cols, rows, a.width, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
