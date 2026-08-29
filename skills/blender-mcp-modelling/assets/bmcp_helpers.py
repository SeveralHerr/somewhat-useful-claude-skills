"""bmcp - helpers for modelling through the Blender MCP.

Load once per session (see SKILL.md §2); afterwards every `execute_blender_code` call
can just `import bmcp`. Loading it from disk means the source never has to travel
through the conversation, and `sys.modules` survives between calls even though the
globals of an individual call do not.

    import sys, importlib.util
    spec = importlib.util.spec_from_file_location("bmcp", r"<skill dir>/assets/bmcp_helpers.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    sys.modules["bmcp"] = m

Everything here is deliberately small and non-destructive. Nothing deletes an object it
did not create, because the file on the other end of the MCP belongs to someone else and
may hold unsaved work.
"""

import json
import math
import os
import struct

import bmesh
import bpy
from mathutils import Vector

__all__ = [
    "world_bbox", "collection_objects", "get_collection", "drop_collection",
    "palette_from_dir", "material_from_spec", "material_from_palette",
    "box", "taper_box", "build_mesh", "flat_shade",
    "preview_rig", "frame_camera", "restore_session",
    "clean_names", "conform", "export_glb", "import_model",
]

RIG = "bmcp_preview"
REF = "bmcp_reference"


# --------------------------------------------------------------- scene bookkeeping

def get_collection(name, parent=None):
    """Fetch or create a collection linked under the scene (or `parent`)."""
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    host = parent or bpy.context.scene.collection
    if coll.name not in {c.name for c in host.children}:
        host.children.link(coll)
    return coll


def collection_objects(name):
    coll = bpy.data.collections.get(name)
    return list(coll.objects) if coll else []


def drop_collection(name):
    """Remove a collection this module created, with its objects. Safe if absent."""
    coll = bpy.data.collections.get(name)
    if coll is None:
        return 0
    n = len(coll.objects)
    for obj in list(coll.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(coll)
    return n


def world_bbox(objs):
    """(min, max) world-space corners over MESH objects only.

    Meshes only, because a light is a VisualInstance too and a point light's bounding
    box is a cube of twice its range - one lamp in the list silently inflates the box
    and every framing or placement decision taken from it is then wrong.
    """
    pts = []
    for obj in objs:
        if obj.type != 'MESH':
            continue
        pts += [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    if not pts:
        return None, None
    lo = Vector((min(p[i] for p in pts) for i in range(3)))
    hi = Vector((max(p[i] for p in pts) for i in range(3)))
    return lo, hi


# ---------------------------------------------------------------------- materials

def _read_gltf_json(path):
    if path.lower().endswith(".gltf"):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    with open(path, "rb") as fh:
        data = fh.read()
    off = 12
    while off < len(data):
        ln, ty = struct.unpack_from("<II", data, off)
        off += 8
        if ty == 0x4E4F534A:
            return json.loads(data[off:off + ln].decode("utf-8"))
        off += ln
    raise ValueError("no JSON chunk in %s" % path)


def palette_from_dir(ref_dir, exclude=()):
    """name -> (base_color, metallic, roughness) read out of reference glTF files.

    Reading the palette instead of eyeballing it is the whole game for flat-shaded
    kits: there is no texture detail to hide a near-miss, so a colour that is close
    reads as a different material sitting next to the real ones.
    """
    skip = {os.path.normcase(os.path.abspath(p)) for p in exclude}
    palette = {}
    for entry in sorted(os.listdir(ref_dir)):
        if not entry.lower().endswith((".glb", ".gltf")):
            continue
        path = os.path.join(ref_dir, entry)
        if os.path.normcase(os.path.abspath(path)) in skip:
            continue
        for mat in _read_gltf_json(path).get("materials", []):
            pbr = mat.get("pbrMetallicRoughness", {})
            palette[mat.get("name")] = (
                tuple(pbr.get("baseColorFactor", [1.0, 1.0, 1.0, 1.0])),
                pbr.get("metallicFactor", 1.0),
                pbr.get("roughnessFactor", 1.0),
            )
    return palette


def material_from_spec(name, base_color, metallic=0.0, roughness=1.0, backface_cull=True):
    """Create a Principled material. `base_color` is LINEAR RGBA, as glTF stores it.

    Blender's Base Color socket is linear too, so glTF values copy across untouched -
    converting to sRGB on the way in is the usual reason a matched palette comes out
    washed out.
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    rgba = tuple(base_color) if len(base_color) == 4 else tuple(base_color) + (1.0,)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    # Workbench and the solid-mode viewport read `diffuse_color`, not the BSDF. Setting
    # only the node leaves both showing pure white, which reads as "the model imported
    # untextured" rather than "the render engine is looking somewhere else".
    mat.diffuse_color = rgba
    mat.use_backface_culling = backface_cull
    return mat


def material_from_palette(name, palette):
    if name not in palette:
        raise KeyError("%r is not in the reference palette. Available: %s"
                       % (name, ", ".join(sorted(palette))))
    base, metallic, roughness = palette[name]
    return material_from_spec(name, base, metallic, roughness)


# ---------------------------------------------------------------------- geometry

def box(x0, x1, y0, y1, z0, z1):
    """Axis-aligned box as (verts, quads)."""
    return taper_box(x0, x1, y0, y1, z0, z1, z1)


def taper_box(x0, x1, y0, y1, z0, z1_at_x0, z1_at_x1):
    """Box whose top face tilts along X. Flat bottom at z0.

    Most chunky low-poly props are a handful of these; resisting the urge to model
    real detail is what keeps a new asset in style with a kit built the same way.
    """
    verts = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1_at_x0), (x1, y0, z1_at_x1),
        (x1, y1, z1_at_x1), (x0, y1, z1_at_x0),
    ]
    quads = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return verts, quads


def flat_shade(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = False


def build_mesh(mesh_name, parts, collection="asset", object_name=None,
               palette=None, uv_scale=None):
    """Assemble one object from `parts`: a list of (material_name, verts, quads).

    Faces are merged into a single mesh with per-face material slots, which is how
    kit assets are usually built - one object, a few materials, no parenting.

    Materials are looked up by exact name in `bpy.data.materials` first, then created
    from `palette` if given. Reusing the existing datablock matters: a fresh
    `materials.new()` when the name is taken yields `name.001`, and that suffix
    exports into the file where it reads as a different material entirely.
    """
    coll = get_collection(collection)
    mesh = bpy.data.meshes.new(mesh_name)
    obj = bpy.data.objects.new(object_name or mesh_name, mesh)
    coll.objects.link(obj)

    verts, faces, face_mat, slot_of = [], [], [], {}
    for mat_name, part_verts, part_quads in parts:
        if mat_name not in slot_of:
            mat = bpy.data.materials.get(mat_name)
            if mat is None:
                if palette is None:
                    raise KeyError("no material %r and no palette to create it from"
                                   % mat_name)
                mat = material_from_palette(mat_name, palette)
            slot_of[mat_name] = len(obj.data.materials)
            obj.data.materials.append(mat)
        base = len(verts)
        verts.extend(part_verts)
        for quad in part_quads:
            faces.append(tuple(base + i for i in quad))
            face_mat.append(slot_of[mat_name])

    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly, slot in zip(mesh.polygons, face_mat):
        poly.material_index = slot
        poly.use_smooth = False

    # Recalculate rather than trusting hand-written winding: a reversed quad is
    # invisible from outside and solid from inside, which no vertex list shows.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    # Many kits carry TEXCOORD_0 even when nothing samples it; a planar projection
    # reproduces that without pretending the values mean anything.
    uv = mesh.uv_layers.new(name="UVMap")
    sx, sy = uv_scale or (1.0, 1.0)
    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = (co.x / sx if sx else 0.0, co.y / sy if sy else 0.0)

    bpy.context.view_layer.update()
    return obj


# ------------------------------------------------------------------ preview + look

def frame_camera(objs, cam=None, direction=(-0.6, -1.0, 0.55), margin=1.35):
    """Point a camera at `objs` and back it off until the whole bounding box fits.

    Solving `dist = radius / tan(fov/2) * margin` rather than guessing an offset is
    the difference between a usable first render and a wasted one: assets are often a
    fraction of a unit across, so any remembered "stand back 2 metres" puts the camera
    inside the mesh.
    """
    cam = cam or bpy.context.scene.camera
    if cam is None or cam.type != 'CAMERA':
        raise ValueError("no camera to frame with - call preview_rig() first")
    lo, hi = world_bbox(objs)
    if lo is None:
        raise ValueError("nothing with geometry to frame")

    target = (lo + hi) / 2.0
    radius = (hi - lo).length / 2.0
    d = Vector(direction).normalized()
    dist = radius / math.tan(cam.data.angle / 2.0) * margin

    cam.location = target + d * dist
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    return {"target": [round(v, 4) for v in target],
            "radius": round(radius, 4), "distance": round(dist, 4)}


def preview_rig(objs, hide_others=True, sun_energy=3.0, fill_energy=12.0,
                background=(0.16, 0.17, 0.19), floor=True, resolution=(960, 640)):
    """Build a camera + key + fill + shadow floor sized to `objs`, in its own collection.

    Total irradiance is kept near 1.0 on purpose. Low-poly base colours run bright, so
    over-lighting clips every surface to white and the palette disappears - a washed-out
    preview is nearly always the lighting, not the materials.
    """
    scene = bpy.context.scene
    lo, hi = world_bbox(objs)
    if lo is None:
        raise ValueError("nothing with geometry to preview")
    target = (lo + hi) / 2.0
    radius = max((hi - lo).length / 2.0, 1e-4)

    drop_collection(RIG)
    rig = get_collection(RIG)

    cam_data = bpy.data.cameras.new("bmcpCam")
    cam_data.lens = 60
    cam = bpy.data.objects.new("bmcpCam", cam_data)
    rig.objects.link(cam)

    sun_data = bpy.data.lights.new("bmcpSun", type='SUN')
    sun_data.energy = sun_energy
    sun = bpy.data.objects.new("bmcpSun", sun_data)
    sun.rotation_euler = (math.radians(50), 0.0, math.radians(35))
    rig.objects.link(sun)

    fill_data = bpy.data.lights.new("bmcpFill", type='AREA')
    fill_data.energy = fill_energy
    fill_data.size = max(radius * 4, 0.5)
    fill = bpy.data.objects.new("bmcpFill", fill_data)
    fill.location = target + Vector((radius * 3, -radius * 3, radius * 2.5))
    fill.rotation_euler = (target - fill.location).to_track_quat('-Z', 'Y').to_euler()
    rig.objects.link(fill)

    if floor:
        span = radius * 6
        me = bpy.data.meshes.new("bmcpFloor")
        me.from_pydata([(-span, -span, 0), (span, -span, 0),
                        (span, span, 0), (-span, span, 0)], [], [(0, 1, 2, 3)])
        me.update()
        fl = bpy.data.objects.new("bmcpFloor", me)
        fl.location = (target.x, target.y, lo.z)
        mat = bpy.data.materials.get("bmcpFloorMat") or \
            material_from_spec("bmcpFloorMat", (0.35, 0.33, 0.30, 1.0), 0.0, 1.0, False)
        me.materials.append(mat)
        rig.objects.link(fl)

    # Remember what we changed so restore_session() can put it back. The scene is the
    # user's; hiding is reversible, deleting is not.
    scene["bmcp_prev_camera"] = scene.camera.name if scene.camera else ""
    hidden = []
    if hide_others:
        keep = {o.name for o in objs} | {o.name for o in rig.objects}
        for obj in scene.objects:
            if obj.name not in keep and not obj.hide_render:
                obj.hide_render = True
                hidden.append(obj.name)
    scene["bmcp_hidden"] = json.dumps(hidden)

    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = resolution
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = tuple(background) + (1.0,)
        bg.inputs["Strength"].default_value = 0.6

    frame_camera(objs, cam=cam)
    return {"camera": cam.name, "hidden": hidden, "radius": round(radius, 4)}


def restore_session(drop_rig=True, drop_reference=True):
    """Undo what preview_rig() changed: unhide, restore the camera, drop our collections."""
    scene = bpy.context.scene
    restored = json.loads(scene.get("bmcp_hidden", "[]"))
    for name in restored:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_render = False
    prev = scene.get("bmcp_prev_camera", "")
    if prev and bpy.data.objects.get(prev):
        scene.camera = bpy.data.objects[prev]
    dropped = 0
    if drop_rig:
        dropped += drop_collection(RIG)
    if drop_reference:
        dropped += drop_collection(REF)
    for key in ("bmcp_hidden", "bmcp_prev_camera"):
        if key in scene.keys():
            del scene[key]
    return {"unhidden": restored, "objects_dropped": dropped}


def import_model(path, location=(0.0, 0.0, 0.0), collection=REF):
    """Import a reference model beside your work, into its own collection.

    Standing a new asset next to a genuine one from the target set is the check that
    catches style drift and scale errors, both of which look completely fine in
    isolation. Drop the collection before exporting.
    """
    coll = get_collection(collection)
    before = set(bpy.data.objects)
    view_layer = bpy.context.view_layer
    previous = view_layer.active_layer_collection
    view_layer.active_layer_collection = view_layer.layer_collection.children[coll.name]
    try:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".glb", ".gltf"):
            bpy.ops.import_scene.gltf(filepath=path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=path)
        else:
            raise ValueError("unsupported reference format: %s" % ext)
    finally:
        view_layer.active_layer_collection = previous

    added = [o for o in bpy.data.objects if o not in before]
    for obj in added:
        if obj.parent is None:
            obj.location = Vector(location)
    bpy.context.view_layer.update()
    return added


# --------------------------------------------------------------- export + conform

def clean_names(obj, mesh_name=None, object_name=None):
    """Strip `.001`-style suffixes from this object's mesh and materials.

    Blender appends the suffix whenever the name is already taken - which it usually is
    mid-iteration, because the previous attempt's datablocks are still in the file. The
    suffix then exports into the asset, where an engine reads `wood.001` as a different
    material from `wood`. Purging the stale orphans first frees the real name.
    """
    keep = set(obj.data.materials)
    stems = {m.name.split(".")[0] for m in keep}
    for mat in list(bpy.data.materials):
        if mat.name.split(".")[0] in stems and mat not in keep and mat.users == 0:
            bpy.data.materials.remove(mat)

    if mesh_name:
        for mesh in list(bpy.data.meshes):
            if mesh is not obj.data and mesh.users == 0 and \
                    mesh.name.split(".")[0] == mesh_name.split(".")[0]:
                bpy.data.meshes.remove(mesh)

    try:
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True,
                                       do_recursive=True)
    except RuntimeError:
        pass  # no orphans, or no context for the operator; neither is a problem

    for mat in obj.data.materials:
        stem = mat.name.split(".")[0]
        if mat.name != stem and bpy.data.materials.get(stem) is None:
            mat.name = stem
    if mesh_name:
        obj.data.name = mesh_name
    if object_name:
        obj.name = object_name

    return {"object": obj.name, "mesh": obj.data.name,
            "materials": [m.name for m in obj.data.materials]}


def conform(obj):
    """Report the facts an exported asset is judged on, before it is exported."""
    lo, hi = world_bbox([obj])
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    return {
        "object": obj.name,
        "mesh": obj.data.name,
        "min": [round(v, 6) for v in lo],
        "size": [round(v, 6) for v in (hi - lo)],
        "triangles": tris,
        "materials": [m.name for m in obj.data.materials],
        "flat_shaded": all(not p.use_smooth for p in obj.data.polygons),
        "transform_is_identity": (
            tuple(round(v, 6) for v in obj.location) == (0.0, 0.0, 0.0)
            and tuple(round(v, 6) for v in obj.scale) == (1.0, 1.0, 1.0)
            and tuple(round(v, 6) for v in obj.rotation_euler) == (0.0, 0.0, 0.0)
        ),
    }


def export_glb(obj, filepath, yup=True):
    """Export just this object to .glb, with the object transform zeroed.

    Selection-only, because anything else in the file - a preview light, an imported
    reference model - would otherwise travel with the asset.
    """
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()

    for other in bpy.context.view_layer.objects:
        other.select_set(other is obj)
    bpy.context.view_layer.objects.active = obj

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format="GLB",
        use_selection=True,
        export_yup=yup,
        export_apply=True,
        export_materials="EXPORT",
        export_normals=True,
        export_texcoords=True,
    )
    return {"path": filepath, "bytes": os.path.getsize(filepath), **conform(obj)}
