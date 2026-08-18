#!/usr/bin/env python3
"""Find Markdown in this repo that renders as something other than what was written.

`SKILL.md` *is* the product here, so a rendering bug is a defect in the deliverable and not a
cosmetic nit. The bug that prompted this: a `**bold**` paragraph placed directly under a list
item with no blank line between them is swallowed by that bullet as a CommonMark **lazy
continuation** — it renders *inside* the bullet. Nothing errors, the raw file looks right in
an editor, and it was caught only because somebody read the diff. Three releases later it
would still have been there.

Three rules, in increasing order of how loudly the defect announces itself:

  L. A block-shaped line glued to a list item's paragraph. See "the quiet direction" below —
     this is the rule that has to earn its keep by *not* firing.
  F. A fenced code block that is opened and never closed. Everything to the end of the file
     renders as code: the rest of the skill silently disappears from the page.
  H. An ATX heading with a paragraph line directly above it. It still renders as a heading in
     CommonMark, but not in every renderer that reads these files, and it is the shape a
     heading takes when a blank line was lost in an edit. "Paragraph line" is the operative
     word: an HTML block above a heading is exempt by rule, because an HTML block is not a
     paragraph and cannot absorb anything. That is not a courtesy — `<!-- BEGIN BEADS
     INTEGRATION -->` sits immediately above `## Beads Issue Tracker` in both `CLAUDE.md` and
     `AGENTS.md`, is written by `bd setup` rather than by anyone here, and renders exactly as
     intended in every renderer. A rule that reported it would be reporting correct,
     tool-generated, unownable text on three lines of the two files a reader opens first.

## The quiet direction, which is most of the design

Rule L is the one that can make the whole tool worthless. A lazy continuation is *any*
unindented line following a list item, and the overwhelmingly common one is legitimate: a
bullet whose own prose wrapped onto the next line. A lint that fires on those gets switched
off within a week, and then rule F never runs either.

The signal that separates the defect from the wrap is not indentation — the bug and a wrap
sit at the same column — it is **what the line would have been had it been a block of its
own**. So rule L fires only on a line that is *block-shaped*: it opens with a strong-emphasis
run (`**like this**`), a table row (`|`), or a link reference definition (`[ref]: url`). Every
one of those is a construct that a reader sees as a new block and that CommonMark cannot start
in the middle of a paragraph, so gluing it to a bullet always renders wrong. Wrapped prose is
not block-shaped, which is why it is exempt by rule rather than by an allowlist.

The same reasoning is why an HTML comment glued to a bullet is silent, and it is not a special
case: `<!--` opens an HTML block, which *can* interrupt a paragraph, so it renders as its own
block and there is nothing wrong with it. `CLAUDE.md` and `AGENTS.md` both end their beads
section that way. Blockquotes, thematic breaks, headings, fences and sibling list markers are
silent for exactly the same reason.

The cost of that narrowness, stated plainly: a *plain prose* paragraph glued to a bullet is
not reported, because it is character-for-character indistinguishable from the bullet's own
wrapped text. If that ever needs catching it wants a different mechanism (a hard wrap column),
not a looser version of this rule.

## There is no ignore pragma, deliberately

Every finding here names a construct that has no legitimate form: the blank line is missing,
or the fence is unterminated. The edit that silences the finding is the same edit that fixes
the rendering, so an escape hatch would only ever be used to keep a rendering bug. (A pragma
would also be self-defeating for rule L — an HTML comment above the offending line already
ends the paragraph, so writing the pragma *is* the fix.)

Usage:
    python tools/lint_markdown.py                  # every skills/*/SKILL.md + the repo-root *.md
    python tools/lint_markdown.py path/to/file.md
    python tools/lint_markdown.py path/to/dir      # every *.md under it, recursively
    python tools/lint_markdown.py --json

Exits 1 if any file renders as something other than what it says, 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Same reasoning as palette_lint.py: this is read through a pipe, a CI log or an agent
# capturing stdout at least as often as on a console, and the source files it quotes are full
# of em dashes and box-drawing characters that would otherwise hit the Windows codepage.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# A list item marker plus at least one space. `1.` and `1)` count; `-` on its own line does
# not open a paragraph, so the trailing `\S` requirement is load-bearing.
_ITEM_RE = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])([ \t]+)(?=\S)")

# Backtick fences may not carry a backtick in the info string; tilde fences may carry anything.
_FENCE_RE = re.compile(r"^([ \t]*)(`{3,}|~{3,})[ \t]*([^`]*?)[ \t]*$")

_ATX_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")

# `---`, `***`, `___` with optional internal spaces. Ends a paragraph, so it is not a defect.
_THEMATIC_RE = re.compile(r"^ {0,3}([-*_])[ \t]*(?:\1[ \t]*){2,}$")

# HTML blocks of CommonMark types 1-6 open on a tag or a comment and *can* interrupt a
# paragraph. Anything matching this is rendering as its own block already.
_HTML_RE = re.compile(r"^[ \t]{0,3}<(?:!--|[!/?]|[a-zA-Z])")

# The three block-shaped starts of rule L. Each is a construct a reader reads as a new block
# and that CommonMark will not begin inside a paragraph.
_BLOCK_SHAPED = (
    # A strong-emphasis run that both opens the line and closes on it. The closing requirement
    # is what keeps `**bold span**` in the middle of wrapped prose out of this: that line does
    # not *start* with the run, and a line that opens with `**` and never closes it is not
    # emphasis at all.
    ("a bold-led paragraph", re.compile(r"^(\*\*|__)(?=\S).*?\1")),
    ("a table row", re.compile(r"^\|")),
    ("a link reference definition", re.compile(r"^\[[^\]\n]+\]:[ \t]")),
)

_WHY = {
    "L": ("swallowed by the list item above it — with no blank line between them CommonMark "
          "reads this as a lazy continuation and renders it inside the bullet"),
    "F": ("opened here and never closed — every line to the end of the file renders as code"),
    "H": ("a heading with a non-blank line directly above it; insert a blank line"),
}


def _width(text: str) -> int:
    """Column width of `text` starting from column 0, tabs expanded to a 4-column stop."""
    width = 0
    for ch in text:
        width += 4 - (width % 4) if ch == "\t" else 1
    return width


def _indent_of(line: str) -> int:
    """Leading whitespace width with tabs expanded to the next multiple of 4."""
    for i, ch in enumerate(line):
        if ch not in " \t":
            return _width(line[:i])
    return _width(line)


def _block_shape(text: str) -> str | None:
    for label, rx in _BLOCK_SHAPED:
        if rx.match(text):
            return label
    return None


def lint_text(lines: list[str]) -> list[dict]:
    """Return findings for one file's lines, as {line, rule, why, source}."""
    findings: list[dict] = []

    fence: tuple[str, int, int, int, str] | None = None  # char, len, indent, line no, raw
    in_frontmatter = False
    frontmatter_closed_on = 0

    # Two pieces of list state, and they are not the same thing.
    #   list_col  — content column of the innermost list item still open. Survives blank lines,
    #               because a fenced block or a second paragraph inside an item does too. It is
    #               what decides how far a fence may legally be indented.
    #   para_col  — set only while we are inside that item's *paragraph*. A blank line ends the
    #               paragraph, and with it every chance of a lazy continuation: an unindented
    #               paragraph after a blank line correctly closes the list and renders fine.
    list_col: int | None = None
    para_col: int | None = None

    for n, raw in enumerate(lines, 1):
        stripped = raw.strip()

        # --- YAML frontmatter -----------------------------------------------------------
        if n == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
                frontmatter_closed_on = n
            continue

        # --- fenced code ----------------------------------------------------------------
        if fence is not None:
            ch, length, f_indent, _, _ = fence
            m = _FENCE_RE.match(raw)
            if (m and m.group(2)[0] == ch and len(m.group(2)) >= length
                    and not m.group(3) and _indent_of(raw) <= f_indent + 3):
                fence = None
            continue  # every rule is blind inside a fence, `#` comments included

        m = _FENCE_RE.match(raw)
        if m:
            indent = _indent_of(raw)
            # CommonMark allows a fence 0-3 columns past the start of its container. Outside a
            # list that is column 3; inside one it is the item's content column plus 3. Beyond
            # that the line is indented code, not a fence, and misreading it would make the
            # whole rest of the file invisible to rules L and H.
            limit = 3 if list_col is None else list_col + 3
            if indent <= limit:
                fence = (m.group(2)[0], len(m.group(2)), indent, n, raw)
                para_col = None
                continue

        # --- blank line -----------------------------------------------------------------
        if not stripped:
            para_col = None
            continue

        indent = _indent_of(raw)

        # --- ATX heading ----------------------------------------------------------------
        if _ATX_RE.match(raw):
            prev = lines[n - 2] if n >= 2 else ""
            # Two exemptions, both because the line above is not a paragraph and so cannot
            # swallow or crowd the heading:
            #   - the frontmatter terminator; `---` then `# Title` renders exactly as intended,
            #     because the frontmatter never reaches the renderer at all
            #   - an HTML block line, which is how every generated BEGIN/END marker in this
            #     repo is written
            if (n > 1 and prev.strip() and n - 1 != frontmatter_closed_on
                    and not _HTML_RE.match(prev)):
                findings.append({"line": n, "rule": "H", "why": _WHY["H"], "source": stripped})
            list_col = None
            para_col = None
            continue

        # --- list item ------------------------------------------------------------------
        im = _ITEM_RE.match(raw)
        if im:
            # The content column is the width of the whole marker prefix, not its indentation:
            # `- ` puts content at column 2 even though the line is indented 0. Getting this
            # wrong makes every continuation look correctly indented and rule L never fires.
            col = _width(im.group(0))
            list_col = col
            para_col = col
            continue

        # --- a plain content line -------------------------------------------------------
        if para_col is not None and indent < para_col:
            # This line is a lazy continuation. Whether that is a defect depends entirely on
            # what shape it is; see the module docstring.
            if _THEMATIC_RE.match(raw) or _HTML_RE.match(raw):
                para_col = None            # both end the paragraph; both render correctly
            elif stripped.startswith(">"):
                para_col = None            # a block quote can interrupt a paragraph too
            else:
                shape = _block_shape(stripped)
                if shape:
                    findings.append({
                        "line": n, "rule": "L",
                        "why": f"{shape} {_WHY['L']}",
                        "source": stripped,
                    })
                # Either way the paragraph continues, so stay in the same state: a second
                # glued line is a second finding, not a cascade of a different kind.
        elif para_col is None and indent == 0 and not _HTML_RE.match(raw):
            list_col = None

    if fence is not None:
        _, _, _, n, raw = fence
        findings.append({"line": n, "rule": "F", "why": _WHY["F"], "source": raw.strip()})

    return findings


def lint_file(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for f in lint_text(lines):
        f = dict(f)
        f["file"] = str(path)
        out.append(f)
    return out


def collect(target: Path | None) -> list[Path]:
    if target is None:
        files = sorted(REPO_ROOT.glob("skills/*/SKILL.md")) + sorted(REPO_ROOT.glob("*.md"))
        return files
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(target.rglob("*.md"))
    sys.exit(f"error: no such file or directory: {target}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("target", type=Path, nargs="?", default=None,
                    help="a .md file, or a directory to scan recursively "
                         "(default: every skills/*/SKILL.md plus the repo-root *.md)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    files = collect(args.target.resolve() if args.target else None)
    findings: list[dict] = []
    for path in files:
        findings.extend(lint_file(path))

    if args.json:
        print(json.dumps({
            "files": [str(p) for p in files],
            "findings": findings,
        }, indent=2))
        return 1 if findings else 0

    # Always name the denominator. "MARKDOWN: OK" over zero files is the report lying about
    # what it looked at, and the default glob is exactly the thing that can silently go empty.
    print(f"{len(files)} file(s) scanned:")
    for p in files:
        try:
            shown = p.relative_to(REPO_ROOT)
        except ValueError:
            shown = p
        print(f"  {shown}")
    print()

    if not findings:
        print(f"MARKDOWN: OK — {len(files)} file(s) render as written.")
        return 0

    for f in findings:
        print(f"{f['file']}:{f['line']}: [{f['rule']}] {f['why']}")
        print(f"    {f['source']}")
    print()
    print(f"MARKDOWN: {len(findings)} place(s) that render as something else.")
    print("Insert the missing blank line, or close the fence — the fix and the silencer are "
          "the same edit, which is why there is no ignore pragma.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
