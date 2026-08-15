# Palettes

Ready-made PALETTE blocks for `ui_theme.gd`. `scaffold_ui.py --palette <name>` substitutes one
of these at scaffold time; you can also paste one over the PALETTE block by hand.

**Pick one from the game's tone before scaffolding, not after.** The kit has to ship *some*
default, and `amber` is it — which means a UI nobody chose a palette for comes out warm and
golden regardless of whether the game is a horror piece or a spreadsheet simulator. Amber being
the default is not a recommendation, and "it looked yellow" is the most common thing wrong with
a UI built from this kit.

Every colour a screen uses is derived from these sixteen constants, so this file is the whole
art direction. `BACKDROP_OPAQUE` is deliberately absent: it is derived from `BACKDROP` in the
template and must stay that way.

That sentence was aspirational for two releases. `scripts/palette_lint.py` is what makes it a
fact — it exits 1 on any colour a palette swap cannot reach, and the last thing it caught was
`ui_theme.gd`'s own button, slot and badge fills sitting as literals below this block, which
left `clinical` rendering near-black text on a near-black button. Run it after editing a
palette or adding a screen.

## How to read a palette

Two of these pairs are load-bearing and are the ones people get wrong when hand-rolling a new
palette:

- **`CHIP_FILL` / `CHIP_INK`** is a contrast pair. The chip is the keycap in a "press [E]"
  prompt. If you darken the fill you *must* lighten the ink, or the glyph vanishes into it.
- **`TEXT` / `PANEL_FILL`** is the other. Most of these palettes are dark-panelled with light
  text; `clinical` inverts both together. Changing one without the other is how you get a
  screen that renders as a blank rectangle.

`OUTLINE` is the outline drawn *behind* HUD text so it survives arbitrary gameplay underneath —
it opposes `TEXT`, so a light-text palette needs a dark outline and vice versa.

## amber

Warm, golden, lamplit. Cosy exploration, treasure hunting, anything with collecting in it.
The kit's default, and the right answer often enough to stay the default.

```gdscript
const ACCENT: Color = Color(1.0, 0.76, 0.24)
const ACCENT_DEEP: Color = Color(0.72, 0.51, 0.16)
const TEXT: Color = Color(0.96, 0.93, 0.88)
const TEXT_DIM: Color = Color(0.76, 0.72, 0.68)
const TEXT_FAINT: Color = Color(0.62, 0.58, 0.55)
const PANEL_FILL: Color = Color(0.05, 0.04, 0.06, 0.68)
const PANEL_FILL_DEEP: Color = Color(0.06, 0.05, 0.07, 0.88)
const PANEL_BORDER: Color = Color(1.0, 0.93, 0.84, 0.11)
const BACKDROP: Color = Color(0.06, 0.05, 0.07, 0.86)
const CHIP_FILL: Color = Color(0.93, 0.90, 0.86, 0.92)
const CHIP_INK: Color = Color(0.08, 0.07, 0.06)
const SLOT_EMPTY: Color = Color(0.16, 0.15, 0.17)
const GOOD: Color = Color(0.44, 0.83, 0.45)
const BAD: Color = Color(0.96, 0.36, 0.33)
const SHADOW: Color = Color(0.0, 0.0, 0.0, 0.45)
const OUTLINE: Color = Color(0.03, 0.02, 0.04, 0.85)
```

## clinical

Cold, sterile, deadpan. Management sims, sci-fi interfaces, anything institutional or
bureaucratic, anything whose humour is dry. The one light-panelled palette here: panels are
near-white, text is near-black, and the keycap chip inverts to dark-on-light. Use it when the
UI should feel like equipment rather than like a game.

```gdscript
const ACCENT: Color = Color(0.10, 0.62, 0.78)
const ACCENT_DEEP: Color = Color(0.06, 0.42, 0.54)
const TEXT: Color = Color(0.09, 0.13, 0.16)
const TEXT_DIM: Color = Color(0.28, 0.34, 0.38)
const TEXT_FAINT: Color = Color(0.45, 0.51, 0.55)
const PANEL_FILL: Color = Color(0.88, 0.92, 0.94, 0.72)
const PANEL_FILL_DEEP: Color = Color(0.93, 0.96, 0.97, 0.92)
const PANEL_BORDER: Color = Color(0.10, 0.20, 0.26, 0.22)
const BACKDROP: Color = Color(0.82, 0.87, 0.90, 0.88)
const CHIP_FILL: Color = Color(0.13, 0.18, 0.22, 0.94)
const CHIP_INK: Color = Color(0.94, 0.97, 0.98)
const SLOT_EMPTY: Color = Color(0.74, 0.80, 0.84)
const GOOD: Color = Color(0.13, 0.55, 0.35)
const BAD: Color = Color(0.78, 0.22, 0.20)
const SHADOW: Color = Color(0.20, 0.28, 0.34, 0.28)
const OUTLINE: Color = Color(0.90, 0.94, 0.96, 0.85)
```

## bloodmoon

Horror. Near-black panels, a desaturated arterial red as the only saturated thing on screen.
Survival horror, dungeon crawlers with teeth, anything where the HUD should feel like a warning
rather than a readout.

```gdscript
const ACCENT: Color = Color(0.85, 0.18, 0.16)
const ACCENT_DEEP: Color = Color(0.48, 0.09, 0.09)
const TEXT: Color = Color(0.92, 0.87, 0.85)
const TEXT_DIM: Color = Color(0.70, 0.63, 0.62)
const TEXT_FAINT: Color = Color(0.52, 0.45, 0.45)
const PANEL_FILL: Color = Color(0.06, 0.03, 0.03, 0.72)
const PANEL_FILL_DEEP: Color = Color(0.08, 0.04, 0.04, 0.90)
const PANEL_BORDER: Color = Color(0.85, 0.40, 0.34, 0.14)
const BACKDROP: Color = Color(0.04, 0.02, 0.02, 0.90)
const CHIP_FILL: Color = Color(0.88, 0.84, 0.82, 0.92)
const CHIP_INK: Color = Color(0.10, 0.05, 0.05)
const SLOT_EMPTY: Color = Color(0.15, 0.10, 0.10)
const GOOD: Color = Color(0.55, 0.72, 0.42)
const BAD: Color = Color(0.92, 0.26, 0.22)
const SHADOW: Color = Color(0.0, 0.0, 0.0, 0.55)
const OUTLINE: Color = Color(0.02, 0.01, 0.01, 0.88)
```

## candy

Bright, sweet, high-saturation. Puzzle games, casual games, anything aimed at children or
anything that wants to read as a toy. Purple panels rather than black, because pure black
chrome under a pink accent reads as edgy rather than sweet.

```gdscript
const ACCENT: Color = Color(1.0, 0.42, 0.62)
const ACCENT_DEEP: Color = Color(0.72, 0.24, 0.42)
const TEXT: Color = Color(0.99, 0.97, 1.0)
const TEXT_DIM: Color = Color(0.84, 0.80, 0.90)
const TEXT_FAINT: Color = Color(0.68, 0.64, 0.76)
const PANEL_FILL: Color = Color(0.22, 0.14, 0.34, 0.70)
const PANEL_FILL_DEEP: Color = Color(0.26, 0.16, 0.40, 0.90)
const PANEL_BORDER: Color = Color(1.0, 0.80, 0.92, 0.18)
const BACKDROP: Color = Color(0.16, 0.10, 0.26, 0.88)
const CHIP_FILL: Color = Color(0.98, 0.94, 1.0, 0.94)
const CHIP_INK: Color = Color(0.20, 0.10, 0.28)
const SLOT_EMPTY: Color = Color(0.32, 0.22, 0.46)
const GOOD: Color = Color(0.36, 0.86, 0.56)
const BAD: Color = Color(1.0, 0.40, 0.44)
const SHADOW: Color = Color(0.10, 0.02, 0.16, 0.42)
const OUTLINE: Color = Color(0.14, 0.06, 0.22, 0.85)
```

## noir

Monochrome with one cold highlight. Detective games, stealth, minimalist arcade, anything
black-and-white with a single colour used sparingly. The accent is a pale steel blue rather
than white so that selection is still legible as selection.

```gdscript
const ACCENT: Color = Color(0.62, 0.74, 0.86)
const ACCENT_DEEP: Color = Color(0.38, 0.47, 0.57)
const TEXT: Color = Color(0.94, 0.94, 0.94)
const TEXT_DIM: Color = Color(0.72, 0.72, 0.73)
const TEXT_FAINT: Color = Color(0.54, 0.54, 0.56)
const PANEL_FILL: Color = Color(0.06, 0.06, 0.07, 0.70)
const PANEL_FILL_DEEP: Color = Color(0.08, 0.08, 0.09, 0.90)
const PANEL_BORDER: Color = Color(0.90, 0.92, 0.96, 0.12)
const BACKDROP: Color = Color(0.05, 0.05, 0.06, 0.88)
const CHIP_FILL: Color = Color(0.92, 0.92, 0.93, 0.92)
const CHIP_INK: Color = Color(0.07, 0.07, 0.08)
const SLOT_EMPTY: Color = Color(0.16, 0.16, 0.18)
const GOOD: Color = Color(0.70, 0.78, 0.70)
const BAD: Color = Color(0.82, 0.44, 0.42)
const SHADOW: Color = Color(0.0, 0.0, 0.0, 0.50)
const OUTLINE: Color = Color(0.02, 0.02, 0.03, 0.85)
```

## verdant

Green and growing. Farming, nature, survival, anything set outdoors in daylight. Panels are a
very dark green rather than neutral black, which is what keeps it from reading as the amber
palette with the accent swapped.

```gdscript
const ACCENT: Color = Color(0.62, 0.84, 0.30)
const ACCENT_DEEP: Color = Color(0.38, 0.55, 0.18)
const TEXT: Color = Color(0.96, 0.97, 0.90)
const TEXT_DIM: Color = Color(0.78, 0.82, 0.70)
const TEXT_FAINT: Color = Color(0.60, 0.65, 0.54)
const PANEL_FILL: Color = Color(0.06, 0.09, 0.05, 0.70)
const PANEL_FILL_DEEP: Color = Color(0.07, 0.11, 0.06, 0.90)
const PANEL_BORDER: Color = Color(0.80, 0.92, 0.70, 0.14)
const BACKDROP: Color = Color(0.05, 0.08, 0.05, 0.88)
const CHIP_FILL: Color = Color(0.94, 0.95, 0.88, 0.92)
const CHIP_INK: Color = Color(0.09, 0.12, 0.06)
const SLOT_EMPTY: Color = Color(0.15, 0.19, 0.13)
const GOOD: Color = Color(0.52, 0.86, 0.44)
const BAD: Color = Color(0.90, 0.44, 0.28)
const SHADOW: Color = Color(0.0, 0.02, 0.0, 0.45)
const OUTLINE: Color = Color(0.02, 0.04, 0.02, 0.85)
```

## Writing a new one

Copy the closest palette, change `ACCENT` first, then push `PANEL_FILL` a little toward the
accent's hue — a fully neutral panel under a strong accent is what makes a palette look like a
recolour rather than a design. Then check the two pairs named at the top. Sixteen constants is
the whole job; if you find yourself wanting a seventeenth, the thing you actually want is
probably derived, like `BACKDROP_OPAQUE`.
