#!/usr/bin/env python3
"""Assert the release metadata agrees with itself before it ships.

`plugin.json` and `marketplace.json` carry the *same* description and the *same* keyword list,
in two files, kept in step by hand — CLAUDE.md says so in as many words. Three releases were
cut that way and one of them shipped three keywords mis-indented in `marketplace.json` for a
whole version. Nothing in this repo looks at either file, so nothing noticed. The other
hand-maintained surfaces are the same shape: the version in `plugin.json`, the frontmatter of
every `skills/*/SKILL.md`, and the skill table in `README.md`.

Five checks:

  D. The two descriptions are byte-identical. On a mismatch this prints the first differing
     character and both tails, because a check that says only "they differ" over a
     four-hundred-character sentence makes you diff it by hand anyway.
  K. The two keyword lists are identical *and in the same order*. Same hand-sync surface, and
     ordering is worth holding because a reordered list is how a dropped keyword hides.
  V. The version parses as `MAJOR.MINOR.PATCH` and has not gone backwards relative to
     `git show HEAD:.claude-plugin/plugin.json`. See the exit codes below — "unchanged" is a
     different answer to "backwards", and only one of them is ever a mistake.
  F. Every `skills/*/SKILL.md` opens with `---`, carries exactly `name` and `description` and
     nothing else, and its `name` equals its directory name. That last one is the trap: the
     directory is what the plugin loader lists and the frontmatter `name` is what a user types,
     so a copy-pasted SKILL.md that kept the name it was forked from produces a skill that
     cannot be invoked by the name it appears under, with no error anywhere.
  R. Every skill directory is named in `README.md`. CLAUDE.md lists updating that table as a
     release step, which means it is a step that can be forgotten.

## Exit codes

    0   everything agrees. In the default mode this includes "the version is the same as
        HEAD's", which is the normal state of the tree on every day that is not a release day.
        A check that goes red when nothing is wrong gets switched off, so it does not.
    1   something disagrees: the descriptions or keywords have drifted, a SKILL.md's
        frontmatter is wrong, a skill is missing from the README, or the version went
        *backwards* or stopped parsing. These are mistakes in every mode.
    2   with `--release`: everything else agrees, but the version was not bumped. Deliberately
        its own code — it is the one finding that is a mistake only in the context of cutting
        a release, and a caller that wants to gate on real disagreements can treat 1 and 2
        differently.

If HEAD carries no `plugin.json` (a fresh repo, a detached worktree, no git at all) the bump
check reports that it was skipped and does not fail. An unavailable comparison is not evidence
of a problem. `--baseline` replaces that lookup with a version you name, which is what you
want when the question is "is this newer than what is *published*" rather than "newer than the
last commit" — the two diverge the moment a release commit lands and the tag does not.

Usage:
    python tools/release_check.py                 # mid-development: unchanged version is fine
    python tools/release_check.py --release       # cutting a release: it had better be bumped
    python tools/release_check.py --baseline 0.14.0
    python tools/release_check.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
README = REPO_ROOT / "README.md"
SKILLS_DIR = REPO_ROOT / "skills"

ALLOWED_FRONTMATTER = {"name", "description"}

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def semver(text: str) -> tuple[int, int, int] | None:
    m = _SEMVER_RE.match(text.strip())
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def first_difference(a: str, b: str) -> str:
    """Say *where* two strings part company, with enough context to fix it in one look."""
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    if i == len(a) == len(b):
        return "identical"
    lead = a[max(0, i - 30):i]
    return (f"first differs at character {i} after ...{lead!r}\n"
            f"           plugin.json: {a[i:i + 60]!r}\n"
            f"      marketplace.json: {b[i:i + 60]!r}")


def head_version() -> tuple[str | None, str | None]:
    """(version string at HEAD, reason it is unavailable). Exactly one is None."""
    try:
        p = subprocess.run(
            ["git", "show", "HEAD:.claude-plugin/plugin.json"],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        return None, f"git is not runnable here ({exc})"
    if p.returncode != 0:
        return None, "HEAD carries no .claude-plugin/plugin.json"
    try:
        return json.loads(p.stdout).get("version"), None
    except json.JSONDecodeError as exc:
        return None, f"HEAD's plugin.json does not parse ({exc})"


def read_frontmatter(path: Path) -> tuple[dict[str, str], str | None]:
    """Return ({key: value}, error). A malformed block yields ({}, why)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "does not open with `---` on line 1"
    fields: dict[str, str] = {}
    last: str | None = None
    for n, raw in enumerate(lines[1:], 2):
        if raw.strip() == "---":
            return fields, None
        m = re.match(r"^([A-Za-z0-9_-]+):[ \t]*(.*)$", raw)
        if m:
            last = m.group(1)
            fields[last] = m.group(2).strip()
        elif raw.strip() and last:
            fields[last] += " " + raw.strip()      # a folded multi-line value
        elif raw.strip():
            return {}, f"line {n} is neither `key: value` nor a continuation: {raw.strip()!r}"
    return {}, "frontmatter is never closed with a second `---`"


def run(release: bool, baseline: str | None = None) -> tuple[list[str], list[str], list[str]]:
    """Return (failures, notes, scanned skill names)."""
    failures: list[str] = []
    notes: list[str] = []

    for path in (PLUGIN_JSON, MARKETPLACE_JSON, README):
        if not path.is_file():
            failures.append(f"[?] missing: {path.relative_to(REPO_ROOT)}")
    if failures:
        return failures, notes, []

    try:
        plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
        market = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"[?] {exc}"], notes, []

    entries = market.get("plugins", [])
    entry = next((e for e in entries if e.get("name") == plugin.get("name")), None)
    if entry is None:
        failures.append(
            f"[D] marketplace.json lists no plugin named {plugin.get('name')!r} "
            f"(it has: {', '.join(repr(e.get('name')) for e in entries) or 'nothing'})"
        )
        entry = {}

    # --- D: descriptions ---------------------------------------------------------------
    pd, md = plugin.get("description", ""), entry.get("description", "")
    if pd != md:
        failures.append(f"[D] description drift — {first_difference(pd, md)}")

    # --- K: keywords -------------------------------------------------------------------
    pk, mk = plugin.get("keywords", []), entry.get("keywords", [])
    if pk != mk:
        only_p = [k for k in pk if k not in mk]
        only_m = [k for k in mk if k not in pk]
        if only_p or only_m:
            failures.append(
                f"[K] keyword drift — only in plugin.json: {only_p or 'none'}; "
                f"only in marketplace.json: {only_m or 'none'}"
            )
        else:
            failures.append(
                f"[K] keyword order differs — plugin.json {pk}, marketplace.json {mk}"
            )

    # --- V: version --------------------------------------------------------------------
    raw = str(plugin.get("version", ""))
    here = semver(raw)
    if here is None:
        failures.append(f"[V] version {raw!r} is not MAJOR.MINOR.PATCH")
    else:
        if baseline is not None:
            there_raw, why, source = baseline, None, "the baseline"
        else:
            there_raw, why = head_version()
            source = "HEAD"
        if why or there_raw is None:
            notes.append(f"[V] bump check skipped — {why or 'HEAD has no version field'}")
        else:
            there = semver(str(there_raw))
            if there is None:
                notes.append(f"[V] bump check skipped — {source} version {there_raw!r} does not parse")
            elif here < there:
                failures.append(
                    f"[V] version went backwards: {raw} is below {source} ({there_raw})"
                )
            elif here == there:
                msg = f"version is unchanged from {source} ({raw})"
                if release:
                    failures.append(f"[V] {msg} — a release has to bump it")
                else:
                    notes.append(f"[V] {msg}; pass --release to make that a failure")
            else:
                notes.append(f"[V] version bumped {there_raw} -> {raw}")

    # --- F: SKILL.md frontmatter -------------------------------------------------------
    skills = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir()) if SKILLS_DIR.is_dir() else []
    names: list[str] = []
    for d in skills:
        names.append(d.name)
        skill_md = d / "SKILL.md"
        if not skill_md.is_file():
            failures.append(f"[F] skills/{d.name}/ has no SKILL.md")
            continue
        fields, err = read_frontmatter(skill_md)
        if err:
            failures.append(f"[F] skills/{d.name}/SKILL.md: {err}")
            continue
        missing = ALLOWED_FRONTMATTER - fields.keys()
        extra = fields.keys() - ALLOWED_FRONTMATTER
        if missing:
            failures.append(f"[F] skills/{d.name}/SKILL.md frontmatter is missing "
                            f"{', '.join(sorted(missing))}")
        if extra:
            failures.append(f"[F] skills/{d.name}/SKILL.md frontmatter carries "
                            f"{', '.join(sorted(extra))} — the contract is name + description only")
        got = fields.get("name", "")
        if got and got != d.name:
            failures.append(
                f"[F] skills/{d.name}/SKILL.md declares name: {got!r} — it must equal its "
                f"directory name, which is what the plugin loader lists it under"
            )
        if "description" in fields and not fields["description"]:
            failures.append(f"[F] skills/{d.name}/SKILL.md has an empty description — that is "
                            f"the whole trigger surface, so the skill would never load")

    # --- R: README table ---------------------------------------------------------------
    readme = README.read_text(encoding="utf-8")
    # Match the table's own convention (a backticked name) rather than a bare substring:
    # `itch-devlog` appearing inside a sentence about `itch-ci-deploy` would otherwise count.
    listed = set(re.findall(r"^\|\s*`([^`]+)`\s*\|", readme, re.M))
    for name in names:
        if name not in listed:
            failures.append(f"[R] skills/{name}/ is not in README.md's table")
    for name in sorted(listed - set(names)):
        failures.append(f"[R] README.md's table lists `{name}`, which is not a skill directory")

    return failures, notes, names


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--release", action="store_true",
                    help="cutting a release: an unbumped version becomes a failure (exit 2)")
    ap.add_argument("--baseline", metavar="VERSION",
                    help="compare the version against this instead of against HEAD's "
                         "(e.g. the version actually published)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    failures, notes, names = run(args.release, args.baseline)
    unbumped = any(f.startswith("[V]") and "version is unchanged" in f for f in failures)
    code = 1 if [f for f in failures if not (unbumped and f.startswith("[V]"))] else (2 if unbumped else 0)

    if args.json:
        print(json.dumps({
            "mode": "release" if args.release else "development",
            "skills": names,
            "failures": failures,
            "notes": notes,
            "exit": code,
        }, indent=2))
        return code

    # Name the denominator, as palette_lint does: "RELEASE: OK" over zero skills would be the
    # report lying about what it looked at.
    print(f"{REPO_ROOT}")
    print(f"  mode: {'release' if args.release else 'development'}")
    print(f"  {len(names)} skill(s): {', '.join(names)}")
    print()
    for n in notes:
        print(f"note: {n}")
    if notes:
        print()
    if not failures:
        print(f"RELEASE: OK — the metadata agrees with itself across "
              f"plugin.json, marketplace.json, README.md and {len(names)} SKILL.md.")
        return code
    for f in failures:
        print(f)
    print()
    if code == 2:
        print("RELEASE: the metadata agrees with itself, but the version was not bumped.")
    else:
        print(f"RELEASE: {len(failures)} disagreement(s).")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
