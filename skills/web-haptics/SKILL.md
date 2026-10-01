---
name: web-haptics
description: Add vibration to a browser game with navigator.vibrate, driven by the game's own events — a pure cue table with priorities, a thin playback layer that never lets a bumper tap cut off a jackpot, a settings toggle shown only on devices that can actually buzz, and a headless test that proves real taps reach the vibrator. Use whenever the user asks to "add vibration", "add haptics", "rumble on mobile", "make hits feel like something", "buzz the phone when I score", "vibrate on game over", "add a vibration setting", or wants game feel on a phone for a web, itch.io, Phaser, Three.js, canvas or web-exported game — and at the symptoms: "navigator.vibrate does nothing", "vibrate returns false", "vibration works on my phone but not on itch.io", "vibrate in an iframe", "[Intervention] Blocked call to navigator.vibrate", "haptics on iOS", "iPhone doesn't vibrate", "the vibration toggle shows on desktop", "the phone just buzzes continuously", "the big moments don't vibrate", "one long rattle instead of taps", "the phone keeps vibrating after I switch tabs", "the new settings row pushed a button off screen". For the event-list test, see `derive-the-list`; for testing code behind a "can this device vibrate?" gate, `extract-a-testable-seam`.
---

# Web haptics

Vibration in a browser game fails silently in every direction: iOS has no API, desktop has
one that does nothing, an iframe refuses calls until it is tapped, and each call cancels the
last, so a busy frame turns the jackpot into a 10 ms tick. None of these throw. Built for a
phone pinball game (plain JS event bus, shipped in an itch.io iframe); the shape fits any
browser game whose systems emit events — an engine's web export that calls
`navigator.vibrate` underneath meets the same rules.

## Facts that decide the design

- **Support.** Android Chromium browsers vibrate; treat any other Android browser as unknown
  until a phone says otherwise. **iOS Safari has no `navigator.vibrate`** at all, and nothing
  a page does from a game loop changes that. Desktop Chrome *defines* the function and returns
  `true`, but there is no motor: gate on `matchMedia('(pointer: coarse)').matches` **and**
  `typeof navigator.vibrate === 'function'`, or the settings toggle appears on laptops and does
  nothing.
- **Sticky activation.** Chrome ignores `vibrate` until the frame has had a tap: the call
  returns `false` and the console logs an `[Intervention] Blocked call to navigator.vibrate`
  warning. The call need not be *inside* the gesture — calling from `requestAnimationFrame`
  minutes later is fine once any tap has landed, so a game that needs a tap to start is
  already covered. **In a cross-origin iframe (itch.io and most portals) the tap must land in
  the iframe**; a tap on the host page's "Run game" button does not count, which is why it
  works on localhost and not on itch.
- **One pattern at a time.** Each `vibrate()` cancels the running pattern. Calling once per
  event means the last event of the frame wins — usually a wall tap that just erased the
  jackpot. So: one call per frame (the frame's top-priority cue), and a running cue is
  replaced only by a *strictly* higher priority. Hold equal or lower cues off for
  `max(pattern length, ~50 ms)`; that also caps a bumper storm at ~20 taps/s instead of one
  continuous buzz.
- **Cheap motors skip pulses under ~10 ms.** Taps 10–22 ms; multi-pulse patterns (≤ 400 ms
  total, odd length so they end on a buzz rather than a dead pause that only stretches the
  busy window) only for rule-level moments — jackpot, mode start, lost ball, game over. The
  player's own input (a flipper, a jump) should be the lightest cue: it is the one they feel
  most, and the one that fires most often.
- **A hidden tab keeps buzzing** the rest of a running pattern. Call `vibrate(0)` on
  `visibilitychange` → hidden.
- **`true` is not proof of a buzz.** It means the browser accepted the call; the phone's own
  vibration/haptics setting can still swallow it. Only a real device answers "can you feel
  it".

## Shape

1. **A pure cue table**, no `navigator` in sight: `key → [pattern ms, priority]`, keys refined
   the same way the audio cues are (`award:<kind>`, `mode.start:<mode>`, `ball.drain:lost`),
   so the two stay in step. Keys absent from the table are still. `pickCue(events)` returns the
   highest priority, first on a tie. Batch facts (was this drain the *lost* ball?) are derived
   from the whole frame's events, not one event.
2. **A thin playback layer**, `createHaptics({ vibrate: fn | null, now })` →
   `consume(events) / setEnabled(on) / stop() / status()`. `vibrate` is injected — `null`
   where unsupported, so every call is a no-op and a headless test can pass a spy. The whole
   anti-cut rule is a few lines:

   ```js
   const cue = pickCue(events);
   if (!cue || !enabled || !vibrate) return;
   const t = now();
   if (t < busyUntil && cue.priority <= busyPriority) return;   // never cut an equal/higher cue
   busyUntil = t + Math.max(patternMs(cue.pattern), MIN_GAP_MS); // ~50 ms
   busyPriority = cue.priority;
   let ok; try { ok = vibrate([...cue.pattern]) !== false; } catch { ok = false; }
   ok ? played++ : blocked++;
   ```

   Pass a **copy** of the pattern: `Object.freeze` on the table is shallow, so the inner arrays
   stay mutable and anything holding the reference (a polyfill, a test spy) can rewrite the
   table for every later cue. Count refused calls (`false` or a throw) as `blocked`; never retry
   — a retry loop on a frame that has not been tapped spams the intervention warning — and never
   throw into the game loop.
3. **Wire it beside audio behind one facade** (`apply(settings)`, `consume(events, state)`):
   the two share the event stream and the settings, and the entry point gains one call instead
   of four. Cancel on `visibilitychange` hidden there.
4. **A setting**, `haptics`, default on, cleaned like the other booleans; previously saved
   settings without the key load as on, not as `undefined`-means-off.
5. **A menu toggle shown only where the device can vibrate.** Switching it back on buzzes once
   (~30 ms): the player feels that it works, and it doubles as "does my phone vibrate at all?".

## Proof

- **Derive the cue keys' event types from the emit sites in the source**, not a hand list, so a
  renamed event fails the test instead of silently going still (`derive-the-list`). Assert the
  scan found something, or an empty scan passes everything.
- **Unit:** priority beats tie, equal priority does not cut a running cue, the busy window
  expires, a storm of taps is capped, the pattern passed is a copy, unsupported is a no-op,
  refused is counted, off → on buzzes once, off stops a running cue. Table shape: whole
  milliseconds, odd length, taps under 25 ms, total ≤ 400 ms.
- **Headless e2e, both ways.** Expose `status()` → `{ supported, enabled, played, blocked }` on
  a debug hook. In an emulated phone (puppeteer `isMobile: true, hasTouch: true`, a phone UA),
  *touch* the controls with `page.touchscreen` and assert `played > 0 && blocked === 0`;
  `blocked > 0` there is the sticky-activation bug. On a mouse-only desktop viewport assert
  `supported === false`. Then delete the `haptics.consume` wiring line and watch the phone
  check fail; a check that stays green is decorative.
- **A new menu row can push the last button below the fold** on a landscape phone. Measure the
  panel (`scrollHeight` vs `clientHeight`, every control's rect inside it) at 844×390 and
  640×360, and fail on any control outside it.
- **Headless cannot prove it feels right.** Emulation proves `vibrate` is called and accepted,
  not how a 10 ms tick feels on a cheap motor. Tune the table on a real Android phone, in the
  real embed, before calling it done.
