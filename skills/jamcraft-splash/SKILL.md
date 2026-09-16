---
name: jamcraft-splash
description: Add the Jamcraft studio logo splash intro to a Godot 4 game. Use this whenever the user wants a Jamcraft logo, company splash, studio intro, boot logo, "made by" screen or start-screen intro in a Godot project — "add my logo to startup", "put the Jamcraft splash in", "show our logo before the title screen" — and when setting up a new Godot game that should open like the other Jamcraft games, even if the logo is not mentioned by name. Godot only; not for web pages, itch.io pages or store art.
---

# Jamcraft splash

Drops a ready-made logo intro (`JamcraftSplash`) into a Godot 4 project. The component is one
self-contained script plus one PNG, so integration is mostly deciding where it runs.

Bundled assets (next to this file):
- `assets/jamcraft_splash.gd` — `class_name JamcraftSplash extends CanvasLayer`; builds its own
  nodes, no .tscn, UIDs or autoloads.
- `assets/jamcraft_logo.png` — 1920x1080, logo centred on a plain black background.

What the component gives you:
- `signal finished`, emitted once; the node frees itself afterward.
- `@export var logo: Texture2D` — falls back to `res://images/jamcraft_logo.png`.
- `@export var next_scene: PackedScene` — if set, calls `change_scene_to_packed` when done.
- `@export var hold_time`, `@export var skippable := true`, `@export var background_color := Color.BLACK`.
- About 1.5–2 s: logo pops in with scale/fade and a brief flash, holds, fades out. Any key,
  click, joypad button or touch skips it. Runs while the tree is paused.

## 1. Read the project

- Find `project.godot` and its `run/main_scene`. It may be `uid://...` rather than `res://...`;
  resolve a uid by grepping `.tscn` headers (`[gd_scene ... uid="uid://..."]`) for it.
- Work out how the title/start screen is reached: is it the main scene, loaded by a boot scene,
  or shown by an autoload? Note the scripts folder layout (`scripts/ui/`, `src/`, flat, ...).
- Look for an existing static splash or `application/boot_splash/*` image that would show a
  logo too, so the player doesn't see it twice.

## 2. Copy the assets

- `assets/jamcraft_logo.png` → `res://images/jamcraft_logo.png` (the script's fallback path;
  if you put it elsewhere, set `logo` explicitly).
- `assets/jamcraft_splash.gd` → the project's UI scripts folder, e.g. `res://scripts/ui/`.
- Don't hand-write `.import` or `.uid` files; Godot generates them on the next import (step 4).

## 3. Integrate — pick one pattern

**A. Splash as the main scene** — best when the game boots straight into a title scene and
you'd rather not touch that scene's code.

1. Create `res://scenes/boot_splash.tscn` with a single root node of type `JamcraftSplash`
   (script attached), and set `next_scene` to the old main scene via an `ext_resource` that
   references it by `path="res://..."`. A path reference survives UID regeneration; omit the
   `uid=` attribute rather than inventing one.
2. Point `run/main_scene` in `project.godot` at the new scene. Use `res://scenes/boot_splash.tscn`;
   Godot accepts a res path there and may rewrite it to a uid itself later, which is fine.

**B. Overlay inside the existing main/title scene** — best when the title scene already does
startup work (music, save load) you want running underneath, or when there is no single scene
to redirect to.

```gdscript
func _ready() -> void:
	title_menu.hide()                      # or set process_input / mouse_filter off
	var splash := JamcraftSplash.new()
	add_child(splash)
	await splash.finished
	title_menu.show()
	title_menu.grab_focus_first_button()   # whatever the project already uses
```

Hold the menu's input until `finished`; otherwise the key press that skips the splash also
activates the focused button underneath.

Either way, remove or disable any older static splash/logo so it isn't shown twice. Leave
Godot's engine boot splash alone unless the user asks — it is a project setting, not a scene.

## 4. Verify

Run from the project root (use the Godot executable the project already uses; on Windows it
may be `godot_console.exe` or a full path). A newer Godot than `config/features` rewrites
`project.godot` on import (version bump, uid autoloads); check `git diff project.godot` after and revert that churn.

1. Import and catch script errors headlessly:
   `godot --headless --path . --import` then `godot --headless --path . --quit-after 120`.
   Any `SCRIPT ERROR`, `Parse Error` or "Could not find type JamcraftSplash" is a failure.
   The class_name cache only updates on import, which is why import runs first.
2. Look at it: `godot --path . --write-movie <tmp>/f.png --fixed-fps 30 --quit-after 75`
   writes numbered PNGs. Read roughly frames 5, 20, 45 and 70: the logo should be scaling in,
   fully visible, then fading, and the last frames should show the title screen.
3. Delete the movie frames and any throwaway test scenes. Keep the `.import`/`.uid` files Godot
   generated for the new assets — they belong in the repo.

Report which pattern was used, the files added or changed, and what the frames showed.
