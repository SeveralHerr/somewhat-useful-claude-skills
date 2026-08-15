---
name: godot-game-ui-juicy
description: Build Godot 4 game UI that MOVES — menus that grow in with an overshoot instead of appearing, rows that arrive in sequence, counters that punch, screens that shrink away, plus shake and screen flash. Everything the godot-game-ui kit ships (theme, HUD, pause, title, results) with a full motion layer on top and a global switch to turn it all off. Use this whenever the user wants their Godot interface to feel better rather than just exist — "the menu just pops in", "make the UI juicy", "add game feel", "animate the pause menu", "the HUD feels static/lifeless/flat", "add transitions between screens", "make it feel satisfying", "the UI is functional but boring" — and also whenever they are adding any Godot menu, HUD or screen and would obviously want it animated, even if they only said "add a pause menu". Prefer this over hand-rolling Tweens on Control nodes: UI animation in Godot fails in ways that produce no error at all (Containers silently reset their children's scale, Tweens freeze on a paused tree, half-finished entrances leave the UI invisible headlessly), and this kit has those failures already solved and tested.
---

# Godot 4 Game UI — Juicy

Everything in the `godot-game-ui` kit, plus the motion that makes it feel like a game rather
than a form. Same code-only constraint: **no image files, no font files, no `.tres`, no
`.tscn`.**

## Fast path

`<skill dir>` below is this skill's own directory. Under a plugin install that is
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/skills/godot-game-ui-juicy/`, which
is version-pinned — resolve it from `installPath` in `~/.claude/plugins/installed_plugins.json`
rather than typing a path, and do not assume `~/.claude/skills/...`, which only exists for a
loose install.

```bash
python <skill dir>/scripts/scaffold_juicy_ui.py /path/to/project --palette bloodmoon
godot --headless --path /path/to/project --import   # generates .uid sidecars + class cache
```

Then verify — this takes fifteen seconds and separates "the kit is broken" from "my wiring
is wrong":

```bash
cp <skill dir>/assets/smoke_test.gd <project>/smoke_test.gd
cp <skill dir>/assets/juice_test.gd <project>/juice_test.gd
godot --headless --path <project> --script res://smoke_test.gd   # SMOKE: ALL PASS
godot --headless --path <project> --script res://juice_test.gd   # JUICE: ALL PASS
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

`--only`, `--dest` and `--force` work as in the plain kit; dependencies resolve
automatically.

## Relationship to `godot-game-ui`

This is a **drop-in superset**. `ui_theme.gd` and `ui_motion.gd` are byte-identical to the
plain kit, all new motion lives in one new file (`ui_juice.gd`), and the four screens gain
entrance/exit hooks. Every existing call signature still works, so a project already using
the plain kit upgrades by scaffolding over it — the plain kit's own smoke test passes against
this one unchanged.

Use the plain kit when a project wants static UI, deterministic frames, or the smallest
possible surface. Use this one otherwise. The two are not meant to be installed side by side:
the class names collide, which is the point — it is an upgrade, not an alternative.

The one API addition worth knowing: screens now have `dismiss()`, which plays the exit and
then frees. `queue_free()` still works and simply skips the animation.

## The four ideas that make motion read as juice

### 1. Entrances overshoot; exits do not

An element that arrives past its resting size and settles back reads as physical. The same
curve on the way out reads as hesitation — the player has already decided, and anything that
delays the decision feels like input lag rather than polish.

So entrances use `TRANS_BACK` / `EASE_OUT` over ~0.34s, and exits use a plain accelerating
curve over ~0.13s. **That asymmetry is most of the difference between "animated" and
"juicy."** It is also the thing people get wrong first, because a symmetric animation looks
more correct written down.

Related: emit the signal on the click, not at the end of the exit. The game should resume the
instant Resume is pressed, with the menu shrinking away over the top of it.

### 2. Things arrive in sequence, not together

Four buttons fading in together is one event. The same four at 45ms apart is a menu
assembling itself, and it costs one delay parameter. Keep the step small — past about 80ms it
stops reading as a single motion and starts reading as a slow interface.

The results screen is where this pays off most: a ripple across the collection grid makes the
player's eye travel the whole collection, including the gaps that are the reason to play
again. A grid that simply appears gets skimmed.

### 3. One property, one animation

Two tweens writing the same property is a stutter, not extra juice. The title screen
deliberately does not `breathe()` its title, because `pop_in` already owns that scale — the
idle wobble is on `rotation` instead, which is why the two can coexist.

When something needs to both punch and move, animate different properties or sequence them.

### 4. Motion must be switchable

`UiJuice.enabled = false` makes every function resolve instantly to its final state, and
`UiJuice.speed` scales all durations at once. Some players need that, some builds need
deterministic frames, and a codebase where motion cannot be turned off has to be edited in a
hundred places the first time someone asks.

The disabled path is the same code path a headless run takes, so the tests exercise it and it
does not rot.

**One switch, not two.** `UiJuice.enabled` and `UiJuice.speed` are views onto
`UiMotion.enabled` / `UiMotion.speed`; setting either name sets the same flag. This kit
shipped with them as separate flags, and the result was a "motion off" build whose counters
still rolled, whose progress bars still slid, and whose headless assertions two frames after
`set_counter()` read a mid-roll number that nothing explained. A switch with an exception is
not a switch. If you add a motion helper of your own, route it through `UiMotion.tween()` or
it will sit outside the switch in exactly the same way.

## The Godot-specific traps, all of which fail silently

These are why this skill exists. None of them produce an error; all of them look like the
tween "just didn't run."

### Containers reset their children's scale and rotation — every layout pass

`Container.fit_child_in_rect` sets its children's position, size, **rotation and scale** every
time it lays out. A tween on any of those properties is overwritten before the frame is drawn.
Nothing errors, the tween reports itself as running, and the element simply never moves.

This is the one that will cost you an afternoon. It is why the pause panel is anchored with
`PRESET_CENTER` + `GROW_DIRECTION_BOTH` rather than parented to a `CenterContainer` — visually
identical, but a `CenterContainer` child cannot be scale-animated at all.

`UiMotion.can_transform(control)` is the check (`not (get_parent() is Container)`) —
`UiJuice.can_transform` forwards to it, so both `punch()`es obey one rule. `stagger()` uses it
to fall back to a fade-only cascade for container children automatically. Alpha is always
safe: `modulate` is not a transform.

**The escape hatch is `UiMotion.transform_shell(node)`**: it wraps the node in a plain
`Control` and returns the wrapper to add to the container in its place, so the shell absorbs
the layout pass while the node inside keeps its transform. Use it whenever an element that
must be punched has to live in a `VBox`/`HBox`/`GridContainer` — which is most of them. The
HUD shells its stat rows, tool slots and big counter for exactly this reason; without them,
`flash_stat()` and `set_active_tool()` were tinting and nothing else, and this kit shipped
that way for two versions because the tint made it look like the punch was just subtle.

A refused punch now emits a one-time `push_warning` naming the node. That is the whole
difference between a five-minute fix and a defect that survives review.

**Symptom to recognise:** the thing fades in correctly but never grows.

### A HUD that is not click-through kills first-person mouse look

Not a motion bug, but it lands in the same session and it is the most expensive one in this
kit's history. `Panel` and `PanelContainer` default to `MOUSE_FILTER_STOP`. In a
captured-cursor game every `InputEventMouseMotion` carries the viewport centre — where the
crosshair sits — so GUI picking consumes it, marks it handled, and `_unhandled_input` never
runs. The player can walk, interact and place things, but cannot turn their head, and the
camera controller they go and read is correct.

`GameHud` now sweeps its whole subtree to `MOUSE_FILTER_IGNORE` after every build. If you
build your own HUD component, do the same rather than setting the flag node by node — the
defect is one forgotten line away, permanently.

**Symptom to recognise:** everything works except looking around.

### A Tween on a paused tree freezes unless you say otherwise

A Tween's pause mode defaults to `TWEEN_PAUSE_BOUND`, meaning it follows the process mode of
the node that created it. A pause menu animating itself in while `get_tree().paused` is true
therefore freezes on frame one — the panel sits at 86% scale, half transparent, forever.

`UiJuice.tween(host, true)` sets `TWEEN_PAUSE_PROCESS`, and everything in the kit routes
through it. Note this is a *separate* problem from the plain kit's `PROCESS_MODE_ALWAYS` rule:
you need both, and fixing only the process modes gets you a menu whose buttons work but whose
entrance is frozen.

**Symptom to recognise:** the pause menu appears at the wrong size and stays there.

### Set the start state only after you know a tween exists

Every entrance sets `modulate.a = 0` and a small scale before animating to the resting values.
Do that *before* checking whether a tween could be created and a headless run ends with a
fully built, entirely invisible UI — no error, no failed assertion, just nothing on screen.

Every function in `ui_juice.gd` has the same shape: ask for the tween, return early with the
final state applied if there isn't one, and only then arm. `juice_test.gd` asserts this
directly by building a menu, pumping zero frames, and requiring every Control to be at
alpha 1.

### `pivot_offset` has to track size, not be set once

A Control inside a Container is laid out *after* `_ready`, so a pivot computed at `_ready` was
computed against a size of zero and the element visibly swings out from its top-left corner.
`UiJuice.center_pivot()` connects to the `resized` signal instead, so the pivot is right on
every frame the layout changes — including the first one and including a window resize
mid-animation.

### Animate relative to the resting scale, never to 1.0

The kit scales whole screens for display resolution (see `UiTheme.fit`), so a screen's resting
scale is often 0.667 or 2.0 rather than 1.0. An exit that tweens `scale` to a literal
`Vector2.ONE * 0.94` makes a 4K UI lurch to a quarter size before shrinking. Every function
here captures `target.scale` first and animates relative to it.

`UiMotion.punch()` and `pop_in()` obey this too — they remember each node's first-seen scale
rather than snapping to `Vector2.ONE`. Remembering it beats re-reading `scale` at call time:
a second punch landing while the first is still settling would otherwise treat the inflated
value as the resting one, and the element creeps a little larger on every hit.

## Tuning

The `FEEL` block at the top of `ui_juice.gd` is the whole personality:

| Constant | Default | Raise it to… |
|---|---|---|
| `IN_TIME` | 0.34 | make entrances more languid and deliberate |
| `OUT_TIME` | 0.13 | (rarely) — keep it well under `IN_TIME`, see idea 1 |
| `STAGGER_STEP` | 0.045 | space a cascade out; past ~0.08 it reads as slowness |
| `POP_FROM` | 0.86 | 0.7 for a punchier arrival, 0.95 for a subtle one |
| `PUNCH_TIME` | 0.26 | lengthen the elastic settle on counters and slots |
| `speed` | 1.0 | 0.7 for arcade snap, 1.3 for a calm, weighty feel |

Retune constantly while a game finds its feel — that is why juice lives in its own file
rather than mixed into `ui_motion.gd`, whose safety rules you touch almost never.

## The juice verbs

Reach for these when the player should *feel* something rather than read it:

```gdscript
hud.flash_stat(&"coins", UiTheme.GOOD)     # tint + squash: something happened here
hud.set_active_tool(2)                     # punches the selected slot
hud.toast("Kitchen complete")              # corner line, no interruption
hud.set_crosshair_state(GameHud.Cross.BLOCKED)  # "not there" — see the plain kit's SKILL.md
hud.shake(9.0)                             # damage, refusal, impact
hud.flash_screen(Color(1, 0.2, 0.2, 0.35)) # full-screen pulse
pause.dismiss()                            # exit animation, then free
```

And the primitives, for your own UI:

```gdscript
UiJuice.enter(host, control, UiJuice.Enter.POP)     # or RISE / DROP
UiJuice.exit_then(host, control, control.queue_free)
UiJuice.stagger(host, vbox.get_children())
UiJuice.punch(host, control, 0.16)                  # squash-and-stretch
UiJuice.shake(host, control, 9.0)
UiJuice.flash(host, Color(1,1,1,0.5))
UiJuice.breathe(host, control)                      # slow idle loop
vbox.add_child(UiMotion.transform_shell(row))       # so `row` can be punched at all
```

Squash-and-stretch is deliberately anisotropic — wider than it is tall on the way out. A
uniform punch reads as "this got bigger"; an anisotropic one reads as something absorbing an
impact, which is what you actually want when a counter ticks.

Use `shake` sparingly and briefly. A shake that outlasts the event it describes stops meaning
"impact" and starts meaning "the UI is broken". Shaking the HUD when the *world* should shake
is the most common misuse.

## Wiring the shell screens

`PauseMenu` emits `resume_requested`, `restart_requested`, `menu_requested`,
`sensitivity_changed`, `volume_changed` — and `quit_requested` only when you set
`show_quit_to_desktop = true`. `ResultsScreen` emits `again_requested` and `menu_requested`;
`TitleScreen` emits `play_requested` and `quit_requested`.

`menu_requested` is the same intent on both screens on purpose, so wiring them to one handler
is correct. Earlier versions had the pause menu's "Quit to menu" button emit `quit_requested`;
integrators wired that to `get_tree().quit()`, and the button labelled *quit to menu* closed
the game. If you are upgrading a project that connected `pause.quit_requested`, that is the
one call site to change.

## Reference

`references/motion.md` — the timing and curve reference: which `TRANS_` to pick for which
kind of motion, how long each class of animation should last, and the annotated pattern for
adding a new juice verb that degrades correctly. Read it when tuning beyond the table above
or writing your own animated component.

`references/palettes.md` — six ready-made palettes plus the two contrast pairs that break
when a palette is written by hand. `--palette` reads this file at scaffold time.

`assets/templates/` — the installable files. `ui_juice.gd` is the one worth reading in full;
it is commented with the reasoning rather than the mechanics.
