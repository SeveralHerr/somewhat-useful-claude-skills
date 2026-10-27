#!/usr/bin/env python3
"""Two-pass encode of a recorded run to a share-size MP4 (default cap 15 MB).

Why a script: the bitrate has to be computed from the duration and the size cap, minus the
audio, and a single-pass CRF encode of a busy horde scene lands at 3x the cap. Two-pass at a
computed target is the only reliable way to hit "fits in the upload box" on the first try.

    python encode_share.py raw.avi --out run.mp4                  # 15 MB, 1024 wide, 30 fps
    python encode_share.py raw.mp4 --out run.mp4 --size-mb 8 --width 854 --no-audio
    python encode_share.py raw.mp4 --out run.mp4 --speed 4        # time-lapse a long run

Output is H.264 yuv420p + AAC with +faststart, so it plays in a browser <video> immediately.
Exits 1 when the input cannot be read or the result overshoots the cap by more than 10%.
Requires ffmpeg only (see _media.py).
"""
import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _media import duration, run_ffmpeg  # noqa: E402

MIN_VIDEO_KBPS = 100


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size-mb", type=float, default=15.0)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--audio-kbps", type=int, default=64)
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0, help="time-lapse factor (>1 = faster; drops audio)")
    a = ap.parse_args(argv)

    if not os.path.isfile(a.src):
        print(f"FAIL: {a.src} does not exist")
        return 1
    dur = duration(a.src)
    if not dur:
        print(f"FAIL: could not read a duration from {a.src}")
        return 1
    out_dur = dur / a.speed
    no_audio = a.no_audio or a.speed != 1.0
    audio_kbps = 0 if no_audio else a.audio_kbps
    # 0.97: container overhead. kbps = kilobits/s; MB here is MiB to match file managers.
    total_kbps = a.size_mb * 8 * 1024 * 1024 / 1000 / out_dur * 0.97
    video_kbps = int(total_kbps - audio_kbps)
    if video_kbps < MIN_VIDEO_KBPS:
        print(f"WARN: {a.size_mb} MB over {out_dur:.0f}s leaves {video_kbps} kbps; clamping to "
              f"{MIN_VIDEO_KBPS} (try --speed or a smaller --width)")
        video_kbps = MIN_VIDEO_KBPS

    vf = f"scale={a.width}:-2,fps={a.fps}"
    if a.speed != 1.0:
        vf = f"setpts=PTS/{a.speed}," + vf
    common = ["-i", a.src, "-vf", vf, "-c:v", "libx264", "-b:v", f"{video_kbps}k",
              "-pix_fmt", "yuv420p", "-preset", "medium"]
    with tempfile.TemporaryDirectory() as td:
        log = os.path.join(td, "pass")
        rc, err = run_ffmpeg(common + ["-pass", "1", "-passlogfile", log, "-an", "-f", "mp4", os.devnull])
        if rc != 0:
            print(f"FAIL: pass 1: {err.strip()[-400:]}")
            return 1
        audio = ["-an"] if no_audio else ["-c:a", "aac", "-b:a", f"{audio_kbps}k"]
        rc, err = run_ffmpeg(common + ["-pass", "2", "-passlogfile", log] + audio +
                             ["-movflags", "+faststart", a.out])
        if rc != 0:
            print(f"FAIL: pass 2: {err.strip()[-400:]}")
            return 1
    size_mb = os.path.getsize(a.out) / 1024 / 1024
    print(f"{a.out}: {size_mb:.2f} MB, {out_dur:.1f}s, video {video_kbps} kbps, audio {audio_kbps} kbps")
    if size_mb > a.size_mb * 1.10 and video_kbps > MIN_VIDEO_KBPS:
        print(f"FAIL: {size_mb:.2f} MB overshoots the {a.size_mb} MB cap")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
