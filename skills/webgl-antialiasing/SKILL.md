---
name: webgl-antialiasing
description: Fix jagged edges in a three.js / WebGL browser game without breaking low-end devices — find which quality profile and context actually drew the jaggies, prefer MSAA over post-process AA, keep a self-heal ladder (full → safe → bare) for phone drivers that lose the context, and prove it with device screenshots, A/B crops and a headless context-loss test. Use whenever the user says jaggies, jagged edges, jagged edges on Android, aliased or stair-stepped rails, pixelated edges, dashed or broken outlines, "three.js antialias not working", "antialias: true does nothing", "FXAA makes it blurry", "pixel art blurry after AA", "text went soft after adding SMAA", "it looks fine on desktop but jagged on my phone", "WebGL context lost on phone", "white canvas but the HUD still works", "Error creating WebGL context", "safe mode GPU", a low-quality or low-power render profile, PowerVR / Mali / Adreno trouble, or AA on a Raspberry Pi — and when an EffectComposer pipeline turned the edges jagged again. For Godot texture filtering ("my art is blurry in Godot") use `kenney-asset-kit`; for making the heal decision unit-testable, `extract-a-testable-seam`.
---

# WebGL anti-aliasing on a budget

Jaggies on a phone are rarely "AA is missing". In the three.js pinball game this skill comes
from, desktop was smooth; the jagged screenshot came from the *safe* profile a phone had
healed into — MSAA off "for safety", DPR capped at 1, then upscaled 2.75× by the phone. The
first fix (tuned FXAA) passed a headless crop and blurred every sprite and label on the
device, and was removed the same day. Diagnose which path drew the frame before choosing.

## Diagnose first

- **Find which profile and context drew the complaint.** If the game has quality profiles,
  the player's device may not be on the one you test. Expose a health hook (e.g.
  `window.__game.health()`) that reports profile, GPU and real AA, and read it on the device.
- **Decide from `gl.getParameter(gl.SAMPLES)`, never from the flag you passed.**
  `gl.getContextAttributes().antialias` echoes the request; browsers ignore it on low-RAM
  builds and under driver workarounds. `SAMPLES > 0` is MSAA, 0 is none. Report that as `aa`.
- **DPR upscaling makes big stair-steps.** A canvas rendered at DPR 1 and shown on a DPR-3
  screen is upscaled by the compositor: every edge becomes a 3-pixel staircase, and lines
  thinner than a pixel (inverted-hull outlines, wireframes) break into dashes. Compare
  `renderer.getPixelRatio()` with `devicePixelRatio`.
- **Blurry pixel art with no AA pass is texture filtering**, not anti-aliasing:
  `texture.magFilter = NearestFilter` (and `generateMipmaps = false` for sprites) fixes it.
- **Post-processing silently drops canvas MSAA.** `EffectComposer` renders the scene into its
  own render target, so `antialias: true` on the renderer no longer touches the scene. Pass
  the composer a target with `samples: 4` (WebGL2), or the edges go jagged the day bloom is
  added.

## Choose

- **MSAA, not FXAA/SMAA, for a game with pixel art or small texture text.** Post-process AA
  works on the final image, so it cannot tell a sprite's hard pixel edge from a geometry edge
  and smears both; even tuned (span 2, threshold 0.25) it blurred characters, faces and labels
  on a DPR-2.75 phone, and it still cannot join an outline thinner than a pixel. MSAA resolves
  only geometry edges; textures stay crisp.
- **MSAA is cheap where you fear it most.** Tile GPUs (Mali, PowerVR, Adreno, Raspberry Pi
  V3D/VC4) resolve it on-chip. It is expensive on SwiftShader (a CPU rasterizer), so headless
  fps overstates the cost — treat it as a relative number, never a device prediction.
- **`antialias` is fixed at context creation.** three.js cannot toggle it on a live renderer,
  so a quality change means a new context or a reload — which is why profiles are chosen at
  boot.
- **A precaution flag needs a heal path, not a permanent off.** Turning MSAA off in the safe
  profile "just in case" after a driver crash ships jaggies to every phone that lands there.
  Keep MSAA on in safe and let the heal ladder below catch the drivers that cannot take it.
- Only when `SAMPLES` is 0 on a profile that asked for MSAA, consider a WebGL2 multisampled
  render target. Ask which device first — one question replaced a render-target design here
  that only one untested device might have needed.

## Profiles and the heal ladder

- **Three profiles, each one step down:** `full` (desktop look), `safe` (no shadow maps, no
  PMREM environment, DPR ≤ 1, textures ≤ 1024 px, `powerPreference: 'low-power'`, **MSAA
  on**), `bare` (safe minus MSAA). Pick at boot: a `?gl=full|safe|bare` override, then the
  remembered choice, then a GPU heuristic (PowerVR, Mali-4xx/T6xx and Adreno 3xx start safe;
  an unknown or masked GPU string stays full). Read the GPU from a throw-away context via
  `WEBGL_debug_renderer_info`, then release it with `WEBGL_lose_context` — browsers cap live
  contexts and silently lose the oldest.
- **Context creation falls back per attribute.** Some phone drivers refuse attributes desktop
  accepts, and three.js throws `Error creating WebGL context.` Try attribute sets best-first
  (MSAA, then without, then low-power with `failIfMajorPerformanceCaveat: false`) and fail
  boot only when all of them do, with a message that says so.
- **Heal on an early failure: step down one rung and reload, once per rung per tab.** When
  the context is lost (or a pixel canary reads nothing) within ~30 s of boot, remember the
  next profile in localStorage, append the failing profile to a list in sessionStorage, and
  `location.reload()`. A profile already in that list, or a failing `bare`, shows the banner
  instead. The list bounds reloads by the ladder's length — no reload loop — and
  sessionStorage scopes it to the tab, so the next session may try again. Keep the decision a
  pure function (`healPlan({ profile, sinceBootMs, healedFrom })`) and the side effects in a
  thin wrapper; wrap every storage access in try/catch (embed iframes and private modes block
  it).
- **A dead canvas must say so.** A lost context paints white on some Android phones while a
  DOM HUD keeps running — a "blank game" with no error. Call `preventDefault()` on
  `webglcontextlost` (otherwise the browser will not restore it), read one centre pixel with
  `readPixels` in the same task as an early draw (no `preserveDrawingBuffer` needed), and
  when the context stays lost for > 2 s or the canary drew nothing, put the cause, profile and
  GPU name on screen. Read the GPU name while the context is alive — a lost context answers
  `null`. A player's screenshot is often the only report you get.

## Prove

- **Unit:** the profiles (safe keeps MSAA, bare = safe minus MSAA), the attempts per profile,
  the heal plan on both rungs, the per-tab guard and the window cut-off. Mutate each one and
  watch it go red.
- **Headless heal loop:** emulation cannot reproduce a driver crash, but
  `gl.getExtension('WEBGL_lose_context').loseContext()` right after boot can. Drive it from
  puppeteer and assert full → reload into safe → lose again → bare → lose again → banner,
  with the reload count bounded. Prove this before shipping the heal; it is the one path no
  desktop playtest exercises.
- **E2E:** `health().aa === 'msaa'` on desktop full and on a phone viewport with `?gl=safe`,
  and the canary drew.
- **Visual:** a three-panel crop (no AA | candidate | MSAA) of one geometry edge and one text
  cluster, then a screenshot from the real device. A headless 390 px crop at DPR 1 hid the
  FXAA blur that a DPR-2.75 phone made obvious.
- **Cost:** fps per profile from the same headless run, before and after — relative only.
  Say plainly which devices are unmeasured (real-GPU fps, a Pi's MSAA cost) instead of
  calling performance done.
