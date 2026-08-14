#!/usr/bin/env python3
"""Drop the Godot game-UI kit into a project.

Copies the template scripts into <project>/scripts/ui/ (or --dest), refusing to clobber
files that already exist unless --force is given, then prints the integration snippet for
whatever was installed.

The templates are plain .gd files with `class_name` declarations and no autoloads, so
installing them is genuinely just a copy — there is no project.godot to patch and nothing
to register. The one post-step Godot requires is an import pass, which is what generates
the .uid sidecars and the global class cache; the script reminds you rather than trying to
synthesise uids itself, because a hand-made uid that collides is much worse than a missing
one.

Usage:
    python scaffold_ui.py /path/to/godot/project
    python scaffold_ui.py . --only hud,theme
    python scaffold_ui.py . --dest ui --force
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# name -> (template filename, depends on, one-line description)
_UI = ("theme", "motion", "juice")
PIECES: dict[str, tuple[str, tuple[str, ...], str]] = {
    "theme":   ("ui_theme.gd",       (),                  "palette, StyleBoxes, vector Glyph icons"),
    "motion":  ("ui_motion.gd",      (),                  "headless-safe tweens, roll-up numbers"),
    "juice":   ("ui_juice.gd",       ("motion",),         "entrances, exits, staggers, punch, shake, flash"),
    "hud":     ("hud.gd",            _UI,                 "in-game HUD (stats, prompt, reward card)"),
    "pause":   ("pause_menu.gd",     _UI,                 "pause overlay, animated in and out"),
    "title":   ("title_screen.gd",   _UI,                 "title screen with staggered entrance"),
    "results": ("results_screen.gd", _UI,                 "end-of-run summary + rippling collection grid"),
}

SNIPPETS: dict[str, str] = {
    "hud": """\
# --- HUD ---------------------------------------------------------------------
var hud: GameHud = GameHud.new()
add_child(hud)

hud.add_stat(&"score", UiTheme.Glyph.Kind.STAR)
hud.add_stat(&"coins", UiTheme.Glyph.Kind.COIN)
hud.build_tools([UiTheme.Glyph.Kind.MAGNIFIER, UiTheme.Glyph.Kind.BOLT])

# then, wherever your state changes:
hud.set_stat(&"score", score)
hud.set_stat(&"coins", coins, func(v: float) -> String:
    return "$" + UiMotion.group_digits(int(round(v))))
hud.set_counter(carried, capacity)
hud.set_progress(float(done) / float(total))
hud.set_prompt("Press [E] to open")     # "" hides it
hud.set_crosshair_hot(target != null)
hud.shout("NICE!", UiTheme.ACCENT, 0.8)
hud.show_card("item found", "Golden Key", "Rare", "It opens something.", UiTheme.ACCENT)

# juice verbs — reach for these when the player should FEEL something, not read it:
hud.set_active_tool(2)                        # punches the slot
hud.flash_stat(&"coins", UiTheme.GOOD)        # tint + squash
hud.shake(9.0)                                # damage, refusal
hud.flash_screen(Color(1, 0.2, 0.2, 0.35))    # full-screen pulse
""",
    "pause": """\
# --- Pause -------------------------------------------------------------------
var pause: PauseMenu = PauseMenu.new()
add_child(pause)
get_tree().paused = true
# Unpause on the click, dismiss() for the exit animation over the top of it. Resuming only
# after the animation would make the menu feel laggy rather than juicy.
pause.resume_requested.connect(func() -> void:
    get_tree().paused = false
    pause.dismiss())
pause.restart_requested.connect(_on_restart)
pause.quit_requested.connect(_on_quit_to_menu)
pause.sensitivity_changed.connect(func(v: float) -> void: player.mouse_sensitivity = 0.0025 * v)
pause.volume_changed.connect(func(v: float) -> void:
    AudioServer.set_bus_volume_db(0, linear_to_db(maxf(v, 0.0001))))
""",
    "title": """\
# --- Title -------------------------------------------------------------------
var title: TitleScreen = TitleScreen.new()
title.title = "MY GAME"
title.taglines = PackedStringArray(["A game about something.", "Another tagline."])
title.controls_hint = "WASD move  ·  Mouse look  ·  E interact  ·  Esc pause"
title.play_requested.connect(_start_game)
title.quit_requested.connect(func() -> void: get_tree().quit())
add_child(title)
""",
    "results": """\
# --- Results -----------------------------------------------------------------
var results: ResultsScreen = ResultsScreen.new()
add_child(results)
results.present(
    [{"label": "Score", "value": str(score)},
     {"label": "Time",  "value": "%d:%02d" % [secs / 60, secs % 60]}],
    # optional collection grid:
    [{"name": item.display_name, "found": owned.has(item.id),
      "color": item.color, "tint": item.rarity_color(),
      "tooltip": "%s - %s" % [item.display_name, item.flavour]} for item in catalogue],
    "Every item found." if complete else "%d left to find." % remaining
)
results.again_requested.connect(_start_game)
results.menu_requested.connect(_goto_menu)
""",
}


def resolve(names: list[str]) -> list[str]:
    """Expand the requested pieces to include their dependencies, in install order."""
    wanted: set[str] = set()
    for n in names:
        if n not in PIECES:
            sys.exit(f"error: unknown piece {n!r}. Choose from: {', '.join(PIECES)}")
        wanted.add(n)
        wanted.update(PIECES[n][1])
    return [k for k in PIECES if k in wanted]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path, help="Godot project directory (contains project.godot)")
    ap.add_argument("--dest", default="scripts/ui",
                    help="destination relative to the project (default: scripts/ui)")
    ap.add_argument("--only", default="all",
                    help="comma-separated subset: " + ",".join(PIECES) + " (default: all)")
    ap.add_argument("--force", action="store_true", help="overwrite files that already exist")
    args = ap.parse_args()

    project: Path = args.project.resolve()
    if not (project / "project.godot").is_file():
        sys.exit(f"error: no project.godot in {project} - point this at a Godot project root.")

    templates = Path(__file__).resolve().parent.parent / "assets" / "templates"
    if not templates.is_dir():
        sys.exit(f"error: templates not found at {templates}")

    names = list(PIECES) if args.only.strip() == "all" else \
        resolve([n.strip() for n in args.only.split(",") if n.strip()])

    dest = project / args.dest
    dest.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    skipped: list[str] = []
    for name in names:
        filename = PIECES[name][0]
        target = dest / filename
        if target.exists() and not args.force:
            skipped.append(filename)
            continue
        shutil.copyfile(templates / filename, target)
        written.append(filename)

    rel = dest.relative_to(project).as_posix()
    print(f"Godot UI kit -> {project}/{rel}\n")
    for f in written:
        piece = next(k for k, v in PIECES.items() if v[0] == f)
        print(f"  + {f:<20} {PIECES[piece][2]}")
    for f in skipped:
        print(f"  = {f:<20} already exists (use --force to overwrite)")

    if not written and not skipped:
        print("  (nothing selected)")
        return 0

    print(
        "\nNext: run an import pass so Godot generates the .uid sidecars and registers the\n"
        "class_names, otherwise every reference to UiTheme/UiMotion fails to resolve:\n"
        "\n    godot --headless --path . --import\n"
    )

    installed = {k for k in names if k in SNIPPETS and PIECES[k][0] in written}
    if installed:
        print("Integration:\n")
        for name in PIECES:
            if name in installed:
                print(SNIPPETS[name])

    print(
        "Re-skin by editing the PALETTE / TYPE / METRICS blocks at the top of ui_theme.gd.\n"
        "Nothing else hard-codes a colour, so that block is the whole art direction.\n"
        "\n"
        "Tune the motion in the FEEL block at the top of ui_juice.gd. `UiJuice.enabled =\n"
        "false` disables every animation globally (accessibility, or deterministic tests) and\n"
        "`UiJuice.speed` scales all durations at once.\n"
        "\n"
        "Resolution: the UI scales itself by viewport height / UiTheme.REFERENCE_HEIGHT\n"
        "(1080 by default), so it holds its proportions on 720p, 1080p, 4K and ultrawide\n"
        "with nothing to configure. If the whole UI looks uniformly too small or too big\n"
        "but correctly proportioned, REFERENCE_HEIGHT is the one number to change -- under\n"
        "stretch/canvas_items it should match your project's BASE viewport height."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
