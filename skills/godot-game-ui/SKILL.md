---
name: godot-game-ui
description: Build polished in-game UI for Godot 4 games — HUDs, pause menus, title screens, end-of-run/results screens, reward and discovery cards, counters, prompts, crosshairs, tool/ability bars, and the motion that makes them feel good. Ships a scaffolder that installs a working, re-skinnable UI kit into any Godot project. Use this whenever the user is working on a Godot game's interface or menus in any form — "add a HUD", "make a pause menu", "show the score", "the UI looks programmer-art", "add a results screen", "level complete screen", "inventory bar", "health display", "interaction prompt", "make the UI feel juicier" — and also when they are building a Godot game feature that will obviously need an interface (a collection system, a scoring system, a currency, a timer) even if they have not mentioned UI yet. Prefer this over hand-rolling Control nodes from scratch; it exists because that path reliably produces UI that looks unfinished and breaks headless tests.
---

# Godot 4 Game UI

A complete, re-skinnable UI system for Godot 4 games: theme, motion, HUD, and the three
shell screens (title / pause / results). Everything is built from Godot primitives and code
— **no image files, no font files, no `.tres` themes, no `.tscn` required.**

That constraint is the reason the kit works rather than a limitation to apologise for. UI
that needs art blocks on art. UI built from `StyleBoxFlat`, `_draw()` and anchors ships the
day it is written, scales to any resolution, re-skins in one block, and survives being
merged by several people at once.

## Fast path

If the user wants working UI in their project, install the kit and wire it up:

```bash
python ~/.claude/skills/godot-game-ui/scripts/scaffold_ui.py /path/to/project
godot --headless --path /path/to/project --import   # generates .uid sidecars + class cache
```

`--only theme,hud` installs a subset (dependencies resolve automatically). `--dest` changes
the target directory. `--force` overwrites. The script prints the integration snippet for
whatever it installed, so wiring is a copy-paste plus renaming the stats.

**Always run the import pass afterwards.** The templates declare `class_name UiTheme` /
`UiMotion` / `GameHud` etc., and until Godot rebuilds its global class cache, every
reference to them fails to resolve — which presents as a cascade of parse errors in files
nobody touched.

Then read the templates you installed and adapt them. They are meant to be edited: the
scaffolder gives you a working starting point, not a library to depend on.

## The nine ideas worth carrying

These matter more than the code. If you write UI from scratch instead of using the kit,
carry these anyway.

### 1. One theme file, and nothing else knows a colour

`ui_theme.gd` holds the palette, the type scale and every `StyleBoxFlat` factory. Screens
call `UiTheme.pill_box()`, never `StyleBoxFlat.new()` with literal colours. The moment two
files know the accent colour they drift, and "the UI looks inconsistent" is almost always
this rather than a design failure.

Re-skinning is then one block at the top of one file. A horror game and a candy-coloured
puzzler differ by about fifteen constants.

### 2. Every label gets an outline *and* a shadow

Game UI sits over an unpredictable, often bright, often moving background. This is the
single most common way a HUD that looked great in a mockup becomes unreadable in play. A
shadow alone fails on bright backgrounds; an outline alone looks flat. Both together
survive anything.

This is why `UiTheme.style_label()` exists as one call — a style guideline nobody applies
consistently is not a style guideline.

### 3. Icons are vector-drawn, not imported

`UiTheme.Glyph` is a `Control` that draws itself in `_draw()` from circles, arcs and
polygons, authored in normalised 0..1 space. It scales to any size, re-tints in one call
with no per-colour asset, costs no import, and stays legible at 16px because it is built
from shapes rather than downsampled art.

Add cases to `Glyph.Kind` for your game. Keep each to a handful of draw calls — an icon
needing twenty wants to be a real asset.

### 4. Numbers roll, they never snap

A counter that jumps from 40 to 165 communicates a new value. One that counts up
communicates *that something happened*, which is the actual job. `UiMotion.count_to()`
scales duration with distance travelled, so +1 is a tick and +5000 is an event.

The subtle part: **start the roll from the value currently displayed, not from the model's
previous value.** They diverge whenever two changes land inside one animation, and starting
from the model makes the number visibly jump backwards before counting up again.

### 5. Animation must degrade to snapping, or the UI is untestable

Headless Godot pumps no frames, so a tween created there never advances and never
completes. Any code that sets text inside a tween callback leaves the label empty forever,
and the test asserting on that text fails for a reason unrelated to the logic it meant to
check.

Every animated function in `ui_motion.gd` therefore has the same shape: try to tween, and
if you cannot, apply the final value immediately. A headless run ends in exactly the state
a finished animation would have reached, just without the motion.

Concretely: `UiMotion.tween(host)` returns `null` outside the tree; every caller handles
null by snapping. Never call `create_tween()` directly in UI code.

### 6. The prompt's shape is decided by its text

A contextual prompt has two jobs that look identical and are not:

```
Press [E] to open      an action you can take       -> keycap + body
It's locked            a status you cannot act on   -> dimmed body, no keycap
```

Showing a keycap in front of a refusal tells the player to press the key that just failed.
`GameHud.set_prompt()` detects `[X]` in the string and picks the shape itself, so callers
never have to think about it and can pass either kind of message to the same function.

### 7. Reward cards queue; they never interrupt each other

Two rewards landing within a second is exactly when the player most wants to read both, and
a card that cuts off its predecessor shows neither. `GameHud.show_card()` appends to a queue
and drains it one at a time.

More generally: the reward announcement is the payoff moment of a collection game and
deserves a real card — kicker, large name, tinted rarity, flavour line — rather than a line
of text in the corner. It is the single highest-leverage piece of UI in that genre.

### 8. Each screen edge gets one margin, and each edge gets one container

The fastest way to make a HUD look unfinished is to anchor every region separately. Each one
then needs its own offset, those offsets set the *top* edge, and regions of different heights
end up with different bottom edges. Nobody can point at what is wrong — it just reads as
sloppy. The bottom of a HUD is where this shows first, because it holds the three most
dissimilar things you own: a row of square slots, a line of type, and a huge number.

So: one `UiTheme.MARGIN` for every edge, and one bottom-anchored container with
`grow_vertical = GROW_DIRECTION_BEGIN` holding everything that lives down there. Cells use
`size_flags_vertical = SIZE_SHRINK_END` so they hang from a shared baseline regardless of
height, and because the stack grows upward, showing or hiding a transient row (the held-item
strip) never shifts the row below it.

### 9. Scale the whole layer by viewport height ÷ a reference height

A HUD authored at 1080p and shipped unscaled is a postage stamp on a 4K monitor. The fix is
one factor applied to the whole layer rather than a scaled font size threaded through every
call site — `CanvasLayer.scale` and `Control.scale` both work, and scaling the layer catches
the vector glyphs, corner radii and stylebox margins that a font-size approach would miss.

Two details make it come out right:

- **Compensate the root's size.** Scaling the layer does not change what the root Control
  thinks its rectangle is, so set `root.size = viewport_size / scale`, with the anchors
  released to `PRESET_TOP_LEFT` first — a `FULL_RECT` control recomputes its own size every
  layout pass and silently overwrites the assignment.
- **Height, never width or a diagonal.** On a 21:9 ultrawide the UI should be the size it is
  on 16:9 and merely spread further apart. Driving off height gives exactly that; the extra
  width just moves the anchored edges outward.

`UiTheme.fit(host, root)` is those few lines, and it is deliberately null-safe: with no
viewport it returns 1.0 and touches nothing, so a HUD built before it enters the tree — or
asserted against headlessly — keeps its plain anchored layout.

It also composes correctly with either stretch mode, which is why there is nothing to
configure. Under `stretch/disabled` the visible rect is real pixels and this does all the
work; under `stretch/canvas_items` the visible rect is the constant base size, so this
contributes a constant and the engine supplies the rest. The two multiply out to the same
on-screen result.

## Layout convention

Players already know this arrangement from tidying/collection games, and matching it means
they do not have to learn yours:

```
┌──────────────────────────────────────────────────────────┐
│ ▣ 12/40    ← stat pill stack                             │
│ ● 3/8         icon + count, one pill each                │
│ $ 1,280                                                  │
│ ▬▬▬▬▭▭▭▭   ← thin progress bar                          │
│ ▸ hint breadcrumb                                        │
│                                                          │
│                  ┌──────────────┐  ← reward card         │
│                  │ ITEM FOUND   │     (transient, queued)│
│                  │ Golden Key   │                        │
│                  └──────────────┘                        │
│                       NICE!       ← shout (transient)    │
│                        ⊙          ← crosshair            │
│                 Press [E] to open ← prompt               │
│                                                          │
│                  Brass Lantern    ← held item            │
│ ▣ ▣ ▣ ▣                                            3/8   │
│ 1 2 3 4  ← tool slots                    big counter ↗   │
└──────────────────────────────────────────────────────────┘
```

## Structural gotchas that cost real time

**A `CanvasLayer` has no size.** `hud.size` does not exist. Give the HUD a full-rect
`Control` child named `Root` and anchor everything inside it; expose `layout_size()` for
tests that need to assert the HUD filled the viewport. Once the layer is scaled (idea 9)
`layout_size()` must return `_root.size * scale` — screen space, not the pre-scale rect —
or every test asserting the HUD covers the viewport starts failing on anything but a 1080p
display, for a reason that has nothing to do with the layout.

**`REFERENCE_HEIGHT` is what "authored size" means.** The kit's pixel metrics appear exactly
as written when the viewport is that tall. Under `stretch/canvas_items` the viewport is your
project's *base* height, not the window's, so a project based at 1152×648 renders the whole
UI at 0.6× until you either raise the base to 1920×1080 or drop `REFERENCE_HEIGHT` to 648.
Neither is wrong — but if the HUD looks uniformly too small or too chunky and the proportions
are all correct, this is the number, and it is the only one.

**Pause menus need `PROCESS_MODE_ALWAYS` on every node, not just the root.**
`get_tree().paused` stops processing for everything inheriting `PAUSABLE`, so a button
whose parent chain inherits the default appears but does not respond — which reads as a
broken UI rather than a paused tree. `PauseMenu._always()` exists so this cannot be
forgotten per-node.

**Layer ordering.** HUD at 5, pause overlay at 50, full-screen flash effects at 128. Pick
the numbers up front; discovering the pause menu renders behind the HUD is an annoying way
to spend twenty minutes.

**Shell screens should emit signals, not call a scene-flow singleton.** A pause menu that
hard-codes `SceneFlow.goto_menu()` only works in the project it was written for. Connecting
three signals is the entire integration cost of reuse.

**Set `pivot_offset` from the current size on every punch**, not once at `_ready`. A Control
inside a container is resized after `_ready`, and a stale pivot makes the scale visibly
swing from a corner.

**Headless Godot clamps the main window to 64×64.** A UI test that sets
`root.size = Vector2i(1920, 1080)` and then asserts the layout is 1920×1080 fails against a
viewport that is really 64×64 — and it looks like a UI bug rather than a display-server one.
Assert against `get_visible_rect().size`, or instantiate into a `SubViewport`, which is not
clamped. (This is what test harnesses that offer an `instantiate_ui(scene, size)` helper are
doing for you.)

**`mouse_filter = IGNORE` on everything decorative.** A full-rect HUD `Control` that accepts
mouse input silently eats clicks meant for the game.

## Testing the UI headlessly

If the project has a test harness that can instantiate scenes offscreen, these are the
assertions worth writing — they catch the failures that are invisible in the file:

- the layout root's `size` equals the viewport size at two different resolutions (catches
  hard-coded offsets that only work at 1920×1080)
- every contract node name resolves (catches renames that silently break wiring)
- the public API is callable with no frames pumped and no errors (catches `_ready` code
  that assumed a viewport or a laid-out child)
- text is correct after calling a setter, with zero frames pumped (catches the tween-callback
  trap from idea 5 — this is the one that matters most)

## Verifying an install

`assets/smoke_test.gd` exercises the whole kit headlessly — it configures a HUD in the same
frame it creates it, checks every value is correct with zero frames pumped, asserts the card
queue keeps the *first* card, checks the prompt drops its keycap on a status message, and
verifies the pause menu's buttons are `PROCESS_MODE_ALWAYS` and its signals fire.

```bash
cp ~/.claude/skills/godot-game-ui/assets/smoke_test.gd <project>/smoke_test.gd
godot --headless --path <project> --script res://smoke_test.gd    # prints SMOKE: ALL PASS
```

Worth running once after scaffolding into a new project or after a Godot version bump —
it is about ten seconds and it distinguishes "the kit is broken" from "my wiring is wrong",
which is otherwise an annoying half hour.

## Reference

`references/patterns.md` — annotated code for the pieces most worth copying by hand when
you are not installing the whole kit: the roll-up counter, the queued card, the escalating
shout, the two-shape prompt, and the vector glyph. Read it when adapting rather than
scaffolding, or when a piece needs to behave differently from the template.

`assets/templates/` — the installable files themselves. Read the one you are adapting;
they are commented with the reasoning, not just the what.
