---
name: blender-mcp-modelling
description: Model 3D assets in Blender through the Blender MCP so they come out matching an existing art style and actually load in the engine. Measures the style being matched — palette, pivot, scale, poly budget — out of the reference files rather than guessing at it, drives a look-at-the-render loop through the live session, and checks the export against the reference set before it ships. Use this whenever the user wants to make, model, build, sculpt or edit a 3D asset in Blender — "model a crate", "make an open book", "add a prop that matches my kit", "build me a mesh for this", "create a low-poly X" — and especially when the new asset has to sit alongside existing ones without looking foreign, or when a finished model came out the wrong size, the wrong colour, pivoted in the wrong place, floating, or invisible after import. Also use it when a Blender render came back unusable (blank, black, washed out, wildly mis-framed), when the user says a model "looks off" or "doesn't match", or when a freshly exported .glb/.gltf/.fbx will not load in Godot, Unity or Unreal. For *placing* models that already exist — laying out a room from a prefab kit, snapping props to a grid — use kenney-asset-kit instead; this skill is for authoring a new model into a set, and the two are complements.
---

# Modelling through the Blender MCP

The MCP lets you run `bpy` against a **running** Blender and look at what came out.
Both halves matter, and the second is the one that gets skipped.

A mesh assembled from coordinates you reasoned about is almost always *numerically*
right and frequently *visually* wrong: a page taper that reads as a wheelchair ramp, a
binding buried under the pages it was meant to separate, a lamp that measures fine and
towers over the room. None of that is visible in the vertex list. It is obvious in one
render. So the loop this skill is built around is **build → render → look → fix**, and
the renders are not a courtesy for the user at the end — they are how you find the bug.

The second failure class is quieter. An asset can be perfect and still be unusable: the
wrong pivot for the kit it joins, a material named `carpetDarker.001` instead of
`carpetDarker`, no engine import sidecar. Each of these produces a file that opens fine
in Blender, previews fine, and is wrong the moment anything else touches it. The fix is
to measure the target *before* building and check the export *after*, both mechanically.

## 1. Treat the live session as someone else's file

You are attached to a Blender someone has open, possibly with unsaved work in it.

- **Never** `bpy.ops.wm.read_factory_settings()` or `bpy.ops.wm.open_mainfile()`. That
  discards their work with no undo across the MCP boundary.
- Build into your own collection (`bpy.data.collections.new("myasset")`). It keeps your
  objects separable from theirs and makes export selection trivial.
- To get their objects out of a render, set `hide_render = True` — never delete. Put it
  back when you are done.
- Don't save their file unless asked.

Inspect before you touch anything: `get_objects_summary` tells you whether you are in an
empty startup file or someone's half-finished level, and those deserve different care.

## 2. Every code call is a fresh namespace — install helpers once

Measured, because it decides how you spend tokens: variables and functions defined in one
`execute_blender_code` call are **gone** by the next one. `sys.modules` and the `bpy`
scene, however, persist.

So don't re-paste helper functions on every iteration. Load the bundled module into the
session once, from disk, and it stays importable for the rest of the session:

```python
import sys, importlib.util
spec = importlib.util.spec_from_file_location("bmcp", r"<skill dir>/assets/bmcp_helpers.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
sys.modules["bmcp"] = m
result = {"loaded": m.__doc__.splitlines()[0], "api": [n for n in dir(m) if not n.startswith("_")]}
```

Then every later call is just `import bmcp`. Read `assets/bmcp_helpers.py` if you need to
know what a function does — but you rarely need to load it into context, because Blender
reads it off disk itself.

If Blender is running on a different machine from the skill files, that path won't
resolve; fall back to `exec(<contents>, m.__dict__)` with the file pasted in, or simply
write the few functions you need inline.

## 3. Measure the style before you model anything

Style-matching by eye fails in a specific way: flat-shaded, untextured kits (Kenney and
most low-poly asset packs) have no texture detail to hide a near-miss, so a colour that is
"basically right" reads as a different material sitting next to the real ones.

Every fact you need is already in the reference files. Read it:

```bash
python <skill dir>/scripts/style_probe.py "<reference asset dir>"
python <skill dir>/scripts/style_probe.py "<ref dir>" --json     # machine-readable
```

Stdlib only, no Blender, no engine — it parses glTF JSON and applies node transforms
(models routinely carry a scale on the node, so raw accessor min/max lies). It reports:

| Output | What you do with it |
|---|---|
| `PALETTE` | The exact linear `baseColorFactor` / metallic / roughness per material **name**. Copy these values; do not sample them off a screenshot and do not convert to sRGB — glTF base colour and Blender's Base Color socket are both linear, so they transfer untouched. |
| `PIVOT` | Where origin sits relative to the bounding box. Decides how you position your geometry, and it is kit-specific — corner-pivot and centred are both common and carrying one across sets is the classic silent error. |
| `BASE` | The Y the lowest point rests at. Non-zero means the set expects a floor somewhere other than 0. |
| `TRIANGLES` | The set's real budget. A 4,000-triangle prop dropped into a 60-triangle kit is off-style even when every colour matches. |
| `TEXTURES` | `none` means the whole art style is named flat materials, so material names are load-bearing (§6). |
| `NAMING` | The node/mesh naming pattern. Kits are usually consistent and engines key off it. |

**The octant trick.** Blender is Z-up, glTF is Y-up: the exporter maps glTF y = blender z
and glTF z = −blender y. So if the target's pivot is a corner at min-X/max-Z with the base
at 0 — very common — build entirely in Blender's **+X/+Y/+Z octant** and the convention
comes out automatically, with no offsets to work out by hand. Check the probe's `PIVOT`
line first; if it says centred, centre it in Blender instead.

## 4. Build, then look

Get *something* on screen early. A first render that reveals the silhouette is worth more
than a second hour of getting coordinates right.

```python
import bmcp
book = bmcp.build_mesh("Mesh crate", parts, collection="myasset")   # parts: [(material, verts, quads)]
bmcp.preview_rig([book])          # camera + sun + fill + shadow floor, in its own collection
bmcp.frame_camera(objs=[book])    # fits the camera to the bounding box
```

Then `render_viewport_to_path` and **read the PNG back**. Looking is the point.

Two framing notes that cost a wasted render each time they're ignored:

- **Fit the camera to the bounding box, never to a guessed offset.** Assets are often a
  fraction of a unit across; a camera placed "2 metres back" is inside the mesh or in
  another postcode. `frame_camera` solves `dist = radius / tan(fov/2) * margin`.
- **Keep total light energy near 1.0 of irradiance.** Low-poly base colours run bright
  (Kenney's wood is 0.90/0.60/0.39). Over-light it and every surface clips to white and
  the palette vanishes. A washed-out render is nearly always this, not the materials.

Now iterate. Expect **two to four** renders for a simple prop. Look for the things
geometry can't tell you: does the silhouette read as the object from a normal viewing
angle; do separate parts actually separate; is anything buried, floating, or z-fighting.
Change one thing at a time so you can tell which change helped.

When rebuilding, reuse the existing material datablocks rather than making new ones — see
§6 for why that matters more than it looks.

## 5. Render it next to a real one

This is the highest-value check in the skill and the least obvious. Import one or two
genuine assets from the target set, stand them beside yours, and render the group:

```python
import bmcp
bmcp.import_model(r"<ref dir>/chair.glb", location=(-0.28, 0.30, 0.0))
bmcp.frame_camera(objs=bmcp.collection_objects("myasset") + bmcp.collection_objects("bmcp_reference"))
```

Style drift that is invisible in isolation is obvious in company — proportions, chunkiness,
how bright the palette actually sits, whether your bevels are finer than the set's. It also
catches **scale errors instantly**, which is the single most expensive class of mistake
here, because a wrongly-scaled asset looks completely fine on its own.

Delete the reference collection before exporting (`bmcp.drop_collection`), or you will
ship someone else's chair inside your crate.

## 6. Names are part of the file format

When a datablock name is already taken, Blender silently appends `.001`. This happens
constantly during iteration, because the mesh and materials from your previous attempt are
still in the file. It then **exports into the asset**, where it is not cosmetic:

- To an engine, `carpetDarker.001` is a *different material* from `carpetDarker`. In a set
  whose entire art style is fifteen shared material names, that quietly breaks the one
  property making it a set.
- Mesh and node names are how engines and tooling identify parts (doors, drawers, lids).

Before every export:

```python
import bmcp
bmcp.clean_names(obj, mesh_name="Mesh crate")   # purges stale datablocks, reclaims names
```

Then confirm in the *exported file*, not in Blender — see §7. Blender is where the mistake
gets made, so it is the wrong place to check for it.

## 7. Verify the export against the reference set

Export, then check the file you actually produced:

```python
import bmcp
bmcp.export_glb(obj, r"<out dir>/crate.glb")     # selection-only, +Y up, applies modifiers
```

```bash
python <skill dir>/scripts/style_probe.py "<ref dir>" --check "<out dir>/crate.glb"
```

`--check` re-derives the contract from the references and validates the candidate against
it: material names known and values matching to float32, no `.001` suffixes anywhere,
pivot and base matching the set's convention, triangle count within range, and textured
state consistent. It exits non-zero on a mismatch and names each one, so it works as a
pre-commit gate rather than something to read and interpret.

Report what it says. "Pivot at (0, 0, −0.15), matching the set" is a claim; "looks right"
is not.

## 8. Exporting is not installing

A written file is not an asset the engine can load. Most engines need an import pass to
generate their own sidecar metadata, and **the project's own static checks will usually
pass while that is missing** — the file is present and well-formed, so nothing complains,
and the failure surfaces later as a missing model.

Godot 4:

```bash
godot --headless --path . --import          # generates the .import sidecar
ls assets/<dir>/<name>.glb.import           # confirm it exists - this is the check
```

Verified in a real project: `lint` reported `UIDs: OK … exit 0` on a `.glb` with no
`.import` file at all. A cheap standing check is comparing the counts of `*.glb` and
`*.glb.import` in the asset folder.

Then load it for real. In Godot a few lines in a `SceneTree` script will instantiate the
scene and print its runtime AABB and material names — the final confirmation that pivot,
scale and palette survived the whole trip. Unity and Unreal do the equivalent on import;
watch the import log rather than trusting the file browser.

## Gotchas

- **Read stderr / the operator return.** `bpy.ops` calls return `{'CANCELLED'}` rather than
  raising when context is wrong. A cancelled operator looks exactly like a successful one
  from the outside.
- **The active object and the selection are different things**, and operators change both
  as a side effect. Set both explicitly between operator calls; export-by-selection is a
  common victim.
- **Update the depsgraph before reading computed values.** World matrices and modifier
  results are stale until `bpy.context.view_layer.update()`.
- **A light's bounding box is not its lamp.** An `OmniLight`/point light's AABB is a cube
  of twice its range, so any framing or measurement that walks "all objects" and hits a
  light silently blows up. Measure `type == 'MESH'` only — `bmcp.world_bbox` does.
- **`from_pydata` trusts your winding order.** Recalculate normals
  (`bmesh.ops.recalc_face_normals`) instead of hand-checking vertex order, or you get
  faces that are invisible from the outside and solid from within.
- **Flat shading is a per-polygon flag.** `polygon.use_smooth = False` on every face; a
  low-poly asset with smooth shading reads as a melted version of itself.
- **Don't trigger modal operators or dialogs.** They block the Blender UI thread and the
  MCP stops responding until someone dismisses them by hand.
- **`--check` failing on triangle count is advisory-ish.** A genuinely more detailed asset
  may be legitimate; a 50× overrun is not. Use judgment, and say which you decided.

## Reference

- `references/troubleshooting.md` — symptom → cause table for renders that come back
  blank, black or washed out, models that import invisible, magenta or mis-scaled, and
  exports that lose their materials. Read it when something looks wrong rather than
  guessing at the cause.
- `assets/bmcp_helpers.py` — the in-session helper module (§2). Read only if you need the
  exact signature of something.
- `scripts/style_probe.py` — measurement and conformance checking (§3, §7). Run it; there
  is no reason to read it.
