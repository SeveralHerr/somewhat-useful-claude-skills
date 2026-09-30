---
name: mockup-on-screenshot
description: Mock up a new game feature, prop, toy or art idea by overlaying the game's REAL sprites on a REAL screenshot of the running game — measured landmarks, an occlusion trick for putting art "behind" the playfield, and a local headless-browser render of every artboard before it is published or shown. Use whenever the user asks for mockups, concepts, "show me where X could go", "what would it look like with Y", "put the statue/arch/logo from the main game into this one", a concept board, a design canvas, or a shareable artifact of feature ideas for an existing game — and at the symptoms of mocking up from memory: redrawn sprites that do not match the game, concepts that fit only because the table was drawn emptier than it is, a toy hidden under a rail or HUD card, an overlay that vanishes against the background, text clipped at the artboard edge, or a published mockup whose images never loaded. For making new art that must match a 2D pack, use `kenney-asset-kit`; for store-page art, `itch-store-page`.
---

# Mockup on a real screenshot

A mockup is a claim that an idea fits the game. Drawn from memory it proves nothing: the
redraw is cleaner than the game, the playfield is emptier, and every idea fits. Overlaying
the real assets on a real frame keeps each concept honest about space, contrast and scale —
in the run this skill comes from, it produced six concepts in one pass, and the local
preview caught two that were broken before anyone saw them.

## Procedure

1. **Find the real art.** Locate the actual sprite files — in the game's own repo, or a
   sibling repo it borrows from (grep scene files for the texture names to find which file
   is "the arch" the user means). Never redraw an asset that exists; if the user refers to a
   prop by nickname, confirm the file before building six boards around the wrong one.
2. **Base every board on a real screenshot** of the running game at the viewport that
   matters (phone portrait at 2x is usually the tightest). Take a fresh one if the last
   capture predates recent layout changes.
3. **Measure the landmarks once and write them down** in CSS pixels on that screenshot:
   HUD cards, rails, lanes, bumpers, flipper pivots, drain, safe area. Every overlay is then
   placed against numbers, not by eye, and the same table tells you what a concept covers.
4. **Overlay with plain absolute `<img>`** at the asset's native pixel scale;
   `image-rendering: pixelated` for pixel art so the preview does not smear it.
5. **Put an overlay "behind" the playfield** by stacking the same screenshot again on top
   of it with a `clip-path: polygon(…)` tracing the foreground outline (cabinet, table
   body, character). The overlay then shows only where the background is — cheaper and more
   faithful than cutting the art.
6. **Split concepts into two rows up front:** gameplay (it changes what the player does) and
   purely aesthetic (backdrop, frame, attract mode). Users routinely ask for the second set
   after seeing the first; offering both saves the round trip.
7. **Keep boards lean.** Each artboard holds the mock, one close-up and a short rule card in
   the game's own UI style. The rationale lives in the chat or the page's prose, not painted
   over the art it describes.

## Preview locally before publishing

Render every artboard in a headless browser and look at the PNG before anyone else does.
If the host rewrites asset URLs (uploaded-asset paths such as `/_blob/<id>`) or wraps the
page in runtime scripts and custom elements, make a preview copy: strip those, point each
image at its local file (`file:///…`, keep an id → file map from the upload), and launch
Chrome with `--allow-file-access-from-files`. A missing image in the preview is a missing
image in production.

Per pass, look for three things and fix them:

- **Occluded toys** — the new prop sits under a rail, HUD card or top bar. One of the first
  board set hid an arch entirely under the top rail.
- **Low-contrast overlays** — a dark sprite on a dark playfield; add an outline or move it.
- **Clipped or covering text** — labels off the artboard edge, or a path line drawn over
  the art it explains.

Re-render after each fix; publish only when a pass finds nothing.
