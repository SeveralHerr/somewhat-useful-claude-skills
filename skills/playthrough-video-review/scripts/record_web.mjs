#!/usr/bin/env node
// TODO(port): game-agnostic web-game recorder — headless Chrome over CDP with a VIRTUAL CLOCK.
//
// Not written yet. The working version is being built in another project
// (hot-sauce-game-review: game/tools/record.js) and will be ported here, minus anything
// game-specific. Until then, SKILL.md section 2b describes the technique well enough to
// write one by hand. The contract this file will keep:
//
//   node record_web.mjs <url> --out raw.mp4 [--seconds 120] [--fps 30] [--size 1280x720]
//                       [--speed 1] [--events events.jsonl] [--chrome <path>]
//
//   1. Launch Chrome headless with --remote-debugging-port, open <url>.
//   2. Before any page script runs (Page.addScriptToEvaluateOnNewDocument), replace
//      requestAnimationFrame, performance.now and Date.now with a virtual clock that only
//      advances when the recorder says so.
//   3. Per output frame: advance the clock by 1000/fps ms, flush the queued rAF callbacks,
//      Page.captureScreenshot, pipe the PNG bytes into `ffmpeg -f image2pipe -r <fps> -i -`.
//      Raster speed then has no effect on the footage: a slow frame just takes longer to
//      capture, and the video still plays at exactly <fps>.
//   4. --speed N advances N frames of game time per captured frame (time-lapse).
//   5. Anything the page pushes to window.__events ({t, kind, ...}) is written to
//      --events with t in VIDEO seconds, so findings cite the same timecode the sheets show.
//
// It must exit non-zero, without writing a video, when ffmpeg or Chrome is missing.
console.error("record_web.mjs is a stub: see the TODO at the top of this file and SKILL.md section 2b.");
process.exit(2);
