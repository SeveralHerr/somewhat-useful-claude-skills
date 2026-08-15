#!/usr/bin/env python3
"""Find colours that a re-skin cannot reach.

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

Run it over the kit's own templates, or over the `scripts/ui/` directory of a project that
scaffolded them — the rules are the same in both, and in a project it catches the screen you
added last week rather than the ones that shipped.

Usage:
    python palette_lint.py                       # the kit's own templates
    python palette_lint.py path/to/project/scripts/ui
    python palette_lint.py --json

Exits 1 if anything is unreachable by a re-skin, 0 if the palette really is the whole story.
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
            palette[m.group(1)] = vals
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


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("directory", type=Path, nargs="?", default=DEFAULT_DIR,
                    help=f"directory holding {THEME_FILE} and its screens "
                         f"(default: the kit's own templates)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    directory = args.directory.resolve()
    findings, palette, palette_end = scan(directory)
    scanned = sorted(p.name for p in directory.glob("*.gd"))

    if args.json:
        print(json.dumps({
            "directory": str(directory),
            "files": scanned,
            "palette": {k: list(v) for k, v in palette.items()},
            "findings": findings,
        }, indent=2))
        return 1 if findings else 0

    # Always name the denominator. "PALETTE: OK" over a directory this found no screens in is
    # the report lying about what it looked at.
    print(f"{directory}")
    print(f"  {len(palette)} palette constants in {THEME_FILE} (through line {palette_end})")
    print(f"  {len(scanned)} file(s) scanned: {', '.join(scanned)}")
    print()

    if not findings:
        print(f"PALETTE: OK — no colour outside the palette in {len(scanned)} file(s).")
        return 0

    for f in findings:
        print(f"{f['file']}:{f['line']}: [{f['rule']}] {f['color']} {f['why']}")
        print(f"    {f['source']}")
    print()
    print(f"PALETTE: {len(findings)} colour(s) a re-skin cannot reach.")
    print("Route each through a palette constant, or mark it `# palette-lint: ignore` with a "
          "reason if it genuinely is not a palette choice.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
