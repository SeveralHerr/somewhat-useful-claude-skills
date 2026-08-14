#!/usr/bin/env python3
"""Measure the style contract of a set of 3D assets, and check a new asset against it.

    python style_probe.py <reference dir>                    # print the contract
    python style_probe.py <reference dir> --json             # same, machine-readable
    python style_probe.py <reference dir> --check <file>     # validate a candidate

Two jobs, one body of measurement:

*Before modelling*, the contract tells you what you have to hit — the exact material
colours, where the origin sits, what the triangle budget really is. Every one of those
is already stated in the reference files, so reading them beats remembering a convention
from a different asset set, which is the usual way a model ends up subtly foreign.

*After exporting*, `--check` re-derives the same contract and validates the new file
against it, exiting non-zero with a named reason. That makes it usable as a gate rather
than as a report someone has to interpret.

Reads glTF 2.0 (`.glb` and `.gltf`). Standard library only, no Blender, no engine, and
it never opens a buffer: positions and indices are described by accessor `min`/`max` and
`count` in the JSON, so bounding boxes and triangle counts come out of the header alone.
That makes it fast enough to run over a whole kit and safe to run anywhere.

Exit codes: 0 pass, 1 findings, 2 the probe could not run (bad path, no models).
"""

import argparse
import json
import os
import struct
import sys

# Colours survive a float32 round-trip through a DCC tool, not an exact one: a stored
# 0.972549 comes back as 0.9725490212440491. Compare at float32 resolution - far below
# anything an eye resolves, but tight enough that a genuinely different colour fails.
EPS = 1e-5

MODEL_EXTS = (".glb", ".gltf")


# --------------------------------------------------------------------- glTF reading

def load_gltf(path):
    """Return the glTF JSON document for a .glb or .gltf file."""
    if path.lower().endswith(".gltf"):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"glTF":
        raise ValueError("not a binary glTF: %s" % path)
    offset = 12
    while offset < len(data):
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        if chunk_type == 0x4E4F534A:  # 'JSON'
            return json.loads(data[offset:offset + chunk_len].decode("utf-8"))
        offset += chunk_len
    raise ValueError("no JSON chunk in %s" % path)


def _identity():
    return [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]


def _mat_mul(a, b):
    """Column-major 4x4 multiply, matching glTF's storage order."""
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return out


def _trs_matrix(node):
    """Compose a node's local matrix from either `matrix` or T/R/S."""
    if "matrix" in node:
        return list(node["matrix"])
    t = node.get("translation", [0.0, 0.0, 0.0])
    r = node.get("rotation", [0.0, 0.0, 0.0, 1.0])   # quaternion xyzw
    s = node.get("scale", [1.0, 1.0, 1.0])
    x, y, z, w = r
    rot = [
        1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w), 0,
        2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w), 0,
        2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y), 0,
        0, 0, 0, 1,
    ]
    for col in range(3):
        for row in range(3):
            rot[col * 4 + row] *= s[col]
    rot[12], rot[13], rot[14] = t[0], t[1], t[2]
    return rot


def _apply(m, p):
    x, y, z = p
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12],
        m[1] * x + m[5] * y + m[9] * z + m[13],
        m[2] * x + m[6] * y + m[10] * z + m[14],
    )


def _scene_nodes(gltf):
    """Yield (node dict, world matrix) for every node reachable from the scenes.

    Node transforms are applied because models routinely carry a scale on the node;
    trusting raw accessor min/max instead reports the wrong size, and every downstream
    judgement (does it fit the grid, is it the right size for the set) inherits that.
    """
    nodes = gltf.get("nodes", [])
    roots = []
    for scene in gltf.get("scenes", [{}]):
        roots.extend(scene.get("nodes", []))
    if not roots:
        roots = list(range(len(nodes)))

    stack = [(i, _identity()) for i in roots]
    seen = set()
    while stack:
        idx, parent = stack.pop()
        if idx in seen or idx >= len(nodes):
            continue
        seen.add(idx)
        node = nodes[idx]
        world = _mat_mul(parent, _trs_matrix(node))
        yield node, world
        for child in node.get("children", []):
            stack.append((child, world))


def model_stats(gltf):
    """Bounding box (transformed), triangle count, and part names for one document."""
    meshes = gltf.get("meshes", [])
    accessors = gltf.get("accessors", [])
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    tris = 0
    found = False

    for node, world in _scene_nodes(gltf):
        if "mesh" not in node:
            continue
        for prim in meshes[node["mesh"]].get("primitives", []):
            pos = prim.get("attributes", {}).get("POSITION")
            if pos is None:
                continue
            acc = accessors[pos]
            if "min" not in acc or "max" not in acc:
                continue
            amin, amax = acc["min"], acc["max"]
            # Transform all eight corners: under rotation the axis-aligned box of the
            # transformed corners is what matters, not the transformed min/max pair.
            for cx in (amin[0], amax[0]):
                for cy in (amin[1], amax[1]):
                    for cz in (amin[2], amax[2]):
                        p = _apply(world, (cx, cy, cz))
                        for i in range(3):
                            lo[i] = min(lo[i], p[i])
                            hi[i] = max(hi[i], p[i])
            found = True
            if "indices" in prim:
                tris += accessors[prim["indices"]]["count"] // 3
            else:
                tris += acc["count"] // 3

    if not found:
        return None
    return {
        "min": lo,
        "max": hi,
        "size": [hi[i] - lo[i] for i in range(3)],
        "triangles": tris,
        "node_names": [n.get("name", "") for n, _ in _scene_nodes(gltf)],
        "mesh_names": [m.get("name", "") for m in meshes],
    }


def model_materials(gltf):
    """name -> (baseColorFactor, metallic, roughness, doubleSided, textured)."""
    out = {}
    for mat in gltf.get("materials", []):
        pbr = mat.get("pbrMetallicRoughness", {})
        textured = "baseColorTexture" in pbr or "normalTexture" in mat
        out[mat.get("name", "<unnamed>")] = (
            tuple(pbr.get("baseColorFactor", [1.0, 1.0, 1.0, 1.0])),
            # glTF defaults, applied so a written 1.0 and an omitted one compare equal.
            pbr.get("metallicFactor", 1.0),
            pbr.get("roughnessFactor", 1.0),
            bool(mat.get("doubleSided", False)),
            textured,
        )
    return out


# ------------------------------------------------------------------- the contract

def _classify_axis(lo, hi, tol):
    """Where the origin sits on one axis relative to the extent."""
    if abs(lo) <= tol:
        return "min"
    if abs(hi) <= tol:
        return "max"
    if abs((lo + hi) / 2.0) <= tol:
        return "centre"
    return "off"


def _mode(values):
    if not values:
        return None
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return max(counts.items(), key=lambda kv: (kv[1], str(kv[0])))[0]


def find_models(path):
    if os.path.isfile(path):
        return [path]
    if not os.path.isdir(path):
        return []
    hits = []
    for root, _dirs, files in os.walk(path):
        for name in sorted(files):
            if name.lower().endswith(MODEL_EXTS):
                hits.append(os.path.join(root, name))
    return hits


def build_contract(paths, tol, exclude=()):
    """Derive the shared style contract from a set of reference models."""
    skip = {os.path.normcase(os.path.abspath(p)) for p in exclude}
    palette, conflicts, per_model = {}, [], []
    textured_any = False

    for path in paths:
        if os.path.normcase(os.path.abspath(path)) in skip:
            continue
        try:
            gltf = load_gltf(path)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            conflicts.append("unreadable: %s (%s)" % (os.path.basename(path), exc))
            continue

        for name, spec in model_materials(gltf).items():
            if spec[4]:
                textured_any = True
            prior = palette.get(name)
            if prior is None:
                palette[name] = spec
            elif not _spec_equal(prior, spec, tol):
                conflicts.append(
                    "material %r differs between files (%s)" % (name, os.path.basename(path))
                )

        stats = model_stats(gltf)
        if stats:
            stats["path"] = path
            stats["name"] = os.path.splitext(os.path.basename(path))[0]
            per_model.append(stats)

    if not per_model:
        return None

    pivots = [
        (_classify_axis(m["min"][0], m["max"][0], tol),
         _classify_axis(m["min"][2], m["max"][2], tol))
        for m in per_model
    ]
    bases = [round(m["min"][1], 4) for m in per_model]
    tris = sorted(m["triangles"] for m in per_model)

    return {
        "models": len(per_model),
        "palette": palette,
        "palette_conflicts": conflicts,
        "textured": textured_any,
        "pivot": _mode(pivots),
        "pivot_agreement": sum(1 for p in pivots if p == _mode(pivots)),
        "base": _mode(bases),
        "base_agreement": sum(1 for b in bases if b == _mode(bases)),
        "triangles": {"min": tris[0], "max": tris[-1], "median": tris[len(tris) // 2]},
        "footprints": sorted({round(m["size"][0], 2) for m in per_model}),
        "per_model": per_model,
    }


def _spec_equal(a, b, tol):
    return (
        all(abs(x - y) <= tol for x, y in zip(a[0], b[0]))
        and abs(a[1] - b[1]) <= tol
        and abs(a[2] - b[2]) <= tol
    )


# ----------------------------------------------------------------------- reporting

def print_contract(c, ref):
    print("Reference set: %s" % ref)
    print("Models: %d\n" % c["models"])

    print("PALETTE  (%d materials; linear baseColorFactor - copy these values verbatim)"
          % len(c["palette"]))
    for name in sorted(c["palette"]):
        base, metal, rough, ds, _tex = c["palette"][name]
        print("  %-16s rgb %.4f %.4f %.4f  a %.2f  metal %.2f  rough %.2f%s"
              % (name, base[0], base[1], base[2], base[3], metal, rough,
                 "  double-sided" if ds else ""))
    for problem in c["palette_conflicts"]:
        print("  WARNING  %s" % problem)

    px, pz = c["pivot"]
    print("\nPIVOT: %s-X / %s-Z  (%d of %d models agree)"
          % (px, pz, c["pivot_agreement"], c["models"]))
    if (px, pz) == ("min", "max"):
        print("  Corner pivot. Build wholly in Blender's +X/+Y/+Z octant and the exporter")
        print("  lands this convention for free (glTF y = blender z, glTF z = -blender y).")
    elif (px, pz) == ("centre", "centre"):
        print("  Centred. Centre your geometry on the origin in X and Y (Blender).")

    print("BASE: lowest point at y = %s  (%d of %d models agree)"
          % (c["base"], c["base_agreement"], c["models"]))
    t = c["triangles"]
    print("TRIANGLES: %d..%d, median %d  - the set's real budget"
          % (t["min"], t["max"], t["median"]))
    print("TEXTURES: %s" % (
        "external images - a new asset needs UVs that sample them"
        if c["textured"] else
        "none; the art style IS the named flat materials, so names are load-bearing"))

    widths = ", ".join("%.2f" % w for w in c["footprints"][:12])
    print("FOOTPRINT WIDTHS: %s%s"
          % (widths, " ..." if len(c["footprints"]) > 12 else ""))


# ------------------------------------------------------------------------- checking

def check_candidate(contract, path, tol):
    """Validate one model against the contract. Returns a list of failure strings."""
    problems = []
    try:
        gltf = load_gltf(path)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return ["unreadable: %s" % exc]

    stats = model_stats(gltf)
    if stats is None:
        return ["no mesh geometry found - nothing was exported"]

    # Materials: known names, matching values.
    for name, spec in model_materials(gltf).items():
        ref = contract["palette"].get(name)
        if ref is None:
            close = [n for n in contract["palette"] if n.split(".")[0] == name.split(".")[0]]
            hint = ("  (did you mean %r? a '.00N' suffix means a stale datablock held "
                    "the name)" % close[0]) if close else ""
            problems.append("material %r is not in the reference set%s" % (name, hint))
        elif not _spec_equal(ref, spec, tol):
            problems.append(
                "material %r has different values from the set: rgb %s vs %s"
                % (name, [round(v, 4) for v in spec[0]], [round(v, 4) for v in ref[0]]))

    # Duplicate-suffix names anywhere. These export silently and change identity.
    for label, names in (("material", list(model_materials(gltf))),
                         ("mesh", stats["mesh_names"]),
                         ("node", stats["node_names"])):
        for name in names:
            tail = name.rsplit(".", 1)[-1]
            if len(tail) == 3 and tail.isdigit():
                problems.append(
                    "%s name %r carries a duplicate suffix - purge the stale datablock "
                    "and reclaim the name before exporting" % (label, name))

    # Pivot and base.
    px = _classify_axis(stats["min"][0], stats["max"][0], tol)
    pz = _classify_axis(stats["min"][2], stats["max"][2], tol)
    if (px, pz) != tuple(contract["pivot"]):
        problems.append(
            "pivot is %s-X/%s-Z but the set uses %s-X/%s-Z (bbox min %s, max %s)"
            % (px, pz, contract["pivot"][0], contract["pivot"][1],
               [round(v, 4) for v in stats["min"]], [round(v, 4) for v in stats["max"]]))

    base = round(stats["min"][1], 4)
    if abs(base - contract["base"]) > max(tol, 1e-4):
        problems.append("base sits at y = %s but the set rests at y = %s"
                        % (base, contract["base"]))

    # Triangle budget - a soft bound, so only a wild overrun is worth flagging.
    hi = contract["triangles"]["max"]
    if stats["triangles"] > max(hi * 3, hi + 200):
        problems.append(
            "%d triangles against a set maximum of %d - likely off-style, though a "
            "genuinely more detailed asset may be fine; say which you decided"
            % (stats["triangles"], hi))

    # Textured state.
    cand_tex = any(spec[4] for spec in model_materials(gltf).values())
    if cand_tex and not contract["textured"]:
        problems.append("candidate is textured but the reference set is flat-material only")
    if not cand_tex and contract["textured"] and model_materials(gltf):
        problems.append("reference set is textured but the candidate samples no texture")

    return problems


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("reference", help="directory (or single file) of reference models")
    ap.add_argument("--check", metavar="FILE", help="validate this model against the set")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--tolerance", type=float, default=EPS,
                    help="float comparison tolerance (default %(default)s)")
    args = ap.parse_args(argv)

    paths = find_models(args.reference)
    if not paths:
        print("no .glb/.gltf models found under %s" % args.reference, file=sys.stderr)
        return 2

    # A candidate living inside the reference directory must not define the very
    # contract it is being judged against - that is drift with nothing to notice it.
    exclude = [args.check] if args.check else []
    contract = build_contract(paths, args.tolerance, exclude=exclude)
    if contract is None:
        print("no readable geometry in %s" % args.reference, file=sys.stderr)
        return 2

    if args.check:
        if not os.path.isfile(args.check):
            print("no such file: %s" % args.check, file=sys.stderr)
            return 2
        problems = check_candidate(contract, args.check, args.tolerance)
        name = os.path.basename(args.check)
        if args.json:
            print(json.dumps({"candidate": name, "passed": not problems,
                              "problems": problems}, indent=2))
        elif problems:
            print("FAIL  %s does not conform to %s\n" % (name, args.reference))
            for p in problems:
                print("  - %s" % p)
        else:
            print("PASS  %s conforms to the %d-model reference set"
                  % (name, contract["models"]))
            stats = model_stats(load_gltf(args.check))
            print("      size %s  pivot %s  %d triangles"
                  % ([round(v, 4) for v in stats["size"]],
                     "/".join(contract["pivot"]), stats["triangles"]))
        return 1 if problems else 0

    if args.json:
        out = dict(contract)
        out["palette"] = {k: {"base_color": list(v[0]), "metallic": v[1],
                              "roughness": v[2], "double_sided": v[3]}
                          for k, v in contract["palette"].items()}
        out.pop("per_model")
        print(json.dumps(out, indent=2))
    else:
        print_contract(contract, args.reference)
    return 0


if __name__ == "__main__":
    sys.exit(main())
