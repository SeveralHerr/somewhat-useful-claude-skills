#!/usr/bin/env python3
"""Prove record_web.mjs records on its VIRTUAL clock, and that this check can fail.

A synthetic canvas page paints a solid colour chosen by floor(performance.now() / 1000) and
burns CPU every frame, so headless Chrome rasters slower than real time. If the recorder's
clock is honest, the frame at video second t shows the colour for game second t*speed no
matter how slow the raster was. Then the same checks run against a copy of the recorder
whose clock advances at the wrong rate, and must go red.

    python scripts/smoke_test_record.py   # RECORD: ALL PASS / RECORD: N FAILED, exit 0/1

Needs Node >= 22, Chrome/Chromium/Edge (or $CHROME), ffmpeg, Pillow. With no Node or
Chrome it prints RECORD: OK - SKIPPED and says why, rather than pretending it tested.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from smoke_test import COLOURS, close  # noqa: E402  (same palette and tolerance)

from PIL import Image  # noqa: E402

PAGE = """<!doctype html><meta charset=utf-8><title>loading</title>
<style>html,body{margin:0;background:#000}canvas{display:block}</style>
<canvas id=c width=320 height=240></canvas>
<script>
const C = %s, g = document.getElementById('c').getContext('2d');
window.__ev = []; let last = -1;
function frame() {
  const now = performance.now(), sec = Math.floor(now / 1000);
  let x = 0; for (let i = 0; i < 3e6; i++) x += Math.sqrt(i);   // slow raster on purpose
  window.__burn = x;
  if (sec !== last) { window.__ev.push({type: 'tick', sec}); last = sec; }
  const [r, gg, b] = C[sec %% C.length];
  g.fillStyle = `rgb(${r},${gg},${b})`; g.fillRect(0, 0, 320, 240);
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
document.title = 'ready';
</script>""" % json.dumps(COLOURS)

PROBE = ("({scene: performance.now() >= 2000 ? 'late' : 'early', game: performance.now(),"
         " events: window.__ev.splice(0)})")


def node_ok():
    node = shutil.which("node")
    if not node:
        return None, "node not on PATH"
    v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)", v)
    if not m or int(m.group(1)) < 22:
        return None, f"node {v} < 22 (needs the global WebSocket)"
    return node, ""


def chrome_ok(node, recorder):
    url = pathlib.Path(recorder).resolve().as_uri()  # ESM import() needs a file URL, not C:/...
    code = (f"import('{url}').then(m => {{ const c = m.findChrome(); "
            "console.log(c || ''); process.exit(c ? 0 : 1); })")
    p = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
    return p.returncode == 0


def record(node, recorder, td, name, *extra, env=None):
    out, ev = os.path.join(td, f"{name}.mp4"), os.path.join(td, f"{name}.jsonl")
    cmd = [node, recorder, "--url", os.path.join(td, "page.html"), "--out", out, "--events", ev,
           "--fps", "10", "--width", "320", "--height", "240", "--ready-js", 'document.title === "ready"',
           "--probe-js", PROBE, "--seconds", "20", *map(str, extra)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, **(env or {})})
    events = []
    if os.path.isfile(ev):
        events = [json.loads(ln) for ln in open(ev, encoding="utf-8") if ln.strip()]
    return p.returncode, p.stdout + p.stderr, out, events


def colour_at(video, t, td):
    d = tempfile.mkdtemp(dir=td)
    p = subprocess.run([sys.executable, os.path.join(HERE, "extract_moment.py"), video, "--at", str(t),
                        "--window", "0", "--out", d], capture_output=True, text=True)
    files = [f for f in os.listdir(d) if f.endswith(".png")]
    if p.returncode or not files:
        return None
    return Image.open(os.path.join(d, files[0])).convert("RGB").getpixel((160, 120))


def clock_checks(node, recorder, td, check):
    """Every assertion that depends on the clock being right. Returns how many failed."""
    before = len(FAILS)
    rc, out, mp4, ev = record(node, recorder, td, "s1", "--speed", 1, "--end-js", "s && s.game >= 3000", "--tail", 0.5)
    check("speed 1 run exits 0 and writes the MP4", rc == 0 and os.path.isfile(mp4), out)
    if rc == 0:
        for t, sec in [(0.55, 0), (1.55, 1), (2.55, 2)]:
            px = colour_at(mp4, t, td)
            check(f"speed 1: video {t}s shows game second {sec}", px is not None and close(px, COLOURS[sec]), str(px))
        ch = [e for e in ev if e.get("type") == "change" and e.get("field") == "scene" and e.get("to") == "late"]
        check("probe change early->late logged at video 1.9s (game 2000 ms)", len(ch) == 1 and ch[0]["t"] == 1.9, str(ch))
        ticks = [e["t"] for e in ev if e.get("type") == "tick"]
        check("page events stamped in video time (ticks at 0, 0.9, 1.9, 2.9)", ticks == [0, 0.9, 1.9, 2.9], str(ticks))
        check("--end-js + --tail 0.5 stops at 35 frames", "35 frames" in out, out)
    rc, out, mp4, ev = record(node, recorder, td, "s2", "--speed", 2, "--end-js", "s && s.game >= 3000", "--tail", 0.5)
    if rc == 0:
        for t, sec in [(0.75, 1), (1.25, 2)]:
            px = colour_at(mp4, t, td)
            check(f"speed 2: video {t}s shows game second {sec}", px is not None and close(px, COLOURS[sec]), str(px))
        check("speed 2 ends twice as soon (20 frames)", "20 frames" in out, out)
    else:
        check("speed 2 run exits 0", False, out)
    return len(FAILS) - before


FAILS = []


def main():
    rec = os.path.join(HERE, "record_web.mjs")
    node, why = node_ok()
    if node and not chrome_ok(node, rec):
        node, why = None, "no Chrome/Chromium/Edge found (set $CHROME)"
    if not node:
        print(f"RECORD: OK - SKIPPED, nothing was tested: {why}")
        return 0

    def check(name, cond, out=""):
        print(("  PASS  " if cond else "  FAIL  ") + name)
        if not cond:
            FAILS.append((name, out))

    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "page.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(PAGE)
        clock_checks(node, rec, td, check)

        rc, out, mp4, _ = record(node, rec, td, "nochrome", "--seconds", 1, env={"CHROME": os.path.join(td, "nope.exe")})
        check("CHROME pointing nowhere exits 1 and writes no video", rc == 1 and not os.path.isfile(mp4), out)
        p = subprocess.run([node, rec, "--url", os.path.join(td, "missing.html"), "--out", os.path.join(td, "m.mp4")],
                           capture_output=True, text=True)
        check("missing page exits 1", p.returncode == 1 and "missing page" in p.stderr, p.stderr)

        # Mutation: a recorder whose clock runs at half rate must fail the clock checks.
        bad = os.path.join(td, "record_web_bad.mjs")
        src = open(rec, encoding="utf-8").read()
        mutated = src.replace("advance(ms) { now += ms;", "advance(ms) { now += ms / 2;")
        check("mutation applied to the clock", mutated != src)
        open(bad, "w", encoding="utf-8", newline="\n").write(mutated)
        print("  -- the same checks against a half-rate clock (red is the point here):")
        red = []

        def expect_red(name, cond, out=""):
            print(("  red     " if not cond else "  stayed green  ") + name)
            if not cond:
                FAILS.append((name, out))  # clock_checks counts FAILS; removed again below
                red.append(name)
        caught = clock_checks(node, bad, td, expect_red)
        del FAILS[len(FAILS) - len(red):]
        check("half-rate clock is caught by the clock checks", caught >= 3, f"only {caught} check(s) went red")

    if FAILS:
        print(f"RECORD: {len(FAILS)} FAILED; first: {FAILS[0][0]}")
        print(FAILS[0][1][-1500:])
        return 1
    print("RECORD: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
