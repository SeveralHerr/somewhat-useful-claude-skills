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

`<skill dir>` below is this skill's own directory. Under a plugin install that is
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/skills/godot-game-ui/`, which is
version-pinned — resolve it from `installPath` in `~/.claude/plugins/installed_plugins.json`
rather than typing a path, and do not assume `~/.claude/skills/...`, which only exists for a
loose install.

```bash
python <skill dir>/scripts/scaffold_ui.py /path/to/project --palette clinical
godot --headless --path /path/to/project --import   # generates .uid sidecars + class cache
```

**Pick `--palette` from the game's tone, as part of installing — not as a later polish
step.** `references/palettes.md` carries six: `amber` (warm, lamplit, collecting),
`clinical` (cold, institutional, dry), `bloodmoon` (horror), `candy` (puzzle, casual,
children), `noir` (monochrome, stealth, detective), `verdant` (nature, farming, outdoors).
`--list-palettes` prints them without touching a project.

The default is `amber`, and it is a default rather than a recommendation. A UI nobody chose
a palette for comes out warm and golden whether the game is a horror piece or a spreadsheet
simulator, and "it all looks yellow" is the most common thing wrong with a UI built from
this kit. If none of the six fit, install the closest and edit the PALETTE block —
`palettes.md` ends with what to change first and which two pairs break if you get them
wrong.

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
puzzler differ by exactly sixteen constants — which is why `references/palettes.md` can hold
a whole art direction as a code block, and why `--palette` can swap one in at scaffold time
by substituting sixteen lines.

The rule is enforced rather than encouraged: `scripts/palette_lint.py` exits 1 on any colour
outside that block, in the kit's files and in yours. It exists because this idea failed
silently for two releases — a hard-coded colour looks *right* until someone re-skins, and by
then it is the palette that gets blamed. Note what it caught last: not screens retyping the
accent, but `ui_theme.gd` itself keeping the button, slot and badge fills as literals in its
own function bodies, below the block a palette substitutes. The file that owns the rule was
the file breaking it, and under the light-panelled `clinical` palette that put near-black text
on a near-black button at 1.41:1 contrast.

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

`UiMotion.enabled = false` forces that same null path everywhere, which is what makes it
one switch rather than a preference: with it off, a test can set state and assert on the
next line without pumping frames or waiting out a roll-up. `UiMotion.speed` scales every
duration. Anything animated that does not route through `UiMotion` is outside the switch and
will keep moving — which is exactly how a "motion off" build ends up with rolling counters
and a headless assertion that reads a number nobody wrote.

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
│ ▣ 12/40    ← stat pill stack        Kitchen complete  ←  │
│ ● 3/8         icon + count, one pill each      toast     │
│ $ 1,280                                    (transient)   │
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

### Announcements come in three sizes, and picking the wrong one costs attention

`set_prompt()` is the standing line under the crosshair — it says what pressing a key would
do, and it is the only one that persists. `toast()` is the corner line for something that
just became true and does not need acting on: "Kitchen complete", "Autosaved". `shout()`
takes the centre of the screen and interrupts, which is right for a combo and wrong for a
milestone. `show_card()` is the payoff moment and queues rather than interrupting.

Games that ship only a shout end up shouting about autosaves, and players learn to ignore
the centre of the screen — which is where the one message that mattered was going to appear.

### The crosshair has three states, not two

`set_crosshair_state(Cross.NEUTRAL | Cross.HOT | Cross.BLOCKED)`; `set_crosshair_hot(bool)`
still works and maps to the first two. `BLOCKED` shrinks and reddens rather than growing and
goldening, because a refusal has to differ from a target in *shape* as well as colour — the
crosshair is read peripherally while the player is looking at the object, not at it. Any game
that lets the player place, stack or hand over an object needs the third state; expressing
"you cannot put it there" by simply not turning the crosshair hot is indistinguishable from
pointing at nothing.

### The HUD can be read back, so tests do not walk its private nodes

`stat_text(id)`, `prompt_text()`, `prompt_key()`, `held_text()`, `hint_text()`,
`counter_text()`, `card_title()`, `toast_text()`, `crosshair_state()`, plus `layout_size()`
and `layout_scale()`. Assert against these rather than
`find_child("PromptLabel", true, false).text`: the `find_child` version couples every test to
this file's private build order, so renaming a node fails a dozen assertions with a null
dereference instead of a message. A write-only UI can only be checked by screenshot, and
screenshot checks are the ones that stop being run.

`counter_text()` is the exception worth knowing: it reports what is on screen, mid-roll
included. Assert on it with motion disabled, or after the roll has finished.

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

**And the signal has to be named after the intent, not the button.** "Quit to menu" on the
pause menu and "Main menu" on the results screen are the *same* request, so both emit
`menu_requested`. `quit_requested` means leave the application, and only `TitleScreen` — and
`PauseMenu` with `show_quit_to_desktop = true` — emits it. This kit shipped with the pause
menu's "Quit to menu" wired to `quit_requested`, an integrator wired that to
`get_tree().quit()`, and the button labelled *quit to menu* closed the game. A signal name
is documentation that the compiler will not check, so the two screens offering the same
choice must agree on it.

**The caption is the other half of that, and it belongs in an export.** If a button's text
and its meaning are separate concerns, then freezing the text into the template couples them
straight back together — from the other side. Every shell-screen button takes its caption
from an `@export` named after the signal it emits (`again_label`, `menu_label`,
`resume_label`, `quit_label`), defaulting to the generic wording. A game with a voice of its
own says "Clock out" instead of "Quit to menu" by setting a property, and a localised game
has somewhere to put the translated string other than a literal inside a script it forked.
This kit shipped with `ResultsScreen.heading` configurable while the two buttons underneath
it were not, which is how you end up with a deadpan-clinical end screen politely offering
"Play again".

**Anything the game might not be able to honour is gated by an export, sliders included.**
`PauseMenu` has `show_restart`, `show_quit_to_desktop`, `show_sensitivity` and
`show_volume`. The two sliders default to on because most games want them, but a kit cannot
know whether yours has camera look or an audio bus — and this one shipped building both
unconditionally, so a game that never connected `sensitivity_changed` put a slider in front
of the player that drags smoothly and changes nothing. That reads as a broken menu rather
than as a feature the game does not have, which is strictly worse than the control being
absent. Turning one off leaves its private field null; `set_values()` already null-checks
both, so the off state costs no other edit.

**Set `pivot_offset` from the current size on every punch**, not once at `_ready`. A Control
inside a container is resized after `_ready`, and a stale pivot makes the scale visibly
swing from a corner.

**Headless Godot clamps the main window to 64×64.** A UI test that sets
`root.size = Vector2i(1920, 1080)` and then asserts the layout is 1920×1080 fails against a
viewport that is really 64×64 — and it looks like a UI bug rather than a display-server one.
Assert against `get_visible_rect().size`, or instantiate into a `SubViewport`, which is not
clamped. (This is what test harnesses that offer an `instantiate_ui(scene, size)` helper are
doing for you.)

**`mouse_filter = IGNORE` on everything decorative — swept over the whole subtree, not set
per node.** `Panel`, `PanelContainer` and `Button` default to `STOP`, so one forgotten line
is enough, and the worst version of this failure has nothing to do with clicks: in a
**captured-cursor first-person game every mouse-motion event carries the viewport centre**,
which is exactly where the crosshair sits. GUI picking consumes it and marks it handled, so
`_unhandled_input` never runs and the player can walk and interact but **cannot turn their
head**. The camera controller is correct, which is why this costs an hour rather than a
minute. `GameHud._make_click_through()` walks the tree after every build (and after
`add_stat`/`build_tools`, which run later) so the default is safe and a clickable element
has to opt back in deliberately.

**A Container child cannot be scaled, so anything you punch needs a shell.**
`Container.fit_child_in_rect` reassigns position, size, rotation *and* scale on every layout
pass. `UiMotion.punch()` refuses such a node with a one-time `push_warning` rather than
animating a property that will be overwritten — silent refusal is worse, because the tint
that usually accompanies a punch still lands and the dead animation reads as "too subtle".
Wrap the node with `UiMotion.transform_shell(node)` and add the *shell* to the container: the
shell gets laid out and reset, the node inside it keeps its transform. The HUD does this for
its stat rows, tool slots and the big counter.

**Punches return to the RESTING scale, not to `1.0`.** Anything on a layer that `UiTheme.fit`
has scaled is not at 1.0, and snapping there mid-animation makes the element lurch to full
size before settling. `UiMotion` remembers each punched node's first-seen scale for this.

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

### Write the harness in the shape `smoke_test.gd` uses, or it passes without looking

A screen builds its children in `_ready`. The obvious harness — a `SceneTree` script with
`_init()` that news a screen up and calls `add_child(...)` — observes it **before** any of
that has run, so it walks an empty `Control`, finds nothing to assert against, and reports
ALL PASS. It is not a flaky test; it is a test of nothing, and it is indistinguishable from
a passing one. This has already cost a debugging detour here: a check written that way passed
against templates deliberately reverted to the buggy version.

Three things make the difference, all of them visible in `assets/smoke_test.gd`:

- `func _initialize()`, not `_init()` — `_initialize` runs after the tree exists
- `root`, not `get_root()`
- return `false` from `_process` for about three frames before asserting, so `_ready` and the
  first layout pass have both happened

Then confirm the harness can fail: break the thing you are checking, watch the assertion go
red, put it back. An assertion that has never failed has not been tested either.

Reading a colour back has its own trap: `Label.get_theme_color_override()` does not exist and
dies at runtime with `Invalid call. Nonexistent function`. The call that resolves an override
is `label.get_theme_color(&"font_color")`.

### What a runtime assertion cannot see: a hard-coded colour

Against the palette that shipped, `Color(0.06, 0.05, 0.07, 1.0)` is numerically identical to
the constant it should have read, so a test that walks the built tree reads the same
`ColorRect.color` whether the screen referenced `UiTheme.BACKDROP` or retyped its value. The
two only differ in the source, which is where the check has to be:

```bash
python <skill dir>/scripts/palette_lint.py <project>/scripts/ui
```

It exits 1 naming every `Color(...)` literal a palette change would not reach — in your
screens as well as the kit's. Run it after adding a screen of your own; that is when the
literals appear. Four shipped in this kit at once for exactly this reason, and the scaffolder
went on telling everyone the palette was the whole art direction the entire time.

### The contrast guarantee, and where it stops

The same script's second arm answers the other question about a palette: not "can a re-skin
reach this colour" but "can anyone read the text on it". It measures **sixteen ink/surface
pairs** the kit actually renders and exits 1 on any that lands under its bar.

```bash
python <skill dir>/scripts/palette_lint.py <project>/scripts/ui --contrast-table
```

Two things in that measurement are easy to get wrong, and getting either wrong produces
numbers that look authoritative and are not:

**Colour space.** Godot `Color` components are sRGB-encoded, and `Color.get_luminance()`
weights them with no transfer curve — it is a perceived-brightness helper, not WCAG relative
luminance. Skipping the piecewise transform understates every mid-tone badly: `bloodmoon`'s
primary button reads 2.65:1 that way and 4.14:1 correctly, and a bar set on the first number
condemns half this file. `UiTheme.relative_luminance()` and `UiTheme.contrast_ratio()` do it
properly and are there for your own screens too.

**Compositing.** Every surface here is translucent on purpose, so the ratio between an ink
constant and a fill constant describes a colour that is never on screen. In `amber` the
secondary button's raw `bg_color` gives 4.00:1 against TEXT; the button a player actually sees
— 0.95 alpha over a 0.88 panel over a 0.86 backdrop — is **11.32:1**. Where gameplay can still
show through the bottom of a stack, the pair is measured over both black and white and judged
on the worse end, so the figure is a bound rather than a guess about your game. The largest
leak in the kit is a HUD pill at 32%; the smallest is the pause menu's buttons at 0.084%, which
is less than one step of an 8-bit channel and is why the shell screens are effectively exact.

**The shipped six, worst case over any gameplay:**

| pair | bar | amber | clinical | bloodmoon | candy | noir | verdant |
|---|---|---|---|---|---|---|---|
| TEXT on a panel | 4.5 | 16.17 | 14.24 | 14.60 | 11.38 | 15.73 | 15.79 |
| TEXT on the backdrop | 4.5 | 11.45 | 9.10 | 12.50 | 10.56 | 12.56 | 12.39 |
| TEXT on a HUD pill | 4.5 | 6.02 | 6.83 | 6.31 | 5.01 | 6.29 | 6.26 |
| TEXT on a reward card | 4.5 | 12.25 | 12.35 | 11.67 | 8.52 | 12.22 | 12.13 |
| CHIP_INK on the keycap | 4.5 | 12.69 | 10.85 | 11.28 | 12.26 | 13.25 | 12.68 |
| secondary button, worst state | 4.5 | 7.10 | 10.88 | 6.35 | 5.09 | 6.66 | 6.67 |
| primary button, worst state | 4.5 | 7.75 | **4.52** | **4.79** | 5.12 | 6.61 | 7.35 |
| TEXT_DIM, worst surface | 3.0 | 3.57 | **3.15** | 3.35 | 3.42 | 3.61 | 4.27 |
| TEXT_FAINT, worst surface | 3.0 | 4.79 | 3.46 | **3.42** | 3.77 | 4.05 | 5.11 |

Two bars because the type ramp has two intentions. TEXT, the button inks and CHIP_INK carry
information and are held to WCAG AA 4.5. TEXT_DIM and TEXT_FAINT are the tiers the design
deliberately whispers with — a card kicker, a controls hint, a stat caption — and are held to
3.0. That is not a discount for failing the real bar; it is the reason **those two tiers must
never be the only place a fact appears.**

The bolded cells are the narrow passes. `clinical`'s pressed primary at 4.52 and its TEXT_DIM
at 3.15 are what a light-panelled palette costs; `bloodmoon`'s 4.79 is a red that was moved to
get there — see `references/palettes.md`.

**Where the guarantee stops, and what to check by hand.** The crosshair ring and any bare
`Glyph` drawn straight onto gameplay have no surface behind them at all, so no ratio exists for
them and nothing measures them. That is a real gap, not an oversight: the kit's answer there is
the outline-plus-shadow every label gets from `style_label` and the ring's own thickness, both
of which are geometry rather than colour. If your game is bright — snow, daylight, a white
lab — look at the crosshair and the HUD glyphs against your brightest scene, because that is
the one thing the lint will never tell you about.

## Verifying an install

`assets/smoke_test.gd` exercises the whole kit headlessly — it configures a HUD in the same
frame it creates it, checks every value is correct with zero frames pumped, asserts the card
queue keeps the *first* card, checks the prompt drops its keycap on a status message, and
verifies the pause menu's buttons are `PROCESS_MODE_ALWAYS` and its signals fire.

It also re-measures the button contrast against what Godot actually built — the real
`StyleBoxFlat.bg_color` and the real `font_color` override, composited down the real panel and
backdrop. That is deliberate duplication: `palette_lint.py` has to *replicate* `style_button`'s
derivation to measure it from the source, and that replica is the thing most likely to go stale
if you edit the theme. When the two disagree, the engine-side one is right.

```bash
cp <skill dir>/assets/smoke_test.gd <project>/smoke_test.gd
godot --headless --path <project> --script res://smoke_test.gd    # prints SMOKE: ALL PASS
python <skill dir>/scripts/palette_lint.py <project>/scripts/ui   # prints PALETTE: OK
```

Worth running once after scaffolding into a new project or after a Godot version bump —
it is about ten seconds and it distinguishes "the kit is broken" from "my wiring is wrong",
which is otherwise an annoying half hour.

## Reference

`references/patterns.md` — annotated code for the pieces most worth copying by hand when
you are not installing the whole kit: the roll-up counter, the queued card, the escalating
shout, the two-shape prompt, and the vector glyph. Read it when adapting rather than
scaffolding, or when a piece needs to behave differently from the template.

`references/palettes.md` — six ready-made palettes plus the two contrast pairs that break
when a palette is written by hand. `--palette` reads this file at scaffold time.

`scripts/palette_lint.py` — run over `assets/templates/` by default, or over a project's
`scripts/ui`. Two arms. The first names every colour a re-skin cannot reach; anything that
genuinely must be a literal takes `# palette-lint: ignore` on its line, and black, white and
greys are exempt already, since a drop shadow or a measured black-or-white ink is not a palette
choice and stays correct under every palette. A colour with a hue is not. The second arm
measures the sixteen ink/surface pairs the kit renders and fails any that is under WCAG AA;
`--contrast-table` prints them all, passing ones included, which is what to run while writing
a palette rather than after shipping one.

`assets/templates/` — the installable files themselves. Read the one you are adapting;
they are commented with the reasoning, not just the what.

## When this skill was wrong

This kit is used far more often than it is edited, so its defects are found here, in a game
project, and lost here too. If using it cost retries — a path in these instructions that did
not resolve, a step it failed to mention, an assertion in the templates it contradicts, a
Godot behaviour it should have warned about — hand that to **`skill-feedback-issue`**,
which files it against this repo with the evidence and the pinned version it broke in.

Two conditions, and they are the same ones that skill enforces: it has to have actually
gone wrong, and you have to be able to say what should change. "The nine ideas section is
long" is not an issue. "`scaffold_ui.py` at the path this file gives does not exist under a
plugin install" is.

If `skill-feedback-issue` is not installed, say what the fix would be and let the user
decide where it goes — do not edit the plugin cache, since the next `/plugin update`
overwrites it and the fix disappears without ever reaching the repo.
