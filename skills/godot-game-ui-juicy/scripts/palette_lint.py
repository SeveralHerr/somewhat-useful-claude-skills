#!/usr/bin/env python3
"""Find colours that a re-skin cannot reach, and text a re-skin has made unreadable.

`ui_theme.gd` promises that changing the PALETTE block changes the whole art direction, and
`scaffold_ui.py` repeats that promise to every user. A `Color(...)` literal written anywhere
else quietly breaks it: it renders correctly today and then survives the palette change,
leaving the old hue sitting in an otherwise re-skinned UI.

The reason this needs a *source* lint rather than a runtime assertion is the whole point of
the check. Against the palette that shipped, `Color(0.06, 0.05, 0.07, 1.0)` is numerically
identical to the constant it should have read, so a test that walks the built tree sees the
same `ColorRect.color` either way and cannot tell "reads BACKDROP" from "hard-codes what
BACKDROP happens to be". The two are only distinguishable in the text. Four such leaks
shipped at once in 0.6.0 for exactly that reason, and a fifth class — art direction hidden in
`ui_theme.gd`'s own function bodies, below the block a palette substitutes — outlived them.

Three rules, in increasing order of how obvious the violation is:

  A. Outside `ui_theme.gd`, no chromatic `Color(...)` literal at all. That file is the whole
     art direction or the claim in the scaffolder output is false.
  B. Inside `ui_theme.gd`, no literal below the PALETTE block may repeat a palette constant's
     RGB. This is the 0.6.0 defect: invisible now, wrong after one re-skin.
  C. Inside `ui_theme.gd`, no chromatic literal below the PALETTE block at all. `--palette`
     substitutes the sixteen constants and nothing else, so a colour in a function body is
     unreachable by every documented way of re-skinning the kit.

Achromatic literals (r == g == b, so black, white and greys) are exempt everywhere. That is
not an escape hatch for the awkward cases — it is the one shape that is provably not a palette
choice. Drop shadows, the white screen flash, the transparent `Color(0, 0, 0, 0)` that means
"no fill", and the black-or-white ink picked by luminance against a game-supplied item colour
are all achromatic, and all of them stay correct under any palette. A colour with a hue does
not.

Anything else that genuinely has to be a literal takes `# palette-lint: ignore` on its line,
which is deliberately noisy to write.

The second arm answers a different question about the same block: is the text on it readable?
A palette that survives all three rules above can still pair near-black ink with a near-black
button, and until this existed nothing in the kit measured contrast at all — which made
`--palette`, and "copy the closest palette and change ACCENT", an invitation to ship an
unreadable UI with every check passing.

Two things make that measurement subtler than feeding two constants to a contrast formula:

  * **Colour space.** Godot `Color` components are sRGB-encoded, and `Color.get_luminance()`
    weights them with no transfer curve. Its output is not WCAG relative luminance and the two
    disagree badly in the mid-tones — 2.65 against 4.14 on `bloodmoon`'s primary button. Every
    ratio here goes through the WCAG piecewise transform instead.
  * **Compositing.** Every surface in this kit is translucent on purpose, so the ratio between
    an ink constant and a fill constant describes a colour that is never on screen. Each pair
    below is composited down its real layer stack. Where gameplay can still show through the
    bottom of that stack, the pair is evaluated over BOTH black and white and judged on the
    worse of the two, so the result is a bound rather than an assumption about the game.

That second point is what keeps this arm quiet. Measuring raw `bg_color` puts the secondary
button at 4.00:1 in `amber`; composited, the button a player actually sees is 11.36:1. A check
on the raw figure would have condemned five of the six shipped palettes on its first run, and
a check that fires on correct code is switched off within a week.

Two bars, because the kit's own type ramp has two intentions. TEXT, the button inks and
CHIP_INK carry information and are held to WCAG AA 4.5. TEXT_DIM and TEXT_FAINT are the tiers
the design deliberately whispers with — a card kicker, a controls hint, a stat caption — and
are held to 3.0. That is not a discount for failing the real bar; it is the reason those tiers
must never be the only place a fact appears.

Not measured, deliberately: the crosshair ring, and any Glyph drawn straight onto gameplay
with no fill behind it. There is no surface to composite against, so no ratio exists; the
kit's answer there is the outline-plus-shadow in `style_label` and the ring's own geometry.

Run it over the kit's own templates, or over the `scripts/ui/` directory of a project that
scaffolded them — the rules are the same in both, and in a project it catches the screen you
added last week rather than the ones that shipped.

Usage:
    python palette_lint.py                       # the kit's own templates
    python palette_lint.py path/to/project/scripts/ui
    python palette_lint.py --contrast-table      # every pair's ratio, pass or fail
    python palette_lint.py --json

Exits 1 if anything is unreachable by a re-skin or lands under its contrast bar, 0 if the
palette really is the whole story and all of it is readable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "assets" / "templates"
THEME_FILE = "ui_theme.gd"

# Same reasoning as seed.py: a lint is read through a pipe, a CI log or an agent capturing
# stdout at least as often as it is read on a console, and on Windows Python would otherwise
# encode to the active codepage and land the em dashes in these messages as a stray byte.
# errors="replace" so a console that cannot render one degrades it rather than raising
# mid-report and losing the findings.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# `const NAME: Color = Color(...)`. Only literal constants define the palette; a derived one
# like `const BACKDROP_OPAQUE: Color = Color(BACKDROP, 1.0)` is already re-skinnable and is
# skipped by the numeric-arguments requirement below.
_CONST_RE = re.compile(r"^const[ \t]+([A-Z_][A-Z_0-9]*)[ \t]*:[ \t]*Color[ \t]*=[ \t]*Color\(([^)]*)\)")

# Any `Color(` call whose arguments are all numeric literals. `Color(accent.r, accent.g, ...)`
# and `Color(BACKDROP, 1.0)` are derived and do not match, which is the point: they move with
# the palette already.
_LITERAL_RE = re.compile(r"\bColor\(\s*([0-9.]+(?:\s*,\s*[0-9.]+){2,3})\s*\)")

_IGNORE = "# palette-lint: ignore"

# Colours are authored to two decimals, so anything closer than half a step is the same
# colour written twice rather than a deliberate near-miss.
EPS = 0.005


def parse_args_floats(arg_text: str) -> tuple[float, ...]:
    return tuple(float(p.strip()) for p in arg_text.split(","))


def is_achromatic(rgb: tuple[float, float, float]) -> bool:
    """r == g == b. Black, white and every grey between them."""
    r, g, b = rgb
    return abs(r - g) < EPS and abs(g - b) < EPS


def strip_comment(line: str) -> str:
    """Drop a trailing `#` comment so a `Color(...)` quoted in prose is not linted.

    GDScript strings can contain `#`, so walk the line tracking quote state rather than
    splitting on the first one. Without this, the comment above CHIP_INK explaining the
    contrast pair would be read as code.
    """
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote and (i == 0 or line[i - 1] != "\\"):
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return line[:i]
    return line


def read_palette(path: Path) -> tuple[dict[str, tuple[float, ...]], int]:
    """Return {CONST: rgba} and the line number the last palette constant sits on.

    The line number is the boundary between "this is the palette" and "this is below the
    palette", which is what rules B and C are about. Taking it from the last constant rather
    than from a header comment means renaming the section heading cannot silently disable
    half the lint.
    """
    palette: dict[str, tuple[float, ...]] = {}
    last_line = 0
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = _CONST_RE.match(line)
        if not m:
            continue
        try:
            vals = parse_args_floats(m.group(2))
        except ValueError:
            continue  # derived from another constant, e.g. Color(BACKDROP, 1.0)
        if len(vals) in (3, 4):
            # Normalised to RGBA here rather than at every use: the contrast arm composites
            # these and an implicit alpha would silently become 0.0, i.e. an invisible panel
            # that scores a perfect ratio against whatever is behind it.
            palette[m.group(1)] = vals if len(vals) == 4 else vals + (1.0,)
            last_line = n
    return palette, last_line


def scan(directory: Path) -> tuple[list[dict], dict[str, tuple[float, ...]], int]:
    theme = directory / THEME_FILE
    if not theme.is_file():
        sys.exit(
            f"error: no {THEME_FILE} in {directory}\n"
            f"       point this at the kit's assets/templates or at a project's scripts/ui"
        )
    palette, palette_end = read_palette(theme)
    if not palette:
        sys.exit(f"error: no `const NAME: Color = Color(...)` constants found in {theme}")

    findings: list[dict] = []
    for path in sorted(directory.glob("*.gd")):
        in_theme = path.name == THEME_FILE
        for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _IGNORE in raw:
                continue
            code = strip_comment(raw)
            for m in _LITERAL_RE.finditer(code):
                try:
                    vals = parse_args_floats(m.group(1))
                except ValueError:
                    continue
                rgb = vals[:3]
                if in_theme and n <= palette_end:
                    continue  # this literal IS the palette
                if is_achromatic(rgb):
                    continue

                # Every match, not the first: two palette constants can legitimately share an
                # RGB and differ only in alpha (amber's PANEL_FILL_DEEP and BACKDROP do), and
                # naming just one of them sends the reader to the wrong constant.
                dups = [name for name, pv in palette.items()
                        if all(abs(a - b) < EPS for a, b in zip(rgb, pv[:3]))]
                dup = " or ".join(dups) if dups else None
                if dup:
                    rule, why = "B", (
                        f"repeats {dup} exactly — renders identically today and keeps the old "
                        f"hue after a re-skin"
                    )
                elif in_theme:
                    rule, why = "C", (
                        "art direction below the PALETTE block — `--palette` substitutes the "
                        "constants and nothing else, so no documented re-skin reaches this"
                    )
                else:
                    rule, why = "A", (
                        "a colour outside ui_theme.gd — the palette is supposed to be the "
                        "whole art direction"
                    )
                findings.append({
                    "file": path.name,
                    "line": n,
                    "rule": rule,
                    "color": m.group(0),
                    "duplicates": dup,
                    "why": why,
                    "source": raw.strip(),
                })
    return findings, palette, palette_end


# ---------------------------------------------------------------------------- contrast arm

# WCAG 2.x bars. AA for anything carrying information; the lower one for the two tiers the
# type ramp deliberately de-emphasises, which is also WCAG's own bar for large and non-text.
AA = 4.5
AA_DIM = 3.0

Rgba = tuple[float, ...]

BLACK: Rgba = (0.0, 0.0, 0.0, 1.0)
WHITE: Rgba = (1.0, 1.0, 1.0, 1.0)


def lightened(c: Rgba, amount: float) -> Rgba:
    """Godot's Color.lightened: move each channel toward 1.0. Alpha is untouched."""
    return tuple(ch + (1.0 - ch) * amount for ch in c[:3]) + (c[3],)


def darkened(c: Rgba, amount: float) -> Rgba:
    """Godot's Color.darkened: scale each channel toward 0.0. Alpha is untouched."""
    return tuple(ch * (1.0 - amount) for ch in c[:3]) + (c[3],)


def with_alpha(c: Rgba, a: float) -> Rgba:
    return c[:3] + (a,)


def linearise(channel: float) -> float:
    """sRGB -> linear, the WCAG 2.x piecewise transform."""
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(c: Rgba) -> float:
    return (0.2126 * linearise(c[0]) + 0.7152 * linearise(c[1]) + 0.0722 * linearise(c[2]))


def contrast_ratio(a: Rgba, b: Rgba) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def composite(top: Rgba, under: Rgba) -> Rgba:
    """`top` over an opaque `under`. Straight-alpha source-over, in sRGB space.

    sRGB and not linear because that is what Godot's 2D pipeline does with hdr_2d off, which
    is the default. Blending in the wrong space shifts a half-transparent panel by several
    percent of luminance, which is enough to move a borderline pair across the bar.
    """
    a = top[3]
    return tuple(top[i] * a + under[i] * (1.0 - a) for i in range(3)) + (1.0,)


def stack(layers: list[Rgba], base: Rgba) -> Rgba:
    """Paint `layers` bottom-to-top onto an opaque `base`."""
    out = base
    for layer in layers:
        out = composite(layer, out)
    return out


def leakage(layers: list[Rgba]) -> float:
    """Fraction of the final pixel still contributed by whatever is under the stack."""
    out = 1.0
    for layer in layers:
        out *= 1.0 - layer[3]
    return out


def min_contrast(ink: Rgba, fills: list[Rgba]) -> float:
    return min(contrast_ratio(ink, f) for f in fills)


def primary_ink(accent: Rgba) -> Rgba:
    """Mirror of `UiTheme.style_button`'s measured ink pick.

    Kept in step with the template by `smoke_test.gd`, which asserts the same bars against the
    StyleBoxes and font_color overrides Godot actually built — so if someone edits the
    derivation, the engine-side check is the one that stays honest and this one goes stale
    loudly rather than quietly.
    """
    fills = [accent, lightened(accent, 0.14), darkened(accent, 0.14)]
    tinted = max([darkened(accent, 0.86), lightened(accent, 0.9)],
                 key=lambda ink: min_contrast(ink, fills))
    if min_contrast(tinted, fills) >= AA:
        return tinted
    return max([BLACK, WHITE], key=lambda ink: min_contrast(ink, fills))


def surfaces(p: dict[str, Rgba]) -> list[tuple[str, Rgba, list[Rgba], float, str]]:
    """Every ink/surface pair the kit renders text on, with the stack under it.

    Layers run bottom-to-top and stop above whatever the pair cannot see past. A shell screen
    ends at BACKDROP_OPAQUE and is exact; a HUD pill ends at the game and is bounded. The
    pause menu keeps translucent BACKDROP, so modelling it that way covers both shell cases at
    once — the extra 0.084% of gameplay it lets through moves the ratio by less than one part
    in a thousand, below what an 8-bit channel can even represent.
    """
    text, dim, faint = p["TEXT"], p["TEXT_DIM"], p["TEXT_FAINT"]
    pill, panel, backdrop = p["PANEL_FILL"], p["PANEL_FILL_DEEP"], p["BACKDROP"]
    accent = p["ACCENT"]

    # style_button's secondary path, verbatim.
    sec = with_alpha(lightened(panel, 0.15), 0.95)
    sec_hover = with_alpha(lightened(sec, 0.14), 1.0)
    sec_press = with_alpha(darkened(sec, 0.14), 1.0)
    pri_ink = primary_ink(accent)

    shell = [backdrop, panel]
    return [
        ("TEXT on a panel", text, shell, AA, "pause/results body copy"),
        ("TEXT_DIM on a panel", dim, shell, AA_DIM, "pause subtitle"),
        ("TEXT_FAINT on a panel", faint, shell, AA_DIM, "title controls hint"),
        ("TEXT_FAINT on a results chip", faint, [backdrop, panel, panel], AA_DIM,
         "stat captions, panel on panel"),
        ("TEXT on the backdrop", text, [backdrop], AA, "title/results text off-panel"),
        ("secondary button", text, shell + [sec], AA, "resume, quit, play again"),
        ("secondary button hover", text, shell + [sec_hover], AA, "the state under the pointer"),
        ("secondary button pressed", text, shell + [sec_press], AA, ""),
        ("primary button", pri_ink, [accent], AA, "the accent-filled call to action"),
        ("primary button hover", pri_ink, [lightened(accent, 0.14)], AA,
         "usually the worst of the three"),
        ("primary button pressed", pri_ink, [darkened(accent, 0.14)], AA, ""),
        ("TEXT on a HUD pill", text, [pill], AA, "stats and counters, over live gameplay"),
        ("TEXT_DIM on a HUD pill", dim, [pill], AA_DIM, "prompt prefix, hint line"),
        ("TEXT on a reward card", text, [panel], AA, "card title"),
        ("TEXT_FAINT on a reward card", faint, [panel], AA_DIM, "card kicker at FS_TINY"),
        ("CHIP_INK on the keycap", p["CHIP_INK"], [pill, p["CHIP_FILL"]], AA,
         "the [E] in a prompt"),
    ]


def contrast_rows(palette: dict[str, Rgba]) -> list[dict]:
    """Measure every pair, bounded over black-to-white gameplay where the stack lets it through."""
    needed = {"TEXT", "TEXT_DIM", "TEXT_FAINT", "PANEL_FILL", "PANEL_FILL_DEEP",
              "BACKDROP", "ACCENT", "CHIP_INK", "CHIP_FILL"}
    missing = needed - set(palette)
    if missing:
        # A palette this arm cannot read is reported, not silently skipped: "CONTRAST: OK"
        # over a file that has been renamed out from under it is the check lying.
        return [{"pair": f"(cannot measure: {THEME_FILE} has no {', '.join(sorted(missing))})",
                 "lo": 0.0, "hi": 0.0, "bar": AA, "bounded": False, "note": "", "pass": False}]

    rows: list[dict] = []
    for name, ink, layers, bar, note in surfaces(palette):
        over_black = contrast_ratio(ink, stack(layers, BLACK))
        over_white = contrast_ratio(ink, stack(layers, WHITE))
        lo, hi = min(over_black, over_white), max(over_black, over_white)
        rows.append({
            "pair": name, "lo": lo, "hi": hi, "bar": bar,
            "bounded": leakage(layers) > 1.0 / 255.0,
            "note": note, "pass": lo >= bar,
        })
    return rows


def format_row(r: dict) -> str:
    span = f"{r['lo']:5.2f}" if not r["bounded"] else f"{r['lo']:5.2f}-{r['hi']:.2f}"
    mark = "ok  " if r["pass"] else "FAIL"
    return f"  {mark} {r['pair']:<30} {span:>12}  (bar {r['bar']:.1f})"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("directory", type=Path, nargs="?", default=DEFAULT_DIR,
                    help=f"directory holding {THEME_FILE} and its screens "
                         f"(default: the kit's own templates)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--contrast-table", action="store_true",
                    help="print every measured pair, passing ones included — the numbers to "
                         "quote when writing a new palette")
    args = ap.parse_args()

    directory = args.directory.resolve()
    findings, palette, palette_end = scan(directory)
    scanned = sorted(p.name for p in directory.glob("*.gd"))
    rows = contrast_rows(palette)
    under_bar = [r for r in rows if not r["pass"]]

    if args.json:
        print(json.dumps({
            "directory": str(directory),
            "files": scanned,
            "palette": {k: list(v) for k, v in palette.items()},
            "findings": findings,
            "contrast": rows,
        }, indent=2))
        return 1 if findings or under_bar else 0

    # Always name the denominator. "PALETTE: OK" over a directory this found no screens in is
    # the report lying about what it looked at.
    print(f"{directory}")
    print(f"  {len(palette)} palette constants in {THEME_FILE} (through line {palette_end})")
    print(f"  {len(scanned)} file(s) scanned: {', '.join(scanned)}")
    print()

    if findings:
        for f in findings:
            print(f"{f['file']}:{f['line']}: [{f['rule']}] {f['color']} {f['why']}")
            print(f"    {f['source']}")
        print()
        print(f"PALETTE: {len(findings)} colour(s) a re-skin cannot reach.")
        print("Route each through a palette constant, or mark it `# palette-lint: ignore` with "
              "a reason if it genuinely is not a palette choice.")
    else:
        print(f"PALETTE: OK — no colour outside the palette in {len(scanned)} file(s).")

    print()
    if args.contrast_table or under_bar:
        print(f"  WCAG 2.x contrast, composited. A range means gameplay shows through the")
        print(f"  bottom of the stack and the pair is judged on the worse end.")
        for r in (rows if args.contrast_table else under_bar):
            print(format_row(r) + (f"  {r['note']}" if r["note"] and args.contrast_table else ""))
        print()

    if under_bar:
        print(f"CONTRAST: {len(under_bar)} pair(s) under the bar.")
        print("Text at these ratios is legible on your monitor and gone on a laptop in "
              "daylight. Move the surface, not the ink: the ink tiers are shared by every "
              "screen, the fills are not.")
        return 1

    print(f"CONTRAST: OK — {len(rows)} ink/surface pair(s) at or above WCAG AA "
          f"({AA:.1f}, {AA_DIM:.1f} for the TEXT_DIM/TEXT_FAINT tiers).")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
