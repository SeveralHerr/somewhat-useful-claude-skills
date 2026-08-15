#!/usr/bin/env python3
"""Measure a Kenney 2D pack: canvas, retina ratio, content box, palette - and gate
a new sprite against it.

Reads PNG directly (stdlib only - zlib and struct, no Pillow, nothing written):

    python kenney_probe2d.py "<pack dir>"                        # pack-wide contract
    python kenney_probe2d.py "<pack dir>" --sprites towerDefense_tile180
    python kenney_probe2d.py "<pack dir>" --json
    python kenney_probe2d.py "<pack dir>" --check new.png        # exits 1 on a mismatch

The 2D counterpart of `kenney_probe.py`, and the same idea pointed the other way:
`kenney_probe.py` measures a kit so you can PLACE from it; this measures a pack so
you can AUTHOR into it, and `--check` re-derives the contract to gate an export.

The one rule that is not guessable: "on-palette" cannot mean "equals a palette
entry". Kenney's vector packs are anti-aliased, so the pixels along the seam
between two flat fills land ON THE SEGMENT between those two colours in RGB.
Exact membership false-fails on every sprite in the pack, Kenney's own included.
The test has to be distance to the nearest palette-PAIR segment - see PALETTE_TOL.
"""

import argparse
import json
import os
import struct
import sys
import zlib
from collections import Counter

# ------------------------------------------------------------------------ PNG IO

_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _chunks(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    off = 8
    while off + 8 <= len(data):
        (length,) = struct.unpack_from(">I", data, off)
        yield data[off + 4:off + 8], data[off + 8:off + 8 + length]
        off += 12 + length


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter(raw, stride, height, bpp):
    """Undo the per-scanline filter PNG applies before deflate."""
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                c = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(a, prev[i], c)) & 255
        elif f != 0:
            raise ValueError("unknown scanline filter %d" % f)
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def _row_samples(row, count, depth, scale):
    """One scanline of packed samples as a list of ints.

    `scale` widens sub-byte GREY samples to 0..255; palette indices must not be
    scaled, so indexed images pass scale=False. Getting that backwards turns a
    4-bit indexed sprite into a lookup miles past the end of PLTE.
    """
    if depth == 8:
        return list(row[:count])
    if depth == 16:
        return list(row[0:count * 2:2])          # high byte; 8 bits is all we compare on
    per = 8 // depth
    mask = (1 << depth) - 1
    maxv = mask
    out = []
    for i in range(count):
        byte = row[i // per]
        shift = 8 - depth * (i % per + 1)
        v = (byte >> shift) & mask
        out.append(v * 255 // maxv if scale else v)
    return out


def read_png(path):
    """Return (width, height, bytearray of RGBA8). Non-interlaced PNG only.

    Every colour type and bit depth Kenney actually ships is covered: a survey of
    38k PNGs across the 2D packs finds indexed at 1/2/4/8 bits, RGBA at 8 and 16,
    and one grey+alpha. Adam7 appears nowhere and is rejected loudly rather than
    decoded wrong.
    """
    with open(path, "rb") as fh:
        data = fh.read()

    hdr, plte, trns, idat = None, b"", None, []
    for typ, body in _chunks(data):
        if typ == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body[:13])
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    if hdr is None:
        raise ValueError("no IHDR chunk")

    w, h, depth, ctype, _comp, _filt, interlace = hdr
    if interlace:
        raise ValueError("interlaced (Adam7) PNG - re-export without interlacing")
    channels = _CHANNELS.get(ctype)
    if channels is None:
        raise ValueError("unknown PNG colour type %d" % ctype)

    stride = (w * channels * depth + 7) // 8
    bpp = max(1, (channels * depth) // 8)
    raw = _unfilter(zlib.decompress(b"".join(idat)), stride, h, bpp)

    # tRNS means different things per colour type: a per-entry alpha table for
    # indexed, and a single fully transparent sample value for grey/truecolour.
    pal_alpha = list(trns) if (ctype == 3 and trns) else []
    key = None
    if trns and ctype in (0, 2):
        vals = struct.unpack(">%dH" % (len(trns) // 2), trns)
        key = tuple(v >> 8 for v in vals) if depth == 16 else tuple(vals)

    rgba = bytearray(w * h * 4)
    for y in range(h):
        row = raw[y * stride:(y + 1) * stride]
        s = _row_samples(row, w * channels, depth, ctype != 3)
        o = y * w * 4
        for x in range(w):
            i = x * channels
            if ctype == 3:
                idx = s[i]
                p = idx * 3
                r, g, b = plte[p], plte[p + 1], plte[p + 2]
                a = pal_alpha[idx] if idx < len(pal_alpha) else 255
            elif ctype == 0:
                r = g = b = s[i]
                a = 0 if key and s[i] == key[0] else 255
            elif ctype == 2:
                r, g, b = s[i], s[i + 1], s[i + 2]
                a = 0 if key and (r, g, b) == key else 255
            elif ctype == 4:
                r = g = b = s[i]
                a = s[i + 1]
            else:
                r, g, b, a = s[i], s[i + 1], s[i + 2], s[i + 3]
            j = o + x * 4
            rgba[j] = r
            rgba[j + 1] = g
            rgba[j + 2] = b
            rgba[j + 3] = a
    return w, h, rgba


# ----------------------------------------------------------------------- measure

def measure(path):
    """Measure one sprite: canvas, opaque bounding box, margins, opaque colours."""
    w, h, rgba = read_png(path)

    x0, y0, x1, y1 = w, h, -1, -1
    colors = Counter()
    transparent = 0
    for y in range(h):
        row = rgba[y * w * 4:(y + 1) * w * 4]
        alpha = row[3::4]
        if not any(alpha):
            transparent += w
            continue
        first = next(i for i, a in enumerate(alpha) if a)
        last = w - 1 - next(i for i, a in enumerate(reversed(alpha)) if a)
        if first < x0:
            x0 = first
        if last > x1:
            x1 = last
        if y < y0:
            y0 = y
        y1 = y
        for x in range(w):
            a = alpha[x]
            if a == 0:
                transparent += 1
            elif a == 255:
                # Only FULLY opaque pixels define or test the palette. A pixel
                # anti-aliased against the transparent background carries the fill
                # colour at partial alpha; counting it as a flat colour would put
                # every unblended fill twice in the histogram.
                j = x * 4
                colors[(row[j], row[j + 1], row[j + 2])] += 1

    if x1 < 0:
        return {"name": os.path.splitext(os.path.basename(path))[0], "path": path,
                "canvas": [w, h], "blank": True, "colors": Counter()}

    return {
        "name": os.path.splitext(os.path.basename(path))[0],
        "path": path,
        "canvas": [w, h],
        "blank": False,
        "bbox": [x0, y0, x1, y1],
        "content": [x1 - x0 + 1, y1 - y0 + 1],
        "margins": [x0, w - 1 - x1, y0, h - 1 - y1],       # left, right, top, bottom
        # Where the content sits across the canvas, -0.5..+0.5 of canvas width.
        "offset_x": round(((x0 + x1 + 1) / 2.0 - w / 2.0) / w, 4),
        "offset_y": round(((y0 + y1 + 1) / 2.0 - h / 2.0) / h, 4),
        # Reaching all four edges, NOT "has no transparent pixel". A water tile
        # with a transparent notch is still a tile, and classing it as an object
        # drags the pack's minimum margin to 0 and disarms the margin check.
        "full_bleed": (x0, y0, x1, y1) == (0, 0, w - 1, h - 1),
        "opaque": transparent == 0,
        "colors": colors,
    }


# ------------------------------------------------------------------- pack survey

# Directories that hold the same art at another resolution or packed into a sheet.
# Surveying them alongside PNG/ double-counts every colour and makes the canvas
# size look bimodal, so the sprite scan picks exactly one directory.
_RETINA = ("retina", "@2x", "double")
_SKIP = ("tilesheet", "spritesheet", "sheet", "vector", "preview", "sample",
         "backgrounds")


def find_sprite_dir(pack_dir):
    """The directory of individual sprites, plus the retina twin if one ships.

    Returns (sprite_dir, count, retina_dir_or_None).
    """
    best, best_rank, retina = None, 99, None
    for root, _dirs, files in os.walk(pack_dir):
        n = sum(1 for f in files if f.lower().endswith(".png"))
        if not n:
            continue
        low = os.path.basename(root).lower()
        rel = os.path.relpath(root, pack_dir).lower()
        if any(k in low for k in _RETINA):
            if retina is None or n > retina[1]:
                retina = (root, n)
            continue
        if any(k in rel for k in _SKIP):
            continue
        rank = 0 if "default" in low else (1 if "png" in rel else 2)
        if rank < best_rank or (rank == best_rank and best and n > best[1]):
            best, best_rank = (root, n), rank
    if best is None:
        return None
    return best[0], best[1], (retina[0] if retina else None)


# Above this many distinct opaque shades the art is not flat-colour and the whole
# palette idea stops applying; the survey says so rather than reporting a
# meaningless 96-entry list.
PALETTE_MAX = 96


def _derive_palette(colors, tol):
    """The colours Kenney CHOSE, separated from the blends between them.

    Frequency alone cannot do this. Sorting the Tower Defense pack by pixel count
    puts #2ECC71 first and #2DCB70 twenty-eight places later - the second is an
    anti-aliased shade of the first, one unit away in RGB, and no threshold on
    count tells them apart because a small object's genuine fill is rarer than a
    big tile's blend.

    So take colours in frequency order and admit one only when it is more than
    `tol` from everything already admitted - measured with the same
    segment metric `--check` uses, so a colour that is merely a mix of two
    entries is rejected too. 1270 shades collapse to 26 on that pack, and the
    leave-one-out worst case (any one sprite judged against the other 298) is
    6.6, half the tolerance.
    """
    if not colors:
        return []
    kept = []
    for rgb, _n in colors.most_common():
        if palette_distance(rgb, kept, limit=tol) > tol:
            kept.append(rgb)
            if len(kept) >= PALETTE_MAX:
                break
    # Report each entry with the area it accounts for, not just its own pixels:
    # a fill's anti-aliased skirt belongs to it, and #ECDCB8's own count under-
    # states how much of the pack is sand.
    area = Counter()
    for rgb, n in colors.items():
        best, hit = None, 0
        for i, e in enumerate(kept):
            d = (rgb[0] - e[0]) ** 2 + (rgb[1] - e[1]) ** 2 + (rgb[2] - e[2]) ** 2
            if best is None or d < best:
                best, hit = d, i
        area[hit] += n
    return [(kept[i], area[i]) for i in sorted(range(len(kept)), key=lambda i: -area[i])]


def _median(values):
    if not values:
        return None
    s = sorted(values)
    return s[len(s) // 2]


def survey(pack_dir, limit=None, exclude=(), tol=None):
    found = find_sprite_dir(pack_dir)
    if not found:
        raise SystemExit("No .png found under %s" % pack_dir)
    sprite_dir, _n, retina_dir = found
    skip = {os.path.abspath(p) for p in exclude}

    names = sorted(f for f in os.listdir(sprite_dir) if f.lower().endswith(".png"))
    if limit:
        names = names[:limit]

    sprites, failed = [], []
    for f in names:
        path = os.path.join(sprite_dir, f)
        if os.path.abspath(path) in skip:
            continue
        try:
            sprites.append(measure(path))
        except Exception as exc:                      # noqa: BLE001 - report, don't abort
            failed.append("%s: %s" % (f, exc))
    if not sprites:
        raise SystemExit("No readable PNG in %s" % sprite_dir)

    canvases = Counter(tuple(s["canvas"]) for s in sprites)
    canvas, canvas_n = canvases.most_common(1)[0]

    colors = Counter()
    for s in sprites:
        colors.update(s["colors"])
    palette = _derive_palette(colors, PALETTE_TOL if tol is None else tol)
    total_px = sum(colors.values()) or 1
    exact = sum(colors.get(rgb, 0) for rgb, _n in palette)

    drawn = [s for s in sprites if not s["blank"]]
    objects = [s for s in drawn if not s["full_bleed"]]
    contents = [max(s["content"]) for s in objects]
    margins = [min(s["margins"]) for s in objects]
    offsets = [abs(s["offset_x"]) for s in objects]

    return {
        "pack": os.path.basename(os.path.normpath(pack_dir)),
        "sprite_dir": sprite_dir,
        "retina_dir": retina_dir,
        "retina_ratio": _retina_ratio(sprite_dir, retina_dir, names),
        "count": len(sprites),
        "failed": failed,
        "canvas": list(canvas),
        "canvas_uniform": canvas_n == len(sprites),
        "canvas_sizes": [(list(k), v) for k, v in canvases.most_common(4)],
        "blank": [s["name"] for s in sprites if s["blank"]],
        "full_bleed": len([s for s in drawn if s["full_bleed"]]),
        "objects": len(objects),
        "palette_tolerance": PALETTE_TOL if tol is None else tol,
        "content_median": _median(contents),
        "content_max": max(contents) if contents else None,
        "content_min": min(contents) if contents else None,
        "margin_min": min(margins) if margins else None,
        "margin_median": _median(margins),
        "offset_x_max": round(max(offsets), 4) if offsets else None,
        "offset_x_median": round(_median(offsets), 4) if offsets else None,
        "distinct_opaque_colors": len(colors),
        "palette": [{"rgb": list(rgb), "hex": "#%02X%02X%02X" % rgb, "area": n,
                     "pixels": colors.get(rgb, 0)}
                    for rgb, n in palette],
        # How much of the pack is EXACTLY a palette entry. Everything else is
        # anti-aliasing, and the gap between this and 100% is what exact palette
        # membership would false-fail on.
        "palette_exact": round(exact / float(total_px), 4),
        "palette_saturated": len(palette) >= PALETTE_MAX,
        "sprites": [{k: v for k, v in s.items() if k != "colors"} for s in sprites],
    }


def _retina_ratio(sprite_dir, retina_dir, names, sample=6):
    """The factor between the two resolutions, measured rather than assumed.

    Reported as a float only when every sampled pair agrees; a pack whose retina
    art is not a clean multiple is one where --check's 2x rule does not apply.
    """
    if not retina_dir:
        return None
    ratios = set()
    for f in names[:sample]:
        twin = os.path.join(retina_dir, f)
        if not os.path.isfile(twin):
            return "incomplete"
        try:
            w, h, _ = read_png(os.path.join(sprite_dir, f))
            rw, rh, _ = read_png(twin)
        except Exception:                             # noqa: BLE001
            return "unreadable"
        if not w or not h:
            continue
        ratios.add((round(rw / float(w), 3), round(rh / float(h), 3)))
    if len(ratios) != 1:
        return "mixed"
    rx, ry = ratios.pop()
    return rx if rx == ry else [rx, ry]


# ------------------------------------------------------------- palette geometry

# Distance, in 0..255 RGB, at which a colour still counts as on-palette. It is
# measured against the nearest SEGMENT between two palette entries, not against
# the entries themselves, because an anti-aliased seam between two flat fills
# lands part-way along that segment. Measured on the Tower Defense pack: Kenney's
# own sprites blend up to ~8 off the nearest segment, while an off-palette hue
# dropped in as a negative control sits at ~190. Anything in 10..30 separates
# them; 12 is chosen to stay close to the observed ceiling.
PALETTE_TOL = 12.0


def _segment_distance(p, a, b):
    """Distance from colour p to the line segment ab, all in RGB."""
    ax, ay, az = a
    bx, by, bz = b
    dx, dy, dz = bx - ax, by - ay, bz - az
    den = dx * dx + dy * dy + dz * dz
    if den == 0:
        t = 0.0
    else:
        t = ((p[0] - ax) * dx + (p[1] - ay) * dy + (p[2] - az) * dz) / float(den)
        t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    ex = p[0] - (ax + t * dx)
    ey = p[1] - (ay + t * dy)
    ez = p[2] - (az + t * dz)
    return (ex * ex + ey * ey + ez * ez) ** 0.5


def palette_distance(rgb, palette, limit=None):
    """How far a colour is from the palette, allowing blends between any two entries.

    `limit` is an early exit: once the answer is known to be at or under it, the
    caller only wanted a yes/no, so stop pairing. That matters - the pair loop is
    quadratic in the palette and this runs once per distinct colour.
    """
    if not palette:
        return float("inf")
    best = min(_segment_distance(rgb, e, e) for e in palette)
    if limit is not None and best <= limit:
        return best
    for i, a in enumerate(palette):
        for b in palette[i + 1:]:
            d = _segment_distance(rgb, a, b)
            if d < best:
                best = d
                if limit is not None and best <= limit:
                    return best
                if best <= 0.0:
                    return 0.0
    return best


# ------------------------------------------------------------------------ check

def _retina_twin(path):
    """Where a candidate's 2x counterpart would live, by the conventions in use."""
    d, base = os.path.split(os.path.abspath(path))
    stem, ext = os.path.splitext(base)
    return [
        os.path.join(d, "Retina", base),
        os.path.join(os.path.dirname(d), "Retina", base),
        os.path.join(d, stem + "@2x" + ext),
    ]


def check_candidate(contract, path, tol=PALETTE_TOL):
    """Validate one sprite against the pack contract. Returns a list of failures."""
    problems = []
    try:
        m = measure(path)
    except (ValueError, OSError, zlib.error) as exc:
        return ["unreadable: %s" % exc], None

    canvas = contract["canvas"]
    # Only a pack where EVERY sprite shares a canvas has a canvas to conform to.
    # A sprite pack's files are cropped to their own art, and demanding the modal
    # size there fails almost every legitimate candidate.
    if contract["canvas_uniform"] and m["canvas"] != canvas:
        problems.append("canvas is %dx%d but the pack is %dx%d"
                        % (m["canvas"][0], m["canvas"][1], canvas[0], canvas[1]))
    if m["blank"]:
        problems.append("no opaque pixels - the export is empty")
        return problems, m

    ratio = contract.get("retina_ratio")
    if isinstance(ratio, (int, float)):
        twins = [p for p in _retina_twin(path) if os.path.isfile(p)]
        if not twins:
            problems.append(
                "the pack ships a %gx retina copy of every sprite and this has none "
                "(looked for %s)" % (ratio, ", ".join(
                    os.path.relpath(p, os.path.dirname(os.path.abspath(path)))
                    for p in _retina_twin(path))))
        else:
            try:
                rw, rh, _ = read_png(twins[0])
            except Exception as exc:                  # noqa: BLE001
                problems.append("retina copy %s is unreadable: %s" % (twins[0], exc))
            else:
                want = (int(canvas[0] * ratio), int(canvas[1] * ratio))
                if (rw, rh) != want:
                    problems.append("retina copy is %dx%d but must be %dx%d (%gx)"
                                    % (rw, rh, want[0], want[1], ratio))

    if not m["full_bleed"] and contract["canvas_uniform"]:
        # Every bound here is the pack's own observed extreme, never a chosen
        # number. A pixel pack whose art runs to the edge reports margin_min 0 and
        # the rule switches itself off, which is correct: it is not a rule there.
        floor = contract.get("margin_min") or 0
        if floor and min(m["margins"]) < floor:
            problems.append(
                "content comes within %d px of the canvas edge (margins l/r/t/b = %s); "
                "the pack keeps at least %d px of clear space around an object"
                % (min(m["margins"]), m["margins"], floor))
        limit = max(0.06, (contract.get("offset_x_max") or 0.0) + 0.01)
        if abs(m["offset_x"]) > limit:
            problems.append(
                "content sits %+.1f%% off the vertical axis; the pack's furthest is "
                "%+.1f%%. Sprites are placed by their centre, so an off-axis object "
                "will not line up with its own tile"
                % (m["offset_x"] * 100, (contract.get("offset_x_max") or 0.0) * 100))
        if contract.get("content_max") and max(m["content"]) > contract["content_max"]:
            problems.append("content is %d px across, larger than anything in the pack "
                            "(max %d)" % (max(m["content"]), contract["content_max"]))

    # A pack whose colours did not cluster is not flat-colour art, and running the
    # palette test against a saturated 96-entry list would pass anything.
    palette = [] if contract.get("palette_saturated") else [
        tuple(e["rgb"]) for e in contract["palette"]]
    offenders = []
    for rgb, n in m["colors"].most_common() if palette else ():
        d = palette_distance(rgb, palette, limit=tol)
        if d > tol:
            offenders.append((rgb, n, d))
    if offenders:
        offenders.sort(key=lambda o: -o[1])
        for rgb, n, d in offenders[:6]:
            problems.append("#%02X%02X%02X (%d px) is %.1f off the palette - past the "
                            "%.0f a blend between two entries can reach"
                            % (rgb[0], rgb[1], rgb[2], n, d, tol))
        if len(offenders) > 6:
            problems.append("... and %d more off-palette colours"
                            % (len(offenders) - 6))
    return problems, m


# ----------------------------------------------------------------------- report

def print_survey(s):
    print("Pack: %s" % s["pack"])
    print("Sprites: %d in %s" % (s["count"], s["sprite_dir"]))
    if s["failed"]:
        print("Unreadable: %d  (%s)" % (len(s["failed"]), s["failed"][0]))
    print()

    print("CANVAS: %dx%d%s" % (s["canvas"][0], s["canvas"][1],
                               "  (every sprite)" if s["canvas_uniform"] else ""))
    if not s["canvas_uniform"]:
        print("  !! mixed: %s" % ", ".join("%dx%d x%d" % (c[0], c[1], n)
                                           for c, n in s["canvas_sizes"]))
        print("  A pack with no single canvas is a SPRITE pack, not a tile pack - place")
        print("  its art by its own bounding box and ignore the content-box lines below.")
    else:
        print("  Author at exactly this size. A tile pack's canvas IS its grid cell, so a")
        print("  sprite drawn 'about the same size' lands off the grid by the difference.")

    if s["retina_dir"]:
        print("RETINA: %s at %s" % (os.path.basename(s["retina_dir"]),
                                    _fmt_ratio(s["retina_ratio"])))
        print("  Ship both, or the pack stops being uniform the moment someone imports the")
        print("  retina set. Godot picks the folder; nothing reconciles a missing file.")
    else:
        print("RETINA: none - this pack ships one resolution")

    if s["objects"] and s["canvas_uniform"]:
        print("CONTENT BOX (%d objects; %d full-bleed tiles excluded):" % (
            s["objects"], s["full_bleed"]))
        print("  spans %d-%d px of the %d px canvas, median %d"
              % (s["content_min"], s["content_max"], s["canvas"][0], s["content_median"]))
        if s["margin_min"]:
            print("  clear margin at least %d px (median %d)"
                  % (s["margin_min"], s["margin_median"]))
        else:
            print("  margin: some objects run to the canvas edge, so this pack has no clear-")
            print("    space rule and --check does not impose one")
        print("  off-axis by at most %.1f%% of the canvas (median %.1f%%)"
              % (s["offset_x_max"] * 100, s["offset_x_median"] * 100))
        print("  This is the 'does it belong' measurement. An object drawn to the full")
        print("  canvas reads as oversized next to the pack even when its colours match,")
        print("  because every neighbour leaves the same air around itself.")
    if s["full_bleed"] and s["canvas_uniform"]:
        print("FULL-BLEED: %d sprites reach all four canvas edges - the terrain tiles."
              % s["full_bleed"])
        print("  They are the exception to every margin rule above; they tile edge to edge.")
    elif s["full_bleed"]:
        print("CROPPED: %d of %d sprites reach all four canvas edges."
              % (s["full_bleed"], s["count"]))
        print("  On a pack with no shared canvas that is not a tile - it means the art is")
        print("  cropped to its own bounding box. Author the same way: trim, and let the")
        print("  file size BE the sprite size rather than padding to a square.")
    if s["blank"]:
        print("BLANK: %d sprite(s) are entirely transparent: %s"
              % (len(s["blank"]), ", ".join(s["blank"][:4])))

    _print_palette(s)


def _fmt_ratio(r):
    if isinstance(r, (int, float)):
        return "exactly %gx" % r
    if isinstance(r, list):
        return "%gx by %gx - NOT square" % tuple(r)
    return r or "unknown"


def _print_palette(s):
    p = s["palette"]
    if not p:
        return
    if s.get("palette_saturated"):
        print("PALETTE: more than %d distinct colours survive clustering (%d raw shades)."
              % (PALETTE_MAX, s["distinct_opaque_colors"]))
        print("  This is not flat-colour art - it is a gradient, photographic or pixel-")
        print("  dithered pack. The palette contract below does not describe it and")
        print("  --check's colour test will be meaningless. Match this pack by eye.")
        return
    print("PALETTE: %d colours, from %d distinct opaque shades. %.1f%% of the pack's "
          "opaque pixels are EXACTLY one of them." % (
              len(p), s["distinct_opaque_colors"], s["palette_exact"] * 100))
    for e in p[:24]:
        print("  %s  %6d px  rgb%s" % (e["hex"], e["area"], tuple(e["rgb"])))
    if len(p) > 24:
        print("  ... %d more (--json for all)" % (len(p) - 24))
    tol = s.get("palette_tolerance", PALETTE_TOL)
    if s["palette_exact"] < 0.99:
        print("  The other %.1f%% is ANTI-ALIASING, and it is the whole reason --check works"
              % ((1 - s["palette_exact"]) * 100))
        print("  the way it does. A pixel on the seam between two flat fills lands part-way")
        print("  ALONG THE SEGMENT between them in RGB, so testing a new sprite for exact")
        print("  palette membership fails on every sprite in this pack, Kenney's included.")
        print("  --check measures distance to the nearest segment between any two entries.")
    else:
        print("  Every opaque pixel is one of them: this pack is not anti-aliased at all, so")
        print("  a new sprite may use these colours and nothing between them.")
    if s["palette_exact"] < 0.70:
        print("  !! only %.0f%% exact - this pack is SHADED rather than flat, so the blend"
              % (s["palette_exact"] * 100))
        print("  cloud is wide and tolerance %.0f leaves little headroom (Kenney's own art"
              % tol)
        print("  reaches ~11 here against ~7 on a flat pack). Raise --tolerance to 16 before")
        print("  believing a colour failure on this one.")

    # Only worth saying where it is true. A 1-bit pack's palette IS black and white,
    # and printing the rule there contradicts the list directly above it.
    if palette_distance((0, 0, 0), [tuple(e["rgb"]) for e in p]) > tol:
        print("  Note what is NOT here: black. Kenney outlines an object in a DARKER SHADE OF")
        print("  ITS OWN FILL, never in black or grey. That single rule is most of what makes")
        print("  a new sprite look native - see the Vector/ SVGs, where the rim is a separate")
        print("  filled path under the fill rather than a stroke.")


def print_sprites(s, wanted):
    index = {x["name"]: x for x in s["sprites"]}
    for name in wanted:
        m = index.get(name)
        if not m:
            hits = [k for k in index if name.lower() in k.lower()]
            if not hits:
                print("%-30s NOT FOUND" % name)
                continue
            m = index[hits[0]]
        if m["blank"]:
            print("%-30s %dx%d  BLANK" % (m["name"], m["canvas"][0], m["canvas"][1]))
            continue
        print("%-30s %dx%d  content %dx%d at (%d,%d)  margins l/r/t/b %s  off-axis "
              "%+.1f%%%s" % (
                  m["name"], m["canvas"][0], m["canvas"][1], m["content"][0],
                  m["content"][1], m["bbox"][0], m["bbox"][1], m["margins"],
                  m["offset_x"] * 100, "  full-bleed" if m["full_bleed"] else ""))


# ------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pack_dir", help="a Kenney 2D pack directory (or its PNG subdir)")
    ap.add_argument("--check", metavar="FILE", help="validate this sprite against the pack")
    ap.add_argument("--sprites", nargs="+", metavar="NAME",
                    help="print these sprites in detail (substring match)")
    ap.add_argument("--limit", type=int, help="only read the first N sprites")
    ap.add_argument("--tolerance", type=float, default=PALETTE_TOL,
                    help="off-palette RGB distance to fail on (default %(default)s)")
    ap.add_argument("--json", action="store_true", help="dump everything as JSON")
    args = ap.parse_args(argv)

    if args.check and not os.path.isfile(args.check):
        print("no such file: %s" % args.check, file=sys.stderr)
        return 2

    # A candidate sitting inside the pack directory must not help define the very
    # contract it is being judged against - that is drift with nothing to notice it.
    s = survey(args.pack_dir, limit=args.limit, tol=args.tolerance,
               exclude=[args.check] if args.check else [])

    if args.check:
        problems, m = check_candidate(s, args.check, args.tolerance)
        name = os.path.basename(args.check)
        if args.json:
            print(json.dumps({"candidate": name, "passed": not problems,
                              "problems": problems}, indent=2))
        elif problems:
            print("FAIL  %s does not conform to %s\n" % (name, s["pack"]))
            for p in problems:
                print("  - %s" % p)
        else:
            print("PASS  %s conforms to the %d-sprite pack" % (name, s["count"]))
            print("      %dx%d  content %dx%d  margins %s  %d opaque colours, all on-palette"
                  % (m["canvas"][0], m["canvas"][1], m["content"][0], m["content"][1],
                     m["margins"], len(m["colors"])))
        return 1 if problems else 0

    if args.json:
        print(json.dumps(s, indent=1))
        return 0

    print_survey(s)
    if args.sprites:
        print()
        print_sprites(s, args.sprites)
    return 0


if __name__ == "__main__":
    sys.exit(main())
