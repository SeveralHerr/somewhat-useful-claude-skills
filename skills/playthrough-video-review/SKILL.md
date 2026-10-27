---
name: playthrough-video-review
description: Record a scripted, human-like 100% playthrough of the user's game as a downloadable MP4, watch it frame by frame for presentation, balance, fun, juice, bug and build-diversity opportunities, publish an approval page (video + chapters + one card per finding with Approve/Later/Reject), then fan out the approved fixes and re-record to compare. Works for Godot (movie mode) and for web/canvas/JS games (headless Chrome with a virtual clock, so the footage is smooth however slowly the page rasters). Use whenever the user says "record a playthrough", "speedrun/100% run", "make a video of my game", "capture gameplay footage", "record the web build", "watch the run and suggest improvements", "playtest review", "review the footage", "contact sheet of the run", "find juice/balance/presentation opportunities", "what would make this more fun", "is any build broken/overpowered", "tier list the builds/weapons/synergies", "are some upgrades dead", "balance pass on the roguelite/horde game", "time-lapse of a long run", or wants before/after gameplay video of a fix — even if they only ask for the video, only for suggestions, or only for a balance check. Needs a bot/autoplay harness or the ability to build one.
---

# Playthrough video review

Loop: **catalogue → scripted run → record → watch → approval page → implement approved → round 2.**
Skip the catalogue and the run misses secrets; skip the page and implementation guesses at
what the user wanted. Every finding cites a video timecode, so the clock is the spine.

## Gotchas first

- **Wall-clock recording of a web game stutters and lies.** A screen grab of a canvas that
  rasters at 20 fps under capture gives a 20 fps video *and* a different run (physics
  stepped by real time). Record on a virtual clock (§2b): footage is smooth and the run
  is the one the headless sim predicted.
- **Godot `time_scale = 0` (hitstop) can hang a fixed-clock recorder** → use 0.05.
- **Recording crawls** → check its log for per-frame warning spam first.
- **Wall-clock effects make the recorded run diverge from headless** → trust the recorded
  run's own event log, not the headless report.
- **Contact sheets lie twice:** adjacent thumbnails fake "doubled" art, and similar rooms or
  fights get confused. Re-extract full size (`extract_moment.py`) before calling a bug.
- **Balance read off one run is an anecdote.** A build that wrecked in the video may assemble
  in 3% of runs. Balance claims come from the sweep (§4), the video only shows the feel.
- **Presentation changes flip balance** (banner timing, callouts shift fight length) → tune last.
- Keep bot runs off the player's real save (scratch profile / save path).

## 1. Catalogue and script the run

- Fan out an Explore agent over scenes/scripts: pickups, power-ups, secrets, collectibles,
  interactables, unlocks, score rules, level flow, and for roguelites every weapon, upgrade,
  fusion/synergy and its unlock condition.
- Drive the REAL game with real input events through the autoplay harness — calling inner
  methods skips overlays, signals and sequencing a player would see.
- Route out of its way for every catalogued item; script what the bot can't see (interact
  presses, door timing) as explicit waypoints.
- Sweep seeds headless first; pick one that wins AND collects everything. Prefer mortal —
  god mode hides soft-locks. Pin the route as a CI scenario asserting every secret is reachable.
- Parallel agents: each writes scratch output under its own prefixed dir.

## 2. Record

### 2a. Godot / native

`godot --write-movie out.avi --fixed-fps 60` (windowed, audio on) — the engine already steps a
fixed clock. Unity: Recorder package with a fixed frame rate. Then `encode_share.py`.

### 2b. Web / canvas / JS — headless Chrome, virtual clock

`<skill dir>/scripts/record_web.mjs` (stub until ported — its header holds the contract). The technique:

1. Launch Chrome headless with `--remote-debugging-port`; talk CDP over its WebSocket.
2. `Page.addScriptToEvaluateOnNewDocument` installs a fake clock *before the game's code
   runs*: `requestAnimationFrame` queues callbacks, `performance.now()`/`Date.now()` return
   virtual time that moves only when told to. `Emulation.setVirtualTimePolicy` alone does
   not cover rAF in every Chrome; overriding the three functions does.
3. Per frame: advance virtual time `1000/fps` ms, run the queued rAF callbacks, then
   `Page.captureScreenshot` and pipe the PNG to `ffmpeg -f image2pipe -framerate <fps> -i -`.
   A slow raster only makes the capture slower; the video still plays at exactly `fps`.
4. **Time-lapse**: step N game frames per captured frame for long runs (a 40 min horde run
   at 4x is a watchable 10 min), or record 1x and `encode_share.py --speed 4`.
5. **Event log in video time**: the game (or an injected hook) pushes `{t, kind, ...}` to
   `window.__events`; the recorder stamps each with the *video* second it landed in and
   writes JSONL. Damage taken, heals, level-ups, picks, deaths, boss spawns — findings cite
   these timecodes and the chapter list is built from them.

Seed `Math.random` too (inject a seeded PRNG) or the recorded run is not the swept run.

### 2c. Share encode

```bash
python <skill dir>/scripts/encode_share.py raw.mp4 --out video.mp4          # 2-pass, <=15 MB
python <skill dir>/scripts/encode_share.py raw.mp4 --out video.mp4 --speed 4 --size-mb 8
```

H.264 yuv420p + AAC + faststart (plays in a browser `<video>` at once). ffmpeg comes from
`$FFMPEG`, PATH, or `pip install imageio-ffmpeg`. Exits 1 if it overshoots the cap by >10%.

## 3. Watch the footage

```bash
python <skill dir>/scripts/contact_sheet.py video.mp4 --every 2 --grid 4x4 --out sheets/
python <skill dir>/scripts/extract_moment.py video.mp4 --at 6:51.5 --window 1 --out moment/
```

Read every sheet (labels are exact video time; `index.json` maps cell → second). Cross-check
the event log: damage sources, heals, HP/score across scene changes. Findings, by category:

| Category | Look for |
|---|---|
| presentation | HUD overlaps, readability in a crowd, safe areas (CRT/overscan), hidden payoffs |
| balance | difficulty curve, score/XP economy, resource carry-over, dead stretches of no threat |
| fun | unrewarded secrets, repetition, dead time, choices that are never close |
| juice | weak payoffs on big moments: no flash/shake/sound/hitstop where one is earned |
| bugs | engine errors, warnings, stale docs, desyncs between log and footage |
| build-diversity | see §4 |

## 4. Build-diversity lens (roguelites, horde/survivor games)

The goal is a *shaped* power curve, not a flat one: **some OP chase builds on purpose, some
weaker, none dead, none accidentally broken.**

1. **Headless synergy sweep.** For every build (weapon × upgrade path × fusion), run N seeded
   headless runs with a bot that *forces* that build. Record time-to-clear or wave reached,
   damage share, deaths.
2. **Natural assembly rate.** Separately, run the normal draft bot (picks what a player
   would) and count how often each build actually comes together, and by which level.
3. **Tier list** = power vs assembly rate. Read the quadrants:
   - high power, low rate → **intended chase build**; keep, make it feel special.
   - high power, high rate → **accidentally broken**; it will eat every run. Nerf or gate.
   - low power, any rate → **weak**; fine if it is a stepping stone, bad if it is a trap pick.
   - never assembles or never wins → **dead**; fix the unlock or the numbers.
4. Show the chosen OP build in the video so the user sees what "too strong" looks like.

Re-sweep after every balance change: chaotic sims hit scripted beats only on some seeds.

## 5. Approval page

Load `artifact-capabilities` and `artifact-design` first. Start from
`<skill dir>/assets/review_page.html`: replace its inline `findings` JSON, publish with
`capabilities: {db: {}, user: {}, downloads: true}` and `files: {"video.mp4": <share encode>}`.

- Video + download button; chapter list that seeks; category filter.
- One card per finding: category, timecode (click to seek), what was seen, proposal,
  effort/impact, Approve / Later / Reject + note. **Balance proposals carry a `change`
  table** (knob, from, to) plus the sweep evidence, so the user approves numbers, not vibes.
- Decisions save to the artifact db, collection `decisions`, doc id = finding id
  (`{verdict, note, at}`). Read them with `ArtifactData` list `decisions` — never re-ask in chat.
  Storage sits behind one `store` adapter in the template; change it there only.

## 6. Implement approved items

- Read `decisions`. On a feature branch: commit prior work, then do repo-wide chores and any
  shared contract (signals, interfaces, config keys) yourself first.
- One agent per disjoint file-ownership group, each in its own short-path worktree outside
  synced folders. The orchestrator merges each branch and reruns ALL suites after every merge.
- Per agent: characterization tests, failing test first, mutation-check new guards,
  screenshot validation.
- **Balance/tuning LAST**, on the merged base, then re-sweep (§4).

## 7. Round 2

Re-record the same route and seed; review again — fixes create their own bugs (callouts
interrupting each other, new overlaps). Update the *same* artifact: before/after videos,
`"shipped": true` cards saying what changed, new findings with fresh votes. Ask before
merging to main or shipping.

## Scripts

| Script | Does | Fails (exit 1) when |
|---|---|---|
| `contact_sheet.py` | video or frame dir → labelled NxM sheets + `index.json` | no frames (missing file, start past end) |
| `extract_moment.py` | full-size frames around a timecode | timecode past the end, nothing extracted |
| `encode_share.py` | two-pass share-size MP4, optional time-lapse | unreadable input, >10% over cap |
| `record_web.mjs` | virtual-clock CDP recorder | **stub** — exits 2 until ported |
| `smoke_test.py` | proves the three above work and can fail | prints `SMOKE: ALL PASS` |
