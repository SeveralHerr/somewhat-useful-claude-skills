---
name: kenney-asset-kit
description: Work with Kenney asset packs (kenney.nl) - the modular 3D kits, 2D tilesheets, UI packs and audio. Measures a kit's real grid unit, pivot convention, model facing and module widths straight out of the glTF instead of guessing at them, and gives a bounding-box-anchored placement pattern (Godot 4 helper included). Use this whenever the user mentions Kenney, or names an asset kit (Furniture Kit, Nature Kit, City Kit, Space Kit, Castle Kit, Modular Dungeon, Tower Defense Kit...), or is assembling a level, room, house, dungeon or town out of prefab 3D models, or is snapping models to a grid - and especially at the symptoms of guessed conventions: furniture facing into walls, tiles that will not line up, models floating or sunk into the floor, pieces overlapping, "which way does this model face". Also covers Kenney 2D tilesheets, sprite atlases and UI packs.
---

# Kenney asset kits

Kenney ships ~50 modular 3D kits plus 2D, UI and audio packs. Every kit is
internally consistent and **no two kits agree with each other**. The Furniture
Kit puts origins in a corner; the Modular Dungeon Kit centres them. Both are
"the Kenney convention".

So the rule is: **measure the kit you are actually using.** A convention carried
over from the last kit produces a scene that renders plausibly and is wrong
everywhere — furniture backed into walls, tiles half a unit off — and you will
spend longer un-guessing it than measuring would have taken.

## 1. Probe the kit

`kenney_probe.py` lives in this skill's `scripts/` directory — run it from there,
or give its absolute path:

```bash
python <skill dir>/scripts/kenney_probe.py "<path to the kit directory>"
python <skill dir>/scripts/kenney_probe.py "<kit>" --models wall floorFull bedDouble
```

Standard library only — no engine, no import step, nothing written. It walks the
glTF node hierarchy and applies node transforms, which matters: Kenney models
routinely carry a scale on the node, so raw accessor min/max is wrong (it reports
the Furniture Kit's double bed as 1.62 x 1.91 when it is 0.96 x 1.13).

Point it at the kit folder; it finds the model directory itself and prefers
`GLB format` over `GLTF format` over the rest.

## 2. Read the report

| Line | What to do with it |
|---|---|
| `STRUCTURAL PIECES ... measure` | The grid unit is normally the value recurring most; larger values are double-width variants. Cross-check against the next line — a real grid shows the same number in both. |
| `MOST COMMON FOOTPRINT` | On a prop or character kit this is the only size signal, and it means nothing structural. |
| `PIVOT` | Decides your placement formula. Corner-pivot: a tile at `(col, 0, -row)` covers cell (col,row). Centred: `(col+0.5, 0, -row-0.5)`. Never carry one across kits. |
| `BASE` | Where the model's lowest point sits. Non-zero means the kit expects a floor at that offset, not at 0. |
| `FACING` | The kit's front axis, inferred from where the tall mass sits — a backrest, headboard or cistern is at the *back*. Heuristic: if it prints a split-vote warning, check two obvious models by hand. |
| `COMMON FOOTPRINT WIDTHS` | A spike well below the grid unit is the kit's **module step** — the Furniture Kit's 0.43 kitchen units, wall segments, shelf runs. Lay runs out on that step, not on the grid. |
| `TEXTURES` | `external` means the kit is textured, not vertex-coloured: copy the `Textures/` folder next to the models or everything imports white. |

Kenney's world scale is roughly **1 unit ≈ 2 m** in the interior kits — a 1.29-unit
wall is a 2.5 m ceiling. Sanity-check your room sizes against that before
building a mansion by accident.

## 3. Place by bounding box, not by pivot

Once measured, do not hand-compute offsets per model. Anchor to the instantiated
model's real AABB and say what you mean — "this bathtub's south edge against
that wall". It survives every pivot convention, so the same code works on the
next kit.

```gdscript
## Grid space: gx runs +X, gz runs south (-Z). Grid point (gx, gz) is world (gx, y, -gz).
## anchor combines "n"/"s" and "e"/"w"; an omitted axis is centred.
func place(node: Node3D, gx: float, gz: float, rot_deg := 0.0, anchor := "c", y := 0.0) -> void:
	node.rotation = Vector3(0.0, deg_to_rad(rot_deg), 0.0)
	var box := Transform3D(node.basis, Vector3.ZERO) * local_aabb(node)
	var c := box.get_center()
	var here := Vector3(c.x, box.position.y, c.z)   # where the anchor sits now
	if anchor.contains("w"): here.x = box.position.x
	elif anchor.contains("e"): here.x = box.end.x
	if anchor.contains("n"): here.z = box.end.z     # north = smaller gz = LARGER world Z
	elif anchor.contains("s"): here.z = box.position.z
	node.position = Vector3(gx, y, -gz) - here

## Geometry only. A Light3D is a VisualInstance3D too, and an OmniLight3D's AABB is
## a cube of twice its range - parent one to a ceiling lamp and the lamp measures
## 7 units across, silently corrupting every placement that reads its box.
static func local_aabb(root: Node3D) -> AABB:
	var out := AABB()
	var found := false
	var stack: Array = [[root, Transform3D.IDENTITY]]
	while not stack.is_empty():
		var e: Array = stack.pop_back()
		var n: Node = e[0]
		var t: Transform3D = e[1]
		if n is GeometryInstance3D:
			var b: AABB = t * (n as GeometryInstance3D).get_aabb()
			out = b if not found else out.merge(b)
			found = true
		for c in n.get_children():
			stack.push_back([c, t * ((c as Node3D).transform if c is Node3D else Transform3D.IDENTITY)])
	return out
```

With `FACING` known, rotation becomes a compass. If the kit fronts +Z and your
grid's north is -Z in world space, then `rot 0` faces north, `90` east, `180`
south, `-90` west — so **a piece pushed against the south wall wants rot 0, not
180**. Write that sentence into your own code as a comment; getting it inverted
is the single most common way a scene ends up backwards.

Two more helpers worth having, both trivial once `local_aabb` exists:
`top_of(node)` (world Y of the box top — for standing a lamp on a nightstand)
and `center_of(node)` (grid-space footprint centre — so a prop lands on its host
instead of hanging off the front edge).

## 4. Check the layout as data, not as screenshots

A misplaced model renders as a perfectly plausible picture. After building,
assert the arrangement numerically: every item's footprint inside its intended
room rectangle, and no two floor-standing footprints overlapping (exempt flat
rugs and anything resting on furniture).

This is cheap and it is what actually catches things. On one 93-item build it
found five bugs no screenshot showed: a lamp measuring 7 units across, a rug
crossing two walls, a fridge 0.09 wider than the run it sat in, opaque
auto-generated node names, and an entire kit rotated backwards.

## Gotchas

- **Set `name` after `add_child()`, not before.** `add_child()` replaces a
  colliding name with an opaque `@Node3D@117`; assigning afterwards gets you a
  readable `kitchenCabinet2`. With 90 instances this decides whether any
  diagnostic output is readable.
- **Sub-parts are separate nodes.** Doors, drawers, lids and pillows are named
  children (`--models` prints them), so you can animate a fridge door or hide a
  bed's cover without touching the mesh.
- **Untextured kits are vertex-flat and pale.** Base colours run high (Furniture
  Kit wood is 0.90/0.60/0.39), so sun + fill + ambient much above ~1.0 of total
  irradiance clips every surface to white and the palette disappears. If a
  render looks washed out, that is the cause, not the models.
- **Several export formats ship per kit.** Prefer GLB/glTF. The OBJ and DAE
  copies exist for older pipelines and lose the node hierarchy.
- **Kenney assets are CC0** — attribution appreciated, not required. Copy the
  kit's `License.txt` alongside the assets anyway.

## 2D, UI and audio packs

No measuring needed, but the 2D packs come in two shapes and they want different
treatment. Check which one you have before writing any region maths.

**Tilemap packs** (e.g. 1-Bit Platformer Pack) — a uniform grid:
- `Tilemap/*.png` — the grid sheet, usually in `_packed` (no padding) and padded
  variants. Take `_packed` unless you hit bleeding at non-integer zoom.
- `Tilesheet.txt` — plain text stating the tile size (`Tile size • 16px × 16px`).
  Read it; do not count pixels.
- `Tiles/` — the same tiles as individual PNGs.
- In Godot this is a `TileSetAtlasSource` with `texture_region_size` set to that
  tile size, plus `separation`/`margin` if you took the padded sheet.

**Sprite packs** (e.g. Abstract Platformer, Animal Pack) — irregular regions:
- `PNG/` — every sprite as its own file. **Prefer these.** Godot imports loose
  PNGs directly and the atlas region maths disappears entirely.
- `Spritesheet/*.png` + `*.xml` — a `<TextureAtlas>` of named `<SubTexture>`
  rects. Only worth parsing if you specifically need one draw call.
- `Vector/` — SVG sources, for when you need the art at arbitrary resolution.

**UI packs** additionally carry `Font/` (Kenney Future .ttf) and `Sounds/`, and
their `PNG/` is split by colour theme (Blue, Green, Grey...). The panels and
buttons are drawn for **9-slice**: read the corner radius off the sprite and set
it as the inset on a `NinePatchRect` or `StyleBoxTexture`. Stretching them as
plain textures smears the corners, and that is what makes Kenney UI look cheap.

**Audio** is loose `.ogg`/`.wav` with descriptive names — nothing to configure.

Pixel-art packs need texture filtering set to **nearest** or they blur; in Godot
that is a project setting (`rendering/textures/canvas_textures/default_texture_filter`),
not something to fix file by file.
