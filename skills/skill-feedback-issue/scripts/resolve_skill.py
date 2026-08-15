#!/usr/bin/env python3
"""Resolve a skill to the repo it ships from, and to the tree it actually ran from.

Step 1 of this skill needs two answers, and only one of them is written down anywhere
obvious. The easy one is *which repo* — cross-reference `installed_plugins.json` with
`known_marketplaces.json` and read the slug. The hard one is *which copy of the skill
produced the behaviour you are about to report*, and that is not the same question.

The plugin cache keeps every version ever installed, side by side:

    ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/

`installed_plugins.json` names one of them as `installPath`. The directory a skill is
loaded from is not guaranteed to be that one — a session can be running from an older
cached tree while that file already records a newer install. For most skills that is a
harmless discrepancy. For *this* skill it is the front door: the whole premise of the
re-verification step is that feedback from a stale install is the most common false alarm
in the loop, so confirming a line number in a tree that did not execute produces exactly
the false alarm the step exists to prevent, and stamps the wrong version on the report
while doing it.

So this script answers, mechanically:

  * the `owner/name` slug to file against, or why there is nowhere to file
  * what `installed_plugins.json` currently records — path, version, sha
  * every version sitting in the cache, so "there is only one" is a fact and not a guess
  * given `--ran-from`, whether the tree that ran is the tree that file names — and if
    not, whether *this skill's own files* differ between the two, which is what decides
    whether your line numbers are trustworthy or merely lucky

That last check is the point. Two versions of a plugin nearly always differ *somewhere*;
what matters is whether they differ in the skill you are reporting on. This repo's own
history has both cases: `skill-feedback-issue/SKILL.md` is byte-identical across four
consecutive releases, and changed materially in the one before them.

Usage:
    python resolve_skill.py godot-game-ui
    python resolve_skill.py skill-feedback-issue --ran-from "<the base directory the harness announced>"
    python resolve_skill.py godot-game-ui --json

Exits 0 when the slug resolved and nothing contradicts itself, 1 when there is nowhere to
file or the tree that ran disagrees with the recorded install in a way that affects this
skill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Same reasoning as seed.py: this is read through a pipe or captured by an agent at least
# as often as it is read on a console, and Windows would otherwise encode to the codepage.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def plugins_root() -> Path:
    """`~/.claude/plugins`, unless CLAUDE_CONFIG_DIR moves the whole config tree."""
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(cfg) if cfg else Path.home() / ".claude"
    return base / "plugins"


def load_json(path: Path) -> dict:
    if not path.is_file():
        sys.exit(f"error: {path} not found — is this a plugin install at all?")
    return json.loads(path.read_text(encoding="utf-8"))


def version_of(path: Path) -> str:
    """The cache lays out .../<plugin>/<version>/, so the version is the leaf directory.

    Taken from the path rather than from a manifest on purpose: the question being asked is
    which *directory* ran, and a plugin.json read out of that directory would answer a
    different question — what that tree calls itself, which is the same string only when
    nothing went wrong.
    """
    return path.name


def find_skill(install_path: Path, skill: str) -> Path | None:
    """Locate a skill inside a plugin, under either layout it can ship in.

    `skills/<name>/SKILL.md` is the common one. A plugin can equally expose a skill as a
    single `commands/<name>.md`, and both register under the same invocable name — the
    plugin that prompted this script does exactly that. Checking only the directory layout
    reports "no installed plugin carries this skill" for a skill that plainly ran, which
    sends the reader looking for a typo in a name that was correct.
    """
    d = install_path / "skills" / skill
    if d.is_dir():
        return d
    f = install_path / "commands" / f"{skill}.md"
    return f if f.is_file() else None


def digest_tree(root: Path) -> dict[str, str]:
    """{relative path: sha1} for every file at `root`, __pycache__ excluded.

    Takes a directory or a single file, since a skill can be either. Compiled bytecode is a
    build artefact of whoever ran the scripts last rather than part of the skill, and
    including it reports a difference between two identical trees.
    """
    if root.is_file():
        return {root.name: hashlib.sha1(root.read_bytes()).hexdigest()}
    out: dict[str, str] = {}
    for f in sorted(root.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        out[f.relative_to(root).as_posix()] = hashlib.sha1(f.read_bytes()).hexdigest()
    return out


def resolve_slug(marketplace: str, markets: dict) -> tuple[str | None, str]:
    """Return (owner/name, how it was determined) for a marketplace name."""
    entry = markets.get(marketplace)
    if not entry:
        return None, f"marketplace {marketplace!r} is not in known_marketplaces.json"
    src = entry.get("source", {})
    kind = src.get("source")
    if kind == "github":
        return src.get("repo"), "known_marketplaces.json source.repo"
    if kind == "directory":
        path = src.get("path") or entry.get("installLocation")
        if not path:
            return None, "directory marketplace with no path recorded"
        try:
            url = subprocess.run(
                ["git", "-C", str(path), "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=15,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            return None, f"could not read origin of {path}: {exc}"
        if not url:
            return None, f"local-only marketplace at {path} has no origin — nowhere to file"
        m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$", url)
        return (m.group(1) if m else None), f"git origin of {path}"
    return None, f"unhandled marketplace source {kind!r}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("skill", help="the skill's directory name, e.g. godot-game-ui")
    ap.add_argument("--ran-from", type=Path, default=None,
                    help="the base directory the harness announced for this skill. Pass it "
                         "whenever you have it — it is the only way to tell which tree ran.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    root = plugins_root()
    installed = load_json(root / "installed_plugins.json")
    markets = load_json(root / "known_marketplaces.json")

    # Find every installed plugin that actually carries this skill, rather than trusting a
    # name to match: plugins are free to bundle a skill whose name resembles their own.
    matches: list[dict] = []
    for key, entries in installed.get("plugins", {}).items():
        plugin, _, marketplace = key.partition("@")
        for e in entries if isinstance(entries, list) else [entries]:
            ip = Path(e.get("installPath", ""))
            if not ip or not find_skill(ip, args.skill):
                continue
            slug, how = resolve_slug(marketplace, markets)
            matches.append({
                "plugin": plugin, "marketplace": marketplace, "slug": slug,
                "slug_source": how, "installPath": str(ip),
                "version": e.get("version", "unknown"),
                "sha": e.get("gitCommitSha"), "scope": e.get("scope"),
            })

    report: dict = {"skill": args.skill, "matches": matches, "cached_versions": [],
                    "ran_from": None, "mismatch": None, "skill_differs": None,
                    "skill_location": None}

    if not matches:
        loose = Path.home() / ".claude" / "skills" / args.skill
        if loose.is_dir():
            msg = (f"{args.skill} is installed loose at {loose}, not as a plugin.\n"
                   f"There is no repo behind it — offer to edit it in place instead of filing.")
        else:
            msg = (f"no installed plugin carries skills/{args.skill}/ or "
                   f"commands/{args.skill}.md.\n"
                   f"Check the name against the directory, not against the skill's title.")
        if args.json:
            report["error"] = msg
            print(json.dumps(report, indent=2))
        else:
            print(msg)
        return 1

    m = matches[0]
    recorded = Path(m["installPath"])
    # Sibling directories of the recorded install are the other cached versions. Listing them
    # turns "there is probably only one" into a countable fact.
    cache_dir = recorded.parent
    cached = sorted(p.name for p in cache_dir.iterdir() if p.is_dir()) if cache_dir.is_dir() else []
    report["cached_versions"] = cached

    ran_version = None
    if args.ran_from:
        ran = args.ran_from.resolve()
        # The announced path points at the skill's own directory; walk up to the version root.
        while ran.name and ran.name not in cached and ran.parent != ran:
            ran = ran.parent
        ran_version = ran.name if ran.name in cached else version_of(args.ran_from)
        report["ran_from"] = {"path": str(args.ran_from), "version": ran_version}
        report["mismatch"] = ran_version != m["version"]

        if report["mismatch"]:
            a = find_skill(cache_dir / ran_version, args.skill)
            b = find_skill(recorded, args.skill)
            if a:
                report["skill_location"] = a.relative_to(cache_dir / ran_version).as_posix()
            if a and b:
                da, db = digest_tree(a), digest_tree(b)
                changed = sorted(
                    set(da) ^ set(db) | {k for k in set(da) & set(db) if da[k] != db[k]}
                )
                report["skill_differs"] = changed
            else:
                report["skill_differs"] = ["<skill absent from one of the two trees>"]

    if args.json:
        print(json.dumps(report, indent=2))
        return 1 if (not m["slug"] or report["mismatch"]) else 0

    print(f"skill:        {args.skill}")
    print(f"plugin:       {m['plugin']}@{m['marketplace']} ({m['scope']} scope)")
    print(f"file against: {m['slug'] or 'NOWHERE — ' + m['slug_source']}")
    if m["slug"]:
        print(f"              (via {m['slug_source']})")
    print(f"recorded:     {m['version']}  sha {m['sha'] or '(none recorded)'}")
    print(f"              {m['installPath']}")
    print(f"cached:       {len(cached)} version(s) — {', '.join(cached) or '(none)'}")
    if len(matches) > 1:
        print(f"NOTE:         {len(matches)} installed plugins carry this skill; "
              f"using the first. Others: "
              f"{', '.join(x['plugin'] + '@' + x['marketplace'] for x in matches[1:])}")
    print()

    if not args.ran_from:
        print("ran-from:     NOT CHECKED. Pass --ran-from with the base directory the")
        print("              harness announced for this skill. Without it you are assuming")
        print(f"              the run came from {m['version']}, and {len(cached)} version(s)")
        print("              are sitting in that cache.")
        return 0 if m["slug"] else 1

    print(f"ran from:     {ran_version}")
    if not report["mismatch"]:
        print(f"MATCH:        the tree that ran is the tree installed_plugins.json records.")
        print(f"              Line numbers and the {m['version']} version stamp are both safe.")
        return 0 if m["slug"] else 1

    print(f"MISMATCH:     ran from {ran_version}, but installed_plugins.json records "
          f"{m['version']}.")
    where = report["skill_location"] or f"skills/{args.skill}"
    diffs = report["skill_differs"] or []
    if not diffs:
        print(f"              {where} is byte-identical in both, so the")
        print("              instructions you followed were the current ones. That is luck,")
        print("              not design — quote both versions in the Environment line.")
    else:
        print(f"              and {where} DIFFERS between them:")
        for f in diffs:
            print(f"                {f}")
        print()
        print("              Every line number you cite must come from the tree that ran")
        print(f"              ({ran_version}), and the report must say so — a claim confirmed")
        print("              in a tree that did not execute is the false alarm this step")
        print("              exists to prevent. Re-verify there before filing.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
