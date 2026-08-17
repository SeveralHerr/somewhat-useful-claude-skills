#!/usr/bin/env python3
"""Turn a raw gameplay screenshot into itch.io store art, and read a palette off it.

Why this exists as a script rather than instructions: the two things that make game
screenshots look right on a store page are both easy to get subtly wrong by hand.

  1. Integer downscale. Pixel art is drawn at some integer zoom, so a 1920x1080 grab has
     each source pixel as an NxN block. Resampling by a non-integer factor smears those
     blocks and the art reads as blurry JPEG mush. This crops an exact multiple of the
     target and then box-filters by that whole number, so blocks stay square.

  2. Supersampled text. An antialiased vector glyph laid over hard-edged pixel art reads
     as a sticker someone stuck on afterwards. Rendering the title small and blowing it up
     with NEAREST puts the letterforms on the same pixel grid as the game.

Usage:
    python store_art.py palette --src shot.png
    python store_art.py cover   --src shot.png --out cover.png  --title "GAME" --subtitle "tagline"
    python store_art.py banner  --src shot.png --out banner.png --title "GAME"

Requires Pillow.
"""

import argparse
import os
import sys
from collections import Counter

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Pillow is required:  pip install Pillow")

COVER = (630, 500)   # itch.io recommended cover; min 315x250
BANNER = (960, 400)  # page banner, shown full width above the content column

# Heavy grotesques first: at 3-4x supersampling, thin strokes disappear entirely.
FONT_CANDIDATES = [
    "C:/Windows/Fonts/ariblk.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit("No heavy sans font found. Pass one via --font.")


def integer_crop(im, target, focus=None):
    """Crop the largest exact integer multiple of `target`, then box-filter down to it.

    Falls back to a plain resize only if the source is smaller than the target, which
    means the art was never big enough for a clean downscale in the first place.
    """
    tw, th = target
    k = min(im.width // tw, im.height // th)
    if k < 1:
        return im.resize(target, Image.BOX)
    cw, ch = tw * k, th * k
    cx, cy = focus if focus else (im.width // 2, im.height // 2)
    left = max(0, min(im.width - cw, cx - cw // 2))
    top = max(0, min(im.height - ch, cy - ch // 2))
    return im.crop((left, top, left + cw, top + ch)).resize(target, Image.BOX)


def pixel_text(text, px, fill, outline, font_path, outline_w=1):
    """Render `text` at 1/scale then NEAREST-upscale, so glyphs share the art's grid.

    `scale` is derived from the requested height rather than fixed: at a fixed 4x, small
    subtitles get only ~8px of font to work with and the glyphs collapse into blocks.
    """
    scale = max(1, min(4, px // 12))
    font = ImageFont.truetype(font_path, max(6, px // scale))
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font)
    pad = outline_w + 1
    small = Image.new("RGBA", (r - l + pad * 2, b - t + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(small)
    for dx in range(-outline_w, outline_w + 1):
        for dy in range(-outline_w, outline_w + 1):
            if dx or dy:
                d.text((pad - l + dx, pad - t + dy), text, font=font, fill=outline)
    d.text((pad - l, pad - t), text, font=font, fill=fill)
    return small.resize((small.width * scale, small.height * scale), Image.NEAREST)


def add_scrim(im, side, strength=185):
    """Darken one edge so light text keeps its edges over bright terrain.

    A solid bar would be easier but hides the art; a gradient keeps the scene readable
    underneath, which is the whole reason to use a real screenshot as the cover.
    """
    w, h = im.size
    scrim = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(scrim)
    if side == "bottom":
        for y in range(h):
            d.line([(0, y), (w, y)], fill=(10, 22, 40, int(strength * (y / h) ** 1.4)))
    elif side == "left":
        for x in range(w):
            a = int(strength * max(0.0, 1 - x / (w * 0.62)) ** 1.3)
            d.line([(x, 0), (x, h)], fill=(10, 22, 40, a))
    im.alpha_composite(scrim)


def fit_text(text, px, fill, outline, font_path, max_w):
    """pixel_text at the largest size <= px whose strip is no wider than max_w."""
    strip = pixel_text(text, px, fill, outline, font_path)
    while strip.width > max_w and px > 12:
        px = max(12, int(px * 0.9))
        strip = pixel_text(text, px, fill, outline, font_path)
    if strip.width > max_w:
        print(f"WARN: '{text}' still {strip.width}px wide at the minimum size; it will clip", file=sys.stderr)
    return strip


def build(args, target, default_scrim, title_px, sub_px):
    src = Image.open(args.src).convert("RGB")
    focus = tuple(int(v) for v in args.focus.split(",")) if args.focus else None
    im = integer_crop(src, target, focus).convert("RGBA")

    if args.title or args.subtitle:
        side = args.scrim or default_scrim
        if side != "none":
            add_scrim(im, side)
        font = args.font or find_font()
        fill = (255, 226, 138, 255)
        parts = []
        # Fit to width: a title px is a ceiling, not a size. "PEST CONTROL" at the
        # cover's default 96px is wider than the 630px cover and both ends were cut
        # off, silently - nothing errors on an overflowing composite. Step the size
        # down (in the pixel grid's steps) until the rendered strip fits with margin.
        max_w = target[0] - 2 * (54 if side == "left" else 20)
        if args.title:
            parts.append(fit_text(args.title, title_px, fill, (28, 22, 14, 255), font, max_w))
        if args.subtitle:
            parts.append(
                fit_text(args.subtitle, sub_px, (206, 236, 255, 255), (22, 32, 48, 255), font, max_w)
            )
        total = sum(p.height for p in parts) + (10 if len(parts) > 1 else 0)
        if side == "left":
            x, y = 54, (target[1] - total) // 2
            for p in parts:
                im.alpha_composite(p, (x, y))
                y += p.height + 10
        else:  # bottom
            y = target[1] - total - 14
            for p in parts:
                im.alpha_composite(p, ((target[0] - p.width) // 2, y))
                y += p.height + 10

    im.convert("RGB").save(args.out)
    print(f"{args.out}  {Image.open(args.out).size}  {os.path.getsize(args.out)//1024} KB")


def palette(args):
    """Dominant colours, for deriving page theme colours from the game's own art.

    A theme built from the real palette reads as an extension of the game; one picked by
    eye usually clashes with the screenshots sitting next to it.
    """
    im = Image.open(args.src).convert("RGB")
    c = Counter(im.getdata())
    total = sum(c.values())
    print(f"{'hex':9} {'share':>7}  swatch")
    for rgb, n in c.most_common(args.count):
        print(f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}  {100*n/total:6.2f}%  rgb{rgb}")
    print(
        "\nPick a dark one for BG, a second dark for BG 2, the most saturated "
        "for links/buttons, and lighten a mid tone for body text (aim >=4.5:1)."
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("cover", "banner", "palette"):
        p = sub.add_parser(name)
        p.add_argument("--src", required=True, help="raw gameplay screenshot")
        if name == "palette":
            p.add_argument("--count", type=int, default=12)
        else:
            p.add_argument("--out", required=True)
            p.add_argument("--title")
            p.add_argument("--subtitle")
            p.add_argument("--font")
            p.add_argument("--scrim", choices=["bottom", "left", "none"])
            p.add_argument("--focus", help="x,y in source pixels to centre the crop on")
    a = ap.parse_args()

    if a.cmd == "palette":
        palette(a)
    elif a.cmd == "cover":
        build(a, COVER, "bottom", 84, 40)
    else:
        build(a, BANNER, "left", 116, 42)


if __name__ == "__main__":
    main()
