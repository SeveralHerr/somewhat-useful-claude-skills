# Troubleshooting

Symptom → cause, for the failures that look like something else. Read the row that
matches what you are seeing rather than reasoning from first principles: most of these
present as a *plausible* result, which is exactly why they cost time.

## Contents

- [Renders](#renders)
- [The model itself](#the-model-itself)
- [Export](#export)
- [Importing into an engine](#importing-into-an-engine)
- [The MCP session](#the-mcp-session)

---

## Renders

**The PNG isn't where I told Blender to put it.**
`scene.render.filepath` is not a filename. Blender appends the extension for the current
`image_settings.file_format`, so `.../look.png` becomes `look.png.png`; and a path
beginning `//` is *relative to the .blend file*, which for an unsaved session is a temp
directory. Set an absolute path with no extension. Reading the wrong file here means you
judge a stale render from the previous pass and "fix" a problem that no longer exists,
which is the single easiest way to waste an iteration.

**The render doesn't match the camera I just framed.**
You captured the viewport, not the camera. `get_viewport_screenshot` shows whatever the
Blender window is pointed at, which `bmcp.frame_camera` does not touch. Render with
`bpy.ops.render.render(write_still=True)` (SKILL.md §4).

**Blank frame, or floor and background only.**
Almost always framing. Assets are frequently a fraction of a unit across, so a camera
placed at a remembered distance sits inside the mesh or far outside it. Frame from the
bounding box (`bmcp.frame_camera`). Also check the object is in a collection that is not
excluded from the view layer, and that `hide_render` is not still set from an earlier pass.

**Everything is black.**
No light, world strength at 0, or the camera is inside geometry looking at backfaces
(which are invisible when backface culling is on). Add the preview rig and re-frame.

**Everything is flat white, but only under Workbench.**
Workbench and the solid-mode viewport read `material.diffuse_color`, not the Principled
BSDF, so a material with only the BSDF set has no colour as far as they are concerned.
`bmcp.material_from_spec` sets both; a hand-rolled material usually doesn't. This reads as
"the materials didn't survive", which is a different and much longer hunt.

**Washed out — pale, colours barely distinguishable.**
Over-lighting, not the materials. Low-poly kit base colours run bright (Kenney's wood is
0.90/0.60/0.39), so pushing much past ~1.0 of total irradiance clips every surface to
white and the palette disappears. Turn the key and fill down before touching a colour.

**Colours are wrong — muddy or too dark.**
A linear/sRGB mix-up. glTF `baseColorFactor` and Blender's Base Color socket are *both*
linear, so values transfer untouched; converting between them "to be safe" is what breaks
it. If you sampled a colour off a screenshot instead of reading the source file, that is
also this.

**One flat colour filling the frame.**
The camera is inside an object, or a single face is against the lens. Re-frame with a
larger margin.

---

## The model itself

**Faces invisible from outside, solid from inside.**
Reversed winding. Don't inspect vertex order by hand — run
`bmesh.ops.recalc_face_normals` (`build_mesh` does).

**The whole thing looks melted or inflated.**
Smooth shading on a low-poly mesh. Flat shading is per-polygon:
`polygon.use_smooth = False` on every face.

**Flickering stripes where two parts meet.**
Z-fighting from coplanar faces. Give the parts a real gap, or make one strictly contain
the other. Two surfaces at exactly the same height will always fight.

**A part is missing but the vertex count says it's there.**
It's buried inside another part. This is what looking at a render catches and reading
coordinates does not: check whether it protrudes at all, not merely whether it exists.

**Measurements come back wrong when a light is in the group.**
A point light's bounding box is a cube of twice its range, so any "measure everything"
pass that includes lights silently inflates the result. Measure meshes only.

**Stale values after a change.**
World matrices and modifier results need `bpy.context.view_layer.update()` before they
read back correctly.

---

## Export

**Material or mesh named `name.001` in the exported file.**
Blender appends the suffix when the name is taken — normal mid-iteration, since the
previous attempt's datablocks are still around — and it exports silently. To an engine
`wood.001` is a different material from `wood`. Purge the orphans, reclaim the name,
re-export (`bmcp.clean_names`).

**Things you didn't want are in the file.**
Export with `use_selection=True` and exactly one object selected *and* active — they are
separate states, and operators change both as a side effect.

**The pivot is offset by exactly the object's position.**
The object transform wasn't zeroed before export, so the geometry carries the offset.
Zero location/rotation/scale first (`bmcp.export_glb` does).

**Materials vanish on export.**
`export_materials="EXPORT"`, and for a textured asset the image files have to travel too.

---

## Importing into an engine

**Exporting is not installing.** A written file is not yet an asset. Most engines need an
import pass to generate their own sidecar metadata, and project lint/test gates typically
pass while it is missing, because the file is present and well-formed.

**The asset simply isn't there.**
No import sidecar. In Godot 4: `godot --headless --path . --import`, then confirm
`<name>.glb.import` exists. Observed in a real project: lint printed `UIDs: OK … exit 0`
for a `.glb` with no `.import` at all. Comparing the counts of `*.glb` and `*.glb.import`
in the asset folder is a cheap standing check.

**Magenta, or plain white.**
Materials didn't survive. For a textured asset, the texture folder usually has to sit
beside the models — check the import log, which names what it couldn't resolve.

**Wrong scale — 100× or 0.01×.**
Unit mismatch, or a scale left on the node. Node transforms are why measuring raw vertex
positions lies; `style_probe.py` applies them.

**Lying on its side, or rotated 90°.**
Y-up versus Z-up. Export with `export_yup=True` for glTF; if it still comes in rotated,
the engine is applying its own conversion on top.

**Sits on the floor in Blender, floats or sinks in the engine.**
The set's base convention isn't 0. `style_probe.py` reports `BASE`; match it.

**It's in the right place but faces the wrong way.**
Front-axis convention differs from the set's. This is a property of the reference kit,
not of your model — check what the neighbours do.

---

## The MCP session

**"Cannot connect to Blender at localhost:9876".**
Blender was closed, or the add-on's server stopped. It cannot be restarted from this side
— ask the user to reopen Blender and start the MCP server. Work that doesn't need the live
session (measuring reference files, checking an exported asset) still runs fine meanwhile.

**A variable or function from the last call is gone.**
Expected: each `execute_blender_code` call gets a fresh namespace. `sys.modules` and the
`bpy` scene persist, which is why helpers are installed as a module once (SKILL.md §2).

**An operator did nothing and reported no error.**
`bpy.ops` returns `{'CANCELLED'}` rather than raising when the context is wrong. Check the
return value; a cancelled operator is indistinguishable from a successful one otherwise.

**Everything hangs.**
A modal operator or a dialog is blocking Blender's UI thread. Nothing will respond until
someone dismisses it in the application — avoid anything that opens a popup or waits for
confirmation.
