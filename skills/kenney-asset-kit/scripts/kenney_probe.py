#!/usr/bin/env python3
"""Measure a Kenney 3D kit: grid unit, pivot convention, facing, module widths.

Reads glTF/GLB directly (stdlib only, no engine, no imports, nothing written).
Point it at a kit directory and it answers the questions you would otherwise
guess at and get wrong:

    python kenney_probe.py "<kit dir>"                  # whole-kit conventions
    python kenney_probe.py "<kit dir>" --models wall floorFull bedDouble
    python kenney_probe.py "<kit dir>" --json

Sizes are in the kit's own units, after applying node transforms — Kenney models
routinely carry a scale on the node, so raw accessor min/max lies.
"""

import argparse
import json
import os
import struct
import sys
from collections import Counter

# --------------------------------------------------------------------- glTF IO


def _load_gltf(path):
    """Return (json, {buffer_index: bytes}) for a .glb or .gltf file."""
    if path.lower().endswith(".glb"):
        data = open(path, "rb").read()
        if len(data) < 12 or data[:4] != b"glTF":
            raise ValueError("not a GLB file")
        _, _, length = struct.unpack_from("<III", data, 0)
        off, doc, chunks = 12, None, {}
        while off < min(length, len(data)):
            clen, ctype = struct.unpack_from("<II", data, off)
            off += 8
            if ctype == 0x4E4F534A:      # JSON
                doc = json.loads(data[off:off + clen].decode("utf-8"))
            elif ctype == 0x004E4942:    # BIN
                chunks[0] = data[off:off + clen]
            off += clen
        return doc, chunks

    doc = json.load(open(path, "r", encoding="utf-8"))
    base = os.path.dirname(path)
    buffers = {}
    for i, buf in enumerate(doc.get("buffers", [])):
        uri = buf.get("uri", "")
        if uri.startswith("data:"):
            import base64
            buffers[i] = base64.b64decode(uri.split(",", 1)[1])
        elif uri:
            from urllib.parse import unquote
            buffers[i] = open(os.path.join(base, unquote(uri)), "rb").read()
    return doc, buffers


def _read_positions(doc, buffers, accessor_index):
    """Yield (x, y, z) for a POSITION accessor. Kenney kits are always float32."""
    acc = doc["accessors"][accessor_index]
    if "bufferView" not in acc:
        return
    view = doc["bufferViews"][acc["bufferView"]]
    blob = buffers.get(view.get("buffer", 0))
    if blob is None:
        return
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or 12
    for i in range(acc["count"]):
        yield struct.unpack_from("<fff", blob, start + i * stride)


# ------------------------------------------------------------------- transforms


def _mat_mul(a, b):
    """Column-major 4x4 multiply, matching glTF's matrix layout."""
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return out


def _node_matrix(node):
    if "matrix" in node:
        return list(node["matrix"])
    t = node.get("translation", [0, 0, 0])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    return [
        (1 - 2 * (y * y + z * z)) * s[0], (2 * (x * y + z * w)) * s[0], (2 * (x * z - y * w)) * s[0], 0,
        (2 * (x * y - z * w)) * s[1], (1 - 2 * (x * x + z * z)) * s[1], (2 * (y * z + x * w)) * s[1], 0,
        (2 * (x * z + y * w)) * s[2], (2 * (y * z - x * w)) * s[2], (1 - 2 * (x * x + y * y)) * s[2], 0,
        t[0], t[1], t[2], 1,
    ]


def _apply(m, p):
    return (
        m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12],
        m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
        m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14],
    )


IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


# ---------------------------------------------------------------------- measure


def measure(path, want_vertices=True):
    """Measure one model. Returns a dict, or None if it has no geometry."""
    doc, buffers = _load_gltf(path)
    scene = doc.get("scenes", [{}])[doc.get("scene", 0)]
    nodes = doc.get("nodes", [])

    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    verts = []

    stack = [(i, IDENTITY) for i in scene.get("nodes", [])]
    while stack:
        idx, parent = stack.pop()
        node = nodes[idx]
        world = _mat_mul(parent, _node_matrix(node))
        if "mesh" in node:
            for prim in doc["meshes"][node["mesh"]].get("primitives", []):
                pos = prim.get("attributes", {}).get("POSITION")
                if pos is None:
                    continue
                acc = doc["accessors"][pos]
                if want_vertices:
                    for v in _read_positions(doc, buffers, pos):
                        w = _apply(world, v)
                        verts.append(w)
                        for i in range(3):
                            lo[i] = min(lo[i], w[i])
                            hi[i] = max(hi[i], w[i])
                else:
                    mn, mx = acc.get("min"), acc.get("max")
                    if not mn:
                        continue
                    for cx in (mn[0], mx[0]):
                        for cy in (mn[1], mx[1]):
                            for cz in (mn[2], mx[2]):
                                w = _apply(world, (cx, cy, cz))
                                for i in range(3):
                                    lo[i] = min(lo[i], w[i])
                                    hi[i] = max(hi[i], w[i])
        for child in node.get("children", []):
            stack.append((child, world))

    if lo[0] == float("inf"):
        return None

    size = [hi[i] - lo[i] for i in range(3)]
    # Where the model's origin sits inside its own box, 0..1 per axis. Kenney is
    # usually 0 or 1 on X/Z (a corner pivot) and 0 on Y (sits on the floor).
    pivot = [
        (0.0 - lo[i]) / size[i] if size[i] > 1e-6 else 0.5
        for i in range(3)
    ]

    info = {
        "name": os.path.splitext(os.path.basename(path))[0],
        "size": [round(v, 4) for v in size],
        "min": [round(v, 4) for v in lo],
        "max": [round(v, 4) for v in hi],
        "pivot_in_box": [round(v, 3) for v in pivot],
        "grounded": abs(lo[1]) < 0.01,
        "materials": [m.get("name", "?") for m in doc.get("materials", [])],
        "colors": {
            m.get("name", "?"): [
                round(c, 3)
                for c in m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])
            ]
            for m in doc.get("materials", [])
        },
        "external_images": [
            im["uri"] for im in doc.get("images", [])
            if im.get("uri") and not im["uri"].startswith("data:")
        ],
        "child_nodes": [n.get("name", "?") for n in nodes if "mesh" in n][1:],
    }
    info["facing"] = _facing(verts, lo, hi) if verts else None
    return info


def _facing(verts, lo, hi):
    """Guess which way a model faces from where its tall mass sits.

    A chair's backrest, a bed's headboard and a toilet's cistern are all the
    tall part, and they all sit at the BACK. So the centroid of the upper
    portion of the mesh, compared to the box centre, points away from the front.
    Returns e.g. "+Z" (the model faces +Z) or None when it is symmetric.
    """
    height = hi[1] - lo[1]
    if height < 1e-6:
        return None
    # The top fifth only. Take more than that and a cabinet's worktop or a
    # fridge's door panel drowns out the actual backrests: at the top 40% the
    # Furniture Kit votes 26-to-19, at the top 20% it votes 35-to-14.
    top = [v for v in verts if v[1] > lo[1] + 0.8 * height]
    if not top:
        return None

    result = {}
    for axis, label in ((0, "X"), (2, "Z")):
        span = hi[axis] - lo[axis]
        if span < 1e-6:
            continue
        centre = (lo[axis] + hi[axis]) / 2.0
        mass = sum(v[axis] for v in top) / len(top)
        result[label] = (mass - centre) / span

    if not result:
        return None
    label, offset = max(result.items(), key=lambda kv: abs(kv[1]))
    if abs(offset) < 0.08:
        return None
    # Tall mass toward +axis means the back is there, so the front is the other way.
    return ("-" if offset > 0 else "+") + label, round(abs(offset), 3)


# Only a pronounced tall mass means anything. A cabinet's flat worktop drifts a
# few percent either way and would otherwise outvote the furniture that has a
# real back, which is how a kit-wide tally ends up a meaningless 35-to-31 split.
FACING_CONFIDENT = 0.18

# Name PREFIXES Kenney gives the pieces that define a kit's grid. Prefixes, not
# substrings: "coatRack" contains "track", and a kit-wide substring match quietly
# fills the sample with props.
STRUCTURAL = ("floor", "wall", "tile", "ground", "road", "path", "base", "block",
              "platform", "ceiling", "roof", "track", "corner", "stairs",
              "corridor", "room", "bridge")


# ------------------------------------------------------------------- kit survey


def find_model_dir(kit_dir):
    """Kenney ships several export formats; prefer GLB, then glTF."""
    best, best_rank = None, 99
    for root, _dirs, files in os.walk(kit_dir):
        n = sum(1 for f in files if f.lower().endswith((".glb", ".gltf")))
        if not n:
            continue
        low = root.lower()
        rank = 0 if "glb" in low else (1 if "gltf" in low else 2)
        if rank < best_rank or (rank == best_rank and best and n > best[1]):
            best, best_rank = (root, n), rank
    return best


def _mode(values, tolerance=0.05):
    """Most common value after snapping to a tolerance grid."""
    if not values:
        return None, 0
    counts = Counter(round(v / tolerance) * tolerance for v in values)
    value, n = counts.most_common(1)[0]
    return round(value, 3), n


def survey(kit_dir, limit=None):
    found = find_model_dir(kit_dir)
    if not found:
        raise SystemExit("No .glb/.gltf found under %s" % kit_dir)
    model_dir, _ = found
    names = sorted(f for f in os.listdir(model_dir) if f.lower().endswith((".glb", ".gltf")))
    if limit:
        names = names[:limit]

    models, failed = [], []
    for f in names:
        try:
            info = measure(os.path.join(model_dir, f))
        except Exception as exc:                       # noqa: BLE001 - report, don't abort
            failed.append("%s: %s" % (f, exc))
            continue
        if info:
            models.append(info)

    # The grid unit is the footprint the kit's own structural pieces share. Two
    # things spoil the naive versions: "flat and square" picks up corner fillers
    # (the Furniture Kit has more 0.55 corner tiles than 1.0 floor tiles), and a
    # name match on its own can rest on a sample of two (the Modular Dungeon Kit
    # matches only `stairs` and `stairs-wide`, whose 8.4 is nobody's grid).
    footprints = [max(m["size"][0], m["size"][2]) for m in models]
    named = [m for m in models if m["name"].lower().startswith(STRUCTURAL)]
    struct_sizes = Counter(
        round(max(m["size"][0], m["size"][2]) / 0.05) * 0.05 for m in named)
    grid, grid_n = _mode([max(m["size"][0], m["size"][2]) for m in named])
    if len(named) < 3:
        grid, grid_n, struct_sizes = None, 0, Counter()
    # Reported separately and never conflated with the grid: every kit has a modal
    # footprint, including kits of food and characters, where it means nothing.
    modal, modal_n = _mode(footprints)
    sample = named if grid else models

    facings = Counter(
        m["facing"][0] for m in models
        if m["facing"] and m["facing"][1] >= FACING_CONFIDENT
    )
    widths = Counter(round(m["size"][0] / 0.05) * 0.05 for m in models)

    return {
        "kit": os.path.basename(os.path.normpath(kit_dir)),
        "model_dir": model_dir,
        "count": len(models),
        "failed": failed,
        "grid_unit": grid,
        "grid_evidence": grid_n,
        "grid_sample": len(named),
        "structural_sizes": [(round(v, 2), n) for v, n in struct_sizes.most_common(3)],
        "modal_footprint": modal,
        "modal_footprint_n": modal_n,
        "tile_pieces": [m["name"] for m in sample
                        if grid and abs(max(m["size"][0], m["size"][2]) - grid) < 0.03][:8],
        "facing": facings.most_common(3),
        "pivot": _pivot_summary(models),
        "base_y": _mode([m["min"][1] for m in models], 0.01),
        "common_widths": [(round(w, 2), n) for w, n in widths.most_common(6)],
        "textured": sorted({im for m in models for im in m["external_images"]}),
        "materials": Counter(mat for m in models for mat in m["materials"]).most_common(8),
        "models": models,
    }


def _pivot_summary(models):
    """Where the origin sits relative to each model's own box, as named cases.

    This is the number that decides whether `position = (col, 0, -row)` puts a
    tile where you meant it, so it is worth naming rather than leaving as a
    fraction the reader has to interpret.
    """
    def classify(m):
        x, z = m["pivot_in_box"][0], m["pivot_in_box"][2]
        if not (-0.1 <= x <= 1.1 and -0.1 <= z <= 1.1):
            return "outside the box"
        near = lambda v, t: abs(v - t) < 0.15                      # noqa: E731
        if near(x, 0.5) and near(z, 0.5):
            return "centred"
        corner_x = "min-X" if near(x, 0) else ("max-X" if near(x, 1) else "?")
        corner_z = "min-Z" if near(z, 0) else ("max-Z" if near(z, 1) else "?")
        if "?" in (corner_x, corner_z):
            return "off-centre"
        return "corner at %s/%s" % (corner_x, corner_z)

    return Counter(classify(m) for m in models).most_common(3)


# ------------------------------------------------------------------------ report


def print_survey(s):
    print("Kit: %s" % s["kit"])
    print("Models: %d in %s" % (s["count"], s["model_dir"]))
    if s["failed"]:
        print("Unreadable: %d  (%s)" % (len(s["failed"]), s["failed"][0]))
    print()

    if s["structural_sizes"]:
        print("STRUCTURAL PIECES (%d named floor*/wall*/road*/tile*/corridor*) measure: %s"
              % (s["grid_sample"], ", ".join("%.2f x%d" % (v, n)
                                             for v, n in s["structural_sizes"])))
        if s["tile_pieces"]:
            print("  at %s: %s" % (s["grid_unit"], ", ".join(s["tile_pieces"][:4])))
        print("  The grid unit is normally the value recurring most here; anything larger")
        print("  is a double-width variant. Confirm it against the line below - a kit whose")
        print("  grid is real shows the same number in both.")
    else:
        print("STRUCTURAL PIECES: none named floor*/wall*/road*/tile*/corridor*.")
        print("  Prop and character kits have no grid at all. If this one is modular under")
        print("  other names, the footprint below is the number to check.")
    print("MOST COMMON FOOTPRINT (all models): %s  (%d of %d)"
          % (s["modal_footprint"], s["modal_footprint_n"], s["count"]))

    print("PIVOT: %s" % ", ".join("%s x%d" % (p, n) for p, n in s["pivot"]))
    lead_pivot = s["pivot"][0][0] if s["pivot"] else ""
    if lead_pivot.startswith("corner at min-X/max-Z"):
        print("  The model occupies +X and -Z from its origin, so a tile placed at")
        print("  (col, 0, -row) covers exactly cell (col, row). Offsets are one-sided:")
        print("  centre a piece by hand, or anchor to its bounding box (see the skill).")
    elif lead_pivot == "centred":
        print("  The origin is the footprint centre, so (col + 0.5, 0, -row - 0.5) puts")
        print("  a tile on cell (col, row). Corner-pivot kits need a different offset -")
        print("  do not carry a formula across kits.")
    else:
        print("  Mixed or off-centre origins: anchor to each model's bounding box rather")
        print("  than assuming a shared offset.")
    print("BASE: models sit with their lowest point at y = %s" % s["base_y"][0])

    if s["facing"]:
        lead, lead_n = s["facing"][0]
        rest = s["facing"][1][1] if len(s["facing"]) > 1 else 0
        print("FACING: %s  (%s)" % (lead, ", ".join("%s x%d" % (f, n) for f, n in s["facing"])))
        print("  from where the tall mass sits - a backrest, headboard or cistern is at the BACK")
        if rest >= lead_n * 0.5:
            print("  !! the vote is split; check two obvious models by hand before trusting it")
    else:
        print("FACING: no model has a pronounced back - this kit has no consistent front")

    print("COMMON FOOTPRINT WIDTHS: %s" % ", ".join(
        "%.2f x%d" % (w, n) for w, n in s["common_widths"]))
    print("  a spike well below the grid unit is the kit's module step "
          "(cabinet runs, wall segments)")

    if s["textured"]:
        print("TEXTURES: external - copy them alongside the models: %s"
              % ", ".join(s["textured"][:4]))
    else:
        print("TEXTURES: none; flat per-material base colours (%s)"
              % ", ".join(m for m, _ in s["materials"][:5]))


def print_models(s, wanted):
    index = {m["name"]: m for m in s["models"]}
    for name in wanted:
        m = index.get(name)
        if not m:
            hits = [k for k in index if name.lower() in k.lower()]
            if not hits:
                print("%-28s NOT FOUND" % name)
                continue
            m = index[hits[0]]
        if not m["facing"]:
            face = "n/a"
        else:
            face = "%s%s" % (m["facing"][0], "" if m["facing"][1] >= FACING_CONFIDENT else "?")
        print("%-28s size=(%6.3f,%6.3f,%6.3f)  min=(%6.3f,%6.3f,%6.3f)  faces %-4s%s" % (
            m["name"], m["size"][0], m["size"][1], m["size"][2],
            m["min"][0], m["min"][1], m["min"][2], face,
            "  parts: " + ", ".join(m["child_nodes"][:4]) if m["child_nodes"] else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kit_dir", help="a Kenney kit directory (or its Models subdir)")
    ap.add_argument("--models", nargs="+", metavar="NAME",
                    help="print these models in detail (substring match)")
    ap.add_argument("--limit", type=int, help="only read the first N models")
    ap.add_argument("--json", action="store_true", help="dump everything as JSON")
    args = ap.parse_args()

    s = survey(args.kit_dir, limit=args.limit)
    if args.json:
        json.dump(s, sys.stdout, indent=1)
        print()
        return
    print_survey(s)
    if args.models:
        print()
        print_models(s, args.models)


if __name__ == "__main__":
    main()
