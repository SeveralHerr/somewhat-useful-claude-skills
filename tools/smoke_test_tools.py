#!/usr/bin/env python3
"""Prove lint_markdown.py and release_check.py can both FIRE and STAY QUIET.

Half of this file is the half that matters. Any lint can be made to report something; the
question CLAUDE.md asks of a new check is whether its exemptions have been shown to stay
silent, because a check that also fires on legitimate input gets switched off within a week
and takes its real findings with it. So every rule below appears twice: once against a fixture
carrying exactly the defect it describes, and once against the nearest *legitimate* construct
that a naive implementation would false-fire on.

The lazy-continuation fixtures reproduce the original bug shape — a `**bold**` paragraph
directly under a bullet, no blank line — and pair it with the three things that look identical
to a bad rule: the bullet's own wrapped prose, an indented continuation paragraph, and the
`<!-- END BEADS INTEGRATION -->` comment that really does sit under a bullet in CLAUDE.md.

Both tools are also run against the repo as it stands, which must be all-pass.

    python tools/smoke_test_tools.py

Prints SMOKE: ALL PASS and exits 0, or the first failing case and exits 1.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LINT = HERE / "lint_markdown.py"
RELEASE = HERE / "release_check.py"

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

FAILS = []

# Everything outside tools/ that this run is allowed to touch: nothing. Hashed before the
# first case and compared after the last one.
WATCHED = [
    REPO / ".claude-plugin" / "plugin.json",
    REPO / ".claude-plugin" / "marketplace.json",
    REPO / "README.md",
    REPO / "CLAUDE.md",
]


def check(name, cond, out=""):
    print(("  PASS  " if cond else "  FAIL  ") + name)
    if not cond:
        FAILS.append((name, out))


def write(path: Path, text: str) -> Path:
    """LF only. Path.write_text emits CRLF on Windows, git normalises it on checkin, and the
    fixture then disagrees with what a reader sees in the diff — see CLAUDE.md."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def run(script, *args):
    p = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


# =====================================================================================
# lint_markdown.py
# =====================================================================================
# (name, expect_rule or None for "must be silent", markdown)
MD_CASES = [
    # --- L: lazy continuation ---------------------------------------------------------
    ("L fires: a **bold** paragraph glued to a bullet (the original bug)", "L", """\
# Title

- Wrap the node with a shell and add the shell to the container.
**Punches return to the RESTING scale, not to `1.0`.** Anything on a scaled layer is not
at 1.0.
"""),
    ("L fires: a bold paragraph glued to an indented continuation of the bullet", "L", """\
# Title

- The first line of the item,
  wrapped properly onto a second line.
**And then a bold paragraph with no blank line above it.**
"""),
    # Two findings, not one: a GFM table is a header row plus a delimiter row, and both are
    # swallowed. Reporting each swallowed line is what makes the extent of the damage visible.
    ("L fires: a table glued to a bullet (both rows)", "LL", """\
# Title

- Read the report:
| Line | What to do with it |
| --- | --- |
"""),
    ("L fires: a link reference definition glued to a bullet", "L", """\
# Title

- See the docs.
[docs]: https://example.invalid/docs
"""),
    ("L fires twice when two bold paragraphs are glued on", "LL", """\
# Title

- A bullet.
**First glued paragraph.**
**Second glued paragraph.**
"""),
    ("L quiet: the bullet's own wrapped prose at column 0", None, """\
# Title

- A bullet whose text is long enough that the author let it run
onto the next line without indenting it. This renders as one paragraph
inside the bullet, which is exactly what was meant.
"""),
    ("L quiet: a properly indented continuation paragraph", None, """\
# Title

- A bullet.

  A second paragraph belonging to that same bullet, indented to its content column.
"""),
    ("L quiet: a bold paragraph separated by a blank line", None, """\
# Title

- A bullet.

**A bold paragraph, which the blank line makes its own block.**
"""),
    ("L quiet: an HTML comment under a bullet (the CLAUDE.md beads marker)", None, """\
# Title

- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->
"""),
    ("L quiet: a sibling bullet directly under a bullet", None, """\
# Title

- First item.
- Second item.
- Third item.
"""),
    ("L quiet: a nested bullet directly under its parent", None, """\
# Title

- Parent item.
  - Child item.
  - Another child.
"""),
    ("L quiet: a fenced code block inside a list item", None, """\
# Title

- Run the probe:

  ```bash
  python scripts/kenney_probe.py "<kit>"
  ```

  Then read the report.
"""),
    ("L quiet: a heading directly under a bullet (headings interrupt paragraphs)", None, """\
# Title

- A bullet.

## Next section
"""),
    ("L quiet: a block quote directly under a bullet", None, """\
# Title

- A bullet.
> quoted text
"""),
    ("L quiet: a bold *span* mid-sentence in wrapped bullet prose", None, """\
# Title

- A bullet that mentions something and then wraps before the emphasis,
so the **bold span** lands mid-line rather than opening the line.
"""),
    ("L quiet: a table indented under a bullet", None, """\
# Title

- A bullet with a table of its own:

  | Line | Meaning |
  | --- | --- |
  | PIVOT | decides your placement formula |
"""),
    ("L quiet: a bold paragraph after a plain paragraph (no list involved)", None, """\
# Title

Some ordinary prose that ends here.
**A bold paragraph glued to it.** This is not a list, so nothing is swallowed.
"""),

    # --- F: unclosed fence ------------------------------------------------------------
    ("F fires: a fence opened and never closed", "F", """\
# Title

```bash
python tools/lint_markdown.py
"""),
    ("F fires: a tilde fence opened and never closed", "F", """\
# Title

~~~
some text
"""),
    ("F fires: a fence closed only by a *different* marker", "F", """\
# Title

```
some text
~~~
"""),
    ("F quiet: a closed fence with an info string", None, """\
# Title

```gdscript
func _ready() -> void:
	pass
```
"""),
    ("F quiet: a fence containing the other marker character", None, """\
# Title

```
~~~ this is content, not a fence
```
"""),
    ("F quiet: a fence containing a longer run of its own marker", None, """\
# Title

````
``` this is an inner fence shown as an example
````
"""),
    ("F quiet: a fence indented inside a list item", None, """\
# Title

- Item:

  ```bash
  echo hi
  ```
"""),
    ("F quiet: a fence indented three spaces at top level", None, """\
# Title

   ```
   text
   ```
"""),

    # --- H: heading with no preceding blank line ---------------------------------------
    ("H fires: a heading glued to a paragraph", "H", """\
# Title

Some prose that ends here.
## A section
"""),
    ("H fires: a heading glued to a bullet", "H", """\
# Title

- A bullet.
## A section
"""),
    ("H quiet: the first line of the file is a heading", None, """\
# Title

Prose.
"""),
    ("H quiet: a heading directly after the frontmatter terminator", None, """\
---
name: probe
description: a probe
---
# Probe
"""),
    ("H quiet: a `#` comment inside a fenced code block", None, """\
# Title

```bash
# rebuild the class cache
godot --headless --import
```
"""),
    ("H quiet: a `#` comment on the first line inside a fence", None, """\
# Title

```python
#!/usr/bin/env python3
print("hi")
```
"""),
    ("H quiet: `---` frontmatter delimiters are not headings or fences", None, """\
---
name: probe
description: a probe

---

# Probe

Prose.
"""),
    ("H quiet: a `#` inside frontmatter", None, """\
---
name: probe
description: mentions a #hashtag
---

# Probe
"""),
    ("H quiet: an HTML marker comment directly above a heading (bd setup output)", None, """\
# Title

Prose.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:970c3bf2 -->
## Beads Issue Tracker

Prose.
"""),
    ("H quiet: a `#` that is not a heading (no space after the hashes)", None, """\
# Title

Prose about issue
#12345 which is not a heading.
"""),
]


def smoke_markdown(tmp: Path):
    print("lint_markdown.py")
    for i, (name, expect, body) in enumerate(MD_CASES):
        f = write(tmp / "md" / f"case{i:02d}.md", body)
        rc, out = run(LINT, str(f), "--json")
        try:
            rules = "".join(x["rule"] for x in json.loads(out)["findings"])
        except (json.JSONDecodeError, KeyError):
            check(name, False, out)
            continue
        want = expect or ""
        ok = rules == want and rc == (1 if want else 0) and "Traceback" not in out
        check(name, ok, f"got rules={rules!r} rc={rc} want={want!r}\n{out}")

    # The whole tree, and the references/ Markdown the default glob does not reach.
    rc, out = run(LINT)
    check("silent on the repo's SKILL.mds and root *.md", rc == 0 and "MARKDOWN: OK" in out, out)
    rc, out = run(LINT, str(REPO / "skills"))
    check("silent on every *.md under skills/ (references/ included)",
          rc == 0 and "MARKDOWN: OK" in out, out)


# =====================================================================================
# release_check.py
# =====================================================================================
def smoke_release():
    print("release_check.py")

    rc, out = run(RELEASE)
    check("development mode passes on the tree as it stands (exit 0)",
          rc == 0 and "RELEASE: OK" in out, out)
    # The real tree is unbumped on every day that is not a release day, and bumped on the day
    # it matters most. These two ran against the tree and asserted the unbumped case, so they
    # went red the moment someone actually cut a release - a check that fails only during the
    # operation it exists to guard. Assert on whichever state the tree is in; the *behaviour*
    # is pinned against fixture repos below, where it can be set deliberately.
    check("development mode explains its version verdict either way",
          ("unchanged from HEAD" in out and "--release" in out) or "version bumped" in out, out)

    rc, out = run(RELEASE, "--release")
    if "unchanged from HEAD" in out or "was not bumped" in out:
        # Exit 2, not 1: not bumped is a different answer to metadata that disagrees.
        check("--release turns an unbumped version into exit 2", rc == 2, out)
        check("exit 2 does not claim the metadata disagrees",
              "was not bumped" in out and "disagreement" not in out.split("RELEASE:")[-1], out)
    else:
        check("--release passes on a tree whose version really was bumped", rc == 0, out)

    rc, out = run(RELEASE, "--json")
    try:
        doc = json.loads(out)
        ok = doc["failures"] == [] and len(doc["skills"]) >= 1 and doc["exit"] == 0
    except (json.JSONDecodeError, KeyError):
        ok = False
    check("--json is parseable and reports no failures on the tree", ok, out)

    rc, out = run(RELEASE, "--baseline", "0.0.1")
    check("--baseline replaces the HEAD lookup and reports the bump it saw",
          rc == 0 and "0.0.1 ->" in out, out)


def smoke_release_fixtures(tmp: Path):
    """Every rule that needs *broken* metadata, against throwaway repos shaped like this one.

    Nothing here mutates the real tree, not even briefly. Three other agents are editing it
    right now, and a smoke test that rewrites `.claude-plugin/` or `skills/` — however
    carefully it restores them afterwards — can lose somebody else's edit in the window
    between the two writes. So each case builds a fixture repo from scratch and copies
    `release_check.py` into a `tools/` inside it, since the script locates the repo it is
    judging from its own path.

    The fixture has no git at all, which is exactly why `--baseline` exists on the script: it
    is how the bump comparison is made against something other than HEAD, and it is what makes
    "went backwards" and "genuinely bumped" testable without a commit.
    """
    print("release_check.py (on fixture repos — the real tree is never written)")

    DESC = ("A personal collection of Claude Code skills for indie game development: "
            "Godot 4 in-game UI, itch.io deploys, and Kenney asset kit conventions.")
    KEYWORDS = ["godot", "gamedev", "itch.io", "butler", "kenney"]

    def build(root: Path, *, skills, readme_names=None, frontmatter=None,
              version="1.0.0", market_desc=None, market_keywords=None, market_name="probe"):
        write(root / "tools" / "release_check.py", RELEASE.read_text(encoding="utf-8"))
        write(root / ".claude-plugin" / "plugin.json", json.dumps({
            "name": "probe", "version": version, "description": DESC, "keywords": KEYWORDS,
        }, indent=2) + "\n")
        write(root / ".claude-plugin" / "marketplace.json", json.dumps({
            "name": "probe", "owner": {"name": "x"},
            "plugins": [{"name": market_name, "source": "./",
                         "description": DESC if market_desc is None else market_desc,
                         "keywords": KEYWORDS if market_keywords is None else market_keywords}],
        }, indent=2) + "\n")
        rows = "".join(f"| `{n}` | does a thing |\n"
                       for n in (readme_names if readme_names is not None else skills))
        write(root / "README.md", f"# probe\n\n| Skill | What it does |\n| --- | --- |\n{rows}")
        for s in skills:
            fm = (frontmatter or {}).get(s, f"---\nname: {s}\ndescription: does a thing\n---\n")
            write(root / "skills" / s / "SKILL.md", fm + f"\n# {s}\n\nProse.\n")
        return root / "tools" / "release_check.py"

    def case(name, expect_rc, expect_text, args=(), **kw):
        with tempfile.TemporaryDirectory() as td:
            script = build(Path(td) / "repo", **kw)
            rc, out = run(script, *args)
            wanted = [expect_text] if isinstance(expect_text, str) else list(expect_text or [])
            ok = rc == expect_rc and all(w in out for w in wanted)
            check(name, ok and "Traceback" not in out, f"rc={rc}\n{out}")

    # HEAD carries no plugin.json in a fixture with no git at all: the bump check must be
    # skipped, not failed. An unavailable comparison is not evidence of a problem.
    case("a clean fixture repo passes, and says the bump check was skipped",
         0, "bump check skipped", skills=["alpha", "beta"])

    # --- D / K: the two hand-synced fields ---------------------------------------------
    case("[D] a one-word description drift is a FAIL that names the differing text",
         1, ["description drift", "first differs at character",
             "'4 in-game UI", "'3 in-game UI"],
         skills=["alpha"], market_desc=DESC.replace("Godot 4", "Godot 3", 1))
    case("[D] quiet: identical descriptions with the keywords intact",
         0, "RELEASE: OK", skills=["alpha"])
    case("[K] a dropped keyword is a FAIL naming the keyword",
         1, ["keyword drift", "butler"],
         skills=["alpha"], market_keywords=[k for k in KEYWORDS if k != "butler"])
    case("[K] a reordered keyword list is a FAIL, and is reported as ordering",
         1, "keyword order differs",
         skills=["alpha"], market_keywords=[KEYWORDS[1], KEYWORDS[0], *KEYWORDS[2:]])
    case("[D] a marketplace entry under a different plugin name is a FAIL",
         1, "lists no plugin named 'probe'", skills=["alpha"], market_name="prob")

    # --- V: the version, compared against an explicit baseline --------------------------
    case("[V] a version below the baseline is a FAIL even in development mode",
         1, "went backwards", skills=["alpha"], version="0.0.1",
         args=("--baseline", "1.0.0"))
    case("[V] a version that is not MAJOR.MINOR.PATCH is a FAIL",
         1, "not MAJOR.MINOR.PATCH", skills=["alpha"], version="1.0")
    case("[V] equal to the baseline is a note in development mode (exit 0)",
         0, ["version is unchanged", "--release"], skills=["alpha"],
         args=("--baseline", "1.0.0"))
    case("[V] equal to the baseline is exit 2 under --release, not exit 1",
         2, ["was not bumped", "the metadata agrees with itself"], skills=["alpha"],
         args=("--baseline", "1.0.0", "--release"))
    case("[V] a genuinely bumped version passes --release (exit 0)",
         0, ["RELEASE: OK", "0.9.0 -> 1.0.0"], skills=["alpha"],
         args=("--baseline", "0.9.0", "--release"))
    case("[V] a real disagreement under --release is exit 1, not exit 2",
         1, "keyword drift", skills=["alpha"],
         market_keywords=KEYWORDS[:-1], args=("--baseline", "1.0.0", "--release"))
    case("[V] an unparseable baseline is skipped, not failed",
         0, "bump check skipped", skills=["alpha"], args=("--baseline", "v1"))

    # --- F: SKILL.md frontmatter --------------------------------------------------------
    case("[F] a SKILL.md whose name != its directory is a FAIL",
         1, "declares name: 'alfa'", skills=["alpha"],
         frontmatter={"alpha": "---\nname: alfa\ndescription: does a thing\n---\n"})
    case("[F] an extra frontmatter key is a FAIL",
         1, "carries version", skills=["alpha"],
         frontmatter={"alpha": "---\nname: alpha\ndescription: d\nversion: 2\n---\n"})
    case("[F] a missing description is a FAIL",
         1, "is missing description", skills=["alpha"],
         frontmatter={"alpha": "---\nname: alpha\n---\n"})
    case("[F] an empty description is a FAIL",
         1, "empty description", skills=["alpha"],
         frontmatter={"alpha": "---\nname: alpha\ndescription:\n---\n"})
    case("[F] no frontmatter at all is a FAIL",
         1, "does not open with", skills=["alpha"],
         frontmatter={"alpha": "# alpha\n"})
    case("[F] unterminated frontmatter is a FAIL",
         1, "never closed", skills=["alpha"],
         frontmatter={"alpha": "---\nname: alpha\ndescription: d\n"})
    case("[F] quiet: a description folded over several lines is legitimate",
         0, "RELEASE: OK", skills=["alpha"],
         frontmatter={"alpha": "---\nname: alpha\ndescription: a long description that\n"
                               "  continues on the next line\n---\n"})

    # --- R: the README table ------------------------------------------------------------
    case("[R] a skill missing from the README table is a FAIL",
         1, "not in README.md's table", skills=["alpha", "beta"], readme_names=["alpha"])
    case("[R] a README row naming a directory that does not exist is a FAIL",
         1, "which is not a skill directory", skills=["alpha"],
         readme_names=["alpha", "ghost"])


def main():
    before = {p: (p.read_bytes() if p.is_file() else None) for p in WATCHED}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        smoke_markdown(tmp)
        print()
        smoke_release()
        print()
        smoke_release_fixtures(tmp)

    # Last, and it is not a formality: this whole file exists to prove two checks behave, and
    # it would be a poor trade to learn that by editing files three other people are holding.
    print()
    changed = [str(p) for p, b in before.items() if (p.read_bytes() if p.is_file() else None) != b]
    check("nothing outside tools/ was written", not changed, "\n".join(changed))

    if FAILS:
        name, out = FAILS[0]
        print(f"\nSMOKE: {len(FAILS)} FAILED; first: {name}\n{out}")
        return 1
    print("\nSMOKE: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
