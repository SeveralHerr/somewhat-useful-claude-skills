#!/usr/bin/env python3
"""Run every check a skill in this repo ships, in a throwaway Godot project.

Verifying a change to a `.gd` template means the same loop every time: write a minimal
`project.godot`, run the skill's scaffolder into it, run `godot --headless --path <p>
--import` so the global class cache is rebuilt, copy the test scripts in, run each one,
and *read stderr* rather than trusting the exit code. That loop was hand-rolled six times
in two sessions. The step that gets dropped is the import pass, and dropping it produces a
parse-error cascade in files nobody touched ("Could not find type GameHud"), which sends
you debugging the template instead of the missing cache.

So the import is not a step here, it is a type. `godot_import()` is the only thing that
can construct an `ImportedProject`, and `run_godot_script()` takes one of those rather
than a path, then re-checks the class cache on disk at call time. There is no way to spell
a test run that skipped the import; the cascade is unreachable from this file.

What runs is *discovered*, not tabled, so a skill added next month is picked up:

    scripts/*test*.py       a pure-Python self-test          run as-is, no Godot
    scripts/palette_lint.py the source lint                  run over the skill's own
                            (colours a re-skin cannot reach) templates AND over the
                                                             scaffolded scripts/ui
    assets/*_test.gd        a Godot test                     needs a project, see below
    scripts/scaffold_*.py   how the .gd under test gets      used only when there are
                            into a project                   assets/*_test.gd
    scripts/*.gd            the .gd under test, when the     copied to the project root
                            skill ships no scaffolder        (godot-2d-placement-audit)

Discovery fails loudly rather than quietly skipping: a skill with `assets/*_test.gd` and
no way to get code into a project, or with two scaffolders and no way to choose, exits 2.
A skill with none of the above is not an error - "nothing to verify" is a real answer for
the probe-only skills (kenney-asset-kit, blender-mcp-modelling, ...) and exits 0.

Pass is not "exit 0". Two of these suites cannot be judged on their exit code at all:
`juice_test.gd` ends by returning true from `_process`, which quits the SceneTree with 0
whether or not it failed, so only the `JUICE: ALL PASS` line on stdout distinguishes them.
Every lane therefore needs its marker line AND a clean exit AND clean stderr:

    PASS      marker present, exit 0, nothing on stderr
    FAIL      marker missing or says FAILED, or non-zero exit, or stderr carried an
              engine error (`SCRIPT ERROR`, `ERROR:`, `Parse Error`, `USER ERROR`)
    SUSPECT   marker present and exit 0, but stderr carried something else - a warning,
              a deprecation. Reported in full and counted as a pass; `--strict` counts it
              as a failure. Graded rather than fatal on purpose: a check that fires on
              legitimate output gets switched off within a week. Measured baseline on
              4.7.1 is an entirely empty stderr for all four suites, so anything here is
              worth printing even when it is not worth failing on.
    SKIP      godot is not on PATH. The Python lanes still run.

`--mutate <relpath> <find> <replace>` runs the second half of the CLAUDE.md convention:
an assertion is not done until it has been shown to FAIL against the defect it describes.
It patches the *scaffolded copy* (never the repo), re-imports, re-runs, and requires the
suite to go RED; then restores, re-imports, re-runs and requires GREEN again. Its exit
code answers "can this assertion fail?", so it is inverted relative to a plain run: 0
means the patch was caught, 1 means the suite stayed green and the assertion is decorative.

Usage:
    python tools/verify_skill.py godot-game-ui
    python tools/verify_skill.py godot-game-ui-juicy --keep
    python tools/verify_skill.py --all --json
    python tools/verify_skill.py godot-game-ui --palette clinical
    python tools/verify_skill.py godot-game-ui \\
        --mutate scripts/ui/hud.gd 'CarryCounter' 'CarryCounterX'

Exit codes (same 0/1/2 contract as scaffold_itch_deploy.py):
    0 = every check that ran passed, or the skill ships nothing to verify
    1 = a check failed; or under --mutate, the patch was NOT caught
    2 = could not run: unknown skill, a discovered file has moved, a suite has no way
        into a project, or --require-godot with no godot on PATH
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"

# Same reasoning as palette_lint.py and seed.py: this is read through a pipe, a CI log or
# an agent capturing stdout at least as often as on a console, and on Windows Python would
# otherwise encode to the active codepage and drop the em dashes as a stray byte.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CACHE_CLASS_RE = re.compile(r'"class":\s*&"([^"]+)"')
_CLASS_NAME_RE = re.compile(r"^class_name\s+([A-Za-z_][A-Za-z_0-9]*)", re.M)

# stderr lines that mean the run is wrong, not merely noisy. Godot writes parse errors,
# failed loads and push_error output here while exiting 0 in some paths - which is the
# whole reason CLAUDE.md says to read stderr rather than the exit code.
# Deliberately NOT matching the `   at: ...` continuation line: Godot prints one under
# warnings too, and grading a legitimate push_warning as a hard failure is how a check gets
# switched off. Warnings land in SUSPECT instead - printed, not fatal.
_ENGINE_ERROR_RE = re.compile(r"SCRIPT ERROR|USER ERROR|Parse Error|^ERROR:", re.M)

# `<WORD>: ALL PASS` / `<WORD>: 3 FAILED` / `SMOKE: 2 FAILED; first: ...`. Every suite in
# this repo ends with one of these; the word differs (SMOKE, JUICE, PALETTE) so it is
# matched rather than named, and the absence of any marker is itself a failure.
_MARKER_RE = re.compile(r"^([A-Z]+):\s+(ALL PASS|OK\b.*|\d+ FAILED.*|.*)$", re.M)
_PASS_MARKER_RE = re.compile(r"^([A-Z]+):\s+(ALL PASS|OK\b.*)$", re.M)

PROJECT_GODOT = """config_version=5

[application]

config/name="verify-skill-probe"
config/features=PackedStringArray("{ver}", "Forward Plus")
"""

PASS, FAIL, SUSPECT, SKIP = "PASS", "FAIL", "SUSPECT", "SKIP"


# --------------------------------------------------------------------------- discovery

class Discovery:
    """What one skill ships that can be run. Built only from files that exist."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.dir = SKILLS / name
        if not (self.dir / "SKILL.md").is_file():
            raise LookupError(name)
        scripts, assets = self.dir / "scripts", self.dir / "assets"
        self.py_tests = sorted(p for p in scripts.glob("*test*.py") if p.is_file())
        self.palette_lint = scripts / "palette_lint.py" if (scripts / "palette_lint.py").is_file() else None
        self.gd_tests = sorted(assets.glob("*_test.gd")) if assets.is_dir() else []
        self.scaffolders = sorted(scripts.glob("scaffold_*.py")) if scripts.is_dir() else []
        # .gd the skill ships to be USED (not the tests). Only relevant with no scaffolder.
        self.gd_sources = sorted(scripts.glob("*.gd")) if scripts.is_dir() else []

    @property
    def empty(self) -> bool:
        return not (self.py_tests or self.palette_lint or self.gd_tests)

    def how_gd_gets_in(self) -> tuple[str, list[Path]]:
        """`("scaffold", [script])` or `("copy", [sources])`, or raise with the reason.

        Loud rather than lenient: this is the branch that would otherwise silently verify
        nothing after somebody renames a directory.
        """
        if self.scaffolders and self.gd_sources:
            # Not ambiguous, just unsupported - and saying so beats guessing.
            raise ValueError(f"{self.name}: ships both scripts/scaffold_*.py and scripts/*.gd; "
                             f"verify_skill.py cannot tell which installs the code under test")
        if len(self.scaffolders) > 1:
            raise ValueError(f"{self.name}: {len(self.scaffolders)} scaffolders "
                             f"({', '.join(p.name for p in self.scaffolders)}); "
                             f"cannot tell which one installs the code under test")
        if self.scaffolders:
            return "scaffold", self.scaffolders
        if self.gd_sources:
            return "copy", self.gd_sources
        raise ValueError(f"{self.name}: has {len(self.gd_tests)} assets/*_test.gd but no "
                         f"scripts/scaffold_*.py and no scripts/*.gd - nothing would put the "
                         f"code under test into a project. Has a file moved?")


def all_skills() -> list[str]:
    return sorted(p.name for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())


# ------------------------------------------------------------------------- run plumbing

def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def run(cmd: list[str], timeout: int = 600) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, strip_ansi(p.stdout or ""), strip_ansi(p.stderr or "")


def _msys_to_win(p: str) -> str:
    """`/c/Users/x` -> `C:/Users/x`. Only Git Bash writes paths that way."""
    m = re.match(r"^/([a-zA-Z])/(.*)$", p)
    return f"{m.group(1).upper()}:/{m.group(2)}" if m else p


def _follow_shim(path: Path) -> Path:
    """Follow a `#!/bin/sh ... exec "<real binary>"` wrapper to the binary it runs.

    On Windows, Godot is often installed as an extensionless shim on PATH so that
    `godot` works in Git Bash. `shutil.which` will not return it (no PATHEXT match) and
    CreateProcess cannot execute it, so a naive probe concludes "godot is not installed"
    about a machine where `godot --version` plainly works. Reading the shim is cheaper
    than making the user pass --godot on the one platform this repo is developed on.
    """
    try:
        head = path.read_bytes()[:512]
    except OSError:
        return path
    if not head.startswith(b"#!"):
        return path
    m = re.search(r'exec\s+"?([^"\n]+?)"?[\s"]', head.decode("utf-8", "replace"))
    return Path(_msys_to_win(m.group(1))) if m else path


def _runs_as_godot(cand: Path) -> bool:
    try:
        rc, out, _ = run([str(cand), "--version"], timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return rc == 0 and bool(re.search(r"^\d+\.\d+", out.strip()))


def find_godot(explicit: str | None) -> str | None:
    """The binary, or None. Every candidate is confirmed by running `--version`."""
    names = [explicit] if explicit else ["godot", "godot4", "godot.exe", "godot4.exe"]
    for name in names:
        if not name:
            continue
        cands: list[Path] = []
        if os.sep in name or "/" in name:
            cands.append(Path(name))
        else:
            found = shutil.which(name)
            if found:
                cands.append(Path(found))
            # Manual PATH sweep: picks up the extensionless shim which() skips on Windows.
            for d in os.environ.get("PATH", "").split(os.pathsep):
                p = Path(d) / name
                if p.is_file() and p not in cands:
                    cands.append(p)
        for cand in cands:
            real = _follow_shim(cand)
            if _runs_as_godot(real):
                return str(real)
    return None


class Check:
    def __init__(self, name: str, status: str, summary: str,
                 command: str = "", stdout: str = "", stderr: str = "") -> None:
        self.name, self.status, self.summary = name, status, summary
        self.command, self.stdout, self.stderr = command, stdout, stderr

    def as_dict(self) -> dict:
        return {"check": self.name, "status": self.status, "summary": self.summary,
                "command": self.command,
                "stdout": self.stdout.strip(), "stderr": self.stderr.strip()}


def judge(name: str, cmd: list[str], rc: int, out: str, err: str) -> Check:
    """Marker AND exit code AND stderr. Any one of the three can sink a run.

    Marker first because it is the only signal `juice_test.gd` gives: it quits the
    SceneTree by returning true from `_process`, so its exit code is 0 either way.
    """
    shown = " ".join(cmd)
    err_lines = [ln for ln in err.splitlines() if ln.strip()]
    passed = _PASS_MARKER_RE.search(out)
    any_marker = _MARKER_RE.search(out)

    if _ENGINE_ERROR_RE.search(err):
        return Check(name, FAIL, "engine errors on stderr", shown, out, err)
    if rc != 0:
        # A suite that exits non-zero without a summary marker still names its failures on
        # stdout (`SMOKE FAIL: ...`); quoting the first one beats printing "exit 1".
        first = next((ln.strip() for ln in out.splitlines() if "FAIL" in ln), "")
        detail = any_marker.group(0).strip() if any_marker else first
        return Check(name, FAIL, f"exit {rc}" + (f" ({detail})" if detail else ""), shown, out, err)
    if not passed:
        if any_marker:
            return Check(name, FAIL, any_marker.group(0).strip(), shown, out, err)
        return Check(name, FAIL, "exited 0 but printed no PASS marker "
                                 "(expected a line like 'SMOKE: ALL PASS')", shown, out, err)
    if err_lines:
        return Check(name, SUSPECT, f"{passed.group(0).strip()}, but {len(err_lines)} "
                                    f"line(s) on stderr", shown, out, err)
    return Check(name, PASS, passed.group(0).strip(), shown, out, err)


# ------------------------------------------------------------------------- godot lanes

class ImportedProject:
    """Proof that `godot --headless --path <p> --import` has run against this project.

    Only `godot_import` constructs one, and `run_godot_script` will not accept anything
    else, so "forgot the import pass" is not a state this module can be in. The class
    cache is re-checked on every use because .godot/ can be deleted between calls.
    """

    def __init__(self, godot: str, path: Path, classes: list[str]) -> None:
        self.godot, self.path, self.classes = godot, path, classes

    @property
    def class_cache(self) -> Path:
        return self.path / ".godot" / "global_script_class_cache.cfg"


def godot_import(godot: str, project: Path) -> tuple[Check, ImportedProject | None]:
    """The import pass, verified rather than merely executed.

    Every `class_name` declared under the project must come back in the cache. Godot
    exits 0 from an import that registered nothing, and an empty cache is exactly the
    state that produces the "Could not find type" cascade one command later.
    """
    cmd = [godot, "--headless", "--path", str(project), "--import"]
    rc, out, err = run(cmd)
    # Drop the `[  16% ] first_scan_filesystem | ...` progress spam: twenty lines of it per
    # run buries the two that matter, in --verbose and in --json alike.
    out = "\n".join(ln for ln in out.splitlines() if not re.match(r"^\[\s*(\d+%|DONE)\s*\]", ln))
    cache = project / ".godot" / "global_script_class_cache.cfg"
    if rc != 0 or not cache.is_file():
        return Check("godot --import", FAIL,
                     f"exit {rc}, class cache {'present' if cache.is_file() else 'ABSENT'}",
                     " ".join(cmd), out, err), None

    registered = set(_CACHE_CLASS_RE.findall(cache.read_text(encoding="utf-8")))
    declared: set[str] = set()
    for gd in project.rglob("*.gd"):
        declared.update(_CLASS_NAME_RE.findall(gd.read_text(encoding="utf-8", errors="replace")))
    missing = sorted(declared - registered)
    if missing:
        return Check("godot --import", FAIL,
                     f"class cache is missing {', '.join(missing)} - every test below would "
                     f"fail with 'Could not find type'", " ".join(cmd), out, err), None

    names = ", ".join(sorted(registered)) or "(none declared)"
    return (Check("godot --import", PASS, f"{len(registered)} global class(es) registered: {names}",
                  " ".join(cmd), out, err),
            ImportedProject(godot, project, sorted(registered)))


def run_godot_script(imported: ImportedProject, script: str) -> Check:
    """Run one res:// test. Takes an ImportedProject, so the import cannot have been skipped."""
    if not isinstance(imported, ImportedProject):  # pragma: no cover - the guarantee, stated
        raise TypeError("run_godot_script needs an ImportedProject from godot_import()")
    if not imported.class_cache.is_file():
        return Check(script, FAIL,
                     "the global class cache vanished after the import pass - refusing to run, "
                     "the result would be a parse-error cascade in files nobody touched",
                     "", "", "")
    cmd = [imported.godot, "--headless", "--path", str(imported.path), "--script", f"res://{script}"]
    rc, out, err = run(cmd)
    return judge(script, cmd, rc, out, err)


def write_project(project: Path, godot: str | None) -> None:
    """The minimal project.godot the scaffolders demand and never create themselves.

    They check for `project.godot` and exit if it is absent, so every hand-rolled run of
    this loop starts with someone writing this file. `config/features` is stamped with the
    engine actually on PATH: an older minor there makes 4.x offer to convert the project.
    """
    ver = "4.4"
    if godot:
        rc, out, _ = run([godot, "--version"], timeout=60)
        m = re.search(r"(\d+\.\d+)", out)
        if rc == 0 and m:
            ver = m.group(1)
    project.mkdir(parents=True, exist_ok=True)
    (project / "project.godot").write_bytes(PROJECT_GODOT.format(ver=ver).encode("utf-8"))


# ------------------------------------------------------------------------------ the run

class Runner:
    def __init__(self, disc: Discovery, work: Path, godot: str | None, palette: str | None) -> None:
        self.d, self.work, self.godot, self.palette = disc, work, godot, palette
        self.project = work / disc.name
        self.prepared = False

    def prepare(self) -> list[Check]:
        """Build the throwaway project and get the skill's .gd into it."""
        checks: list[Check] = []
        write_project(self.project, self.godot)
        mode, sources = self.d.how_gd_gets_in()
        if mode == "scaffold":
            cmd = [sys.executable, str(sources[0]), str(self.project)]
            if self.palette:
                cmd += ["--palette", self.palette]
            rc, out, err = run(cmd)
            if rc != 0:
                checks.append(Check(sources[0].name, FAIL, f"scaffolder exited {rc}",
                                    " ".join(cmd), out, err))
                return checks
            checks.append(Check(sources[0].name, PASS,
                                f"scaffolded into {self.project.name}/", " ".join(cmd), out, err))
        else:
            for src in sources:
                shutil.copyfile(src, self.project / src.name)
            checks.append(Check("copy scripts/*.gd", PASS,
                                f"{', '.join(p.name for p in sources)} -> project root"))
        for test in self.d.gd_tests:
            shutil.copyfile(test, self.project / test.name)
        self.prepared = True
        return checks

    def godot_lane(self) -> list[Check]:
        if not self.d.gd_tests:
            return []
        if not self.godot:
            return [Check(t.name, SKIP, "no usable godot binary") for t in self.d.gd_tests]
        checks = self.prepare() if not self.prepared else []
        if any(c.status == FAIL for c in checks):
            return checks
        imp_check, imported = godot_import(self.godot, self.project)
        checks.append(imp_check)
        if imported is None:
            return checks
        for test in self.d.gd_tests:
            checks.append(run_godot_script(imported, test.name))
        return checks

    def python_lane(self) -> list[Check]:
        checks = []
        for script in self.d.py_tests:
            cmd = [sys.executable, str(script)]
            rc, out, err = run(cmd)
            checks.append(judge(script.name, cmd, rc, out, err))
        return checks

    def palette_lane(self) -> list[Check]:
        """Templates always; the scaffolded copy too, which is where a project's own
        screens would be. CLAUDE.md asks for both and they are not the same check - the
        scaffolded one has had a palette substituted into it."""
        if not self.d.palette_lint:
            return []
        checks = []
        for label, args in self._palette_targets():
            cmd = [sys.executable, str(self.d.palette_lint)] + args
            rc, out, err = run(cmd)
            c = judge(f"palette_lint ({label})", cmd, rc, out, err)
            checks.append(c)
        return checks

    def _palette_targets(self) -> list[tuple[str, list[str]]]:
        targets = [("templates", [])]
        ui = self.project / "scripts" / "ui"
        if self.prepared and (ui / "ui_theme.gd").is_file():
            targets.append(("scaffolded scripts/ui", [str(ui)]))
        return targets


def verify(disc: Discovery, work: Path, godot: str | None, palette: str | None) -> tuple[Runner, list[Check]]:
    r = Runner(disc, work, godot, palette)
    checks = r.python_lane()
    checks += r.godot_lane()          # prepares the project, so it runs before the lint
    checks += r.palette_lane()
    return r, checks


# ------------------------------------------------------------------------------- mutate

def mutate_proof(r: Runner, relpath: str, find: str, replace: str) -> tuple[list[Check], list[Check], str]:
    """Patch the scaffolded copy, require RED, restore, require GREEN.

    The half of the CLAUDE.md convention that gets skipped under time pressure: "a new
    assertion is not done until it has been shown to FAIL against the defect it describes".
    Nothing here touches the repo - `target` is inside the throwaway project by
    construction, and the original bytes are held in memory for the restore.
    """
    target = (r.project / relpath).resolve()
    if not str(target).startswith(str(r.project.resolve())):
        raise ValueError(f"--mutate path escapes the throwaway project: {relpath}")
    if not target.is_file():
        raise ValueError(f"--mutate target not found in the scaffolded project: {relpath}\n"
                         f"       it is relative to the project root, e.g. scripts/ui/hud.gd")
    original = target.read_bytes()
    text = original.decode("utf-8")
    if find not in text:
        raise ValueError(f"--mutate found no {find!r} in {relpath} - the patch would be a no-op, "
                         f"and a no-op that 'goes red' would be proving nothing")
    target.write_bytes(text.replace(find, replace).encode("utf-8"))
    try:
        red = r.godot_lane() + r.palette_lane()
    finally:
        target.write_bytes(original)
    green = r.godot_lane() + r.palette_lane()
    return red, green, f"{relpath}: {find!r} -> {replace!r}"


# -------------------------------------------------------------------------------- print

def print_checks(checks: list[Check], verbose: bool) -> None:
    width = max((len(c.name) for c in checks), default=0)
    for c in checks:
        print(f"  {c.status:<8} {c.name:<{width}}  {c.summary}")
    for c in checks:
        if c.status == PASS and not verbose:
            continue
        if c.status == SKIP:
            continue
        body = "\n".join(x for x in (c.stdout.rstrip(), c.stderr.rstrip()) if x.strip())
        if not body:
            continue
        print(f"\n  --- {c.name} ---")
        if c.command:
            print(f"  $ {c.command}")
        for line in body.splitlines():
            print(f"  | {line}")
    if any(c.status != PASS for c in checks) or verbose:
        print()


def tally(checks: list[Check]) -> dict[str, int]:
    out = {PASS: 0, FAIL: 0, SUSPECT: 0, SKIP: 0}
    for c in checks:
        out[c.status] = out.get(c.status, 0) + 1
    return out


def summarise(name: str, checks: list[Check]) -> str:
    t = tally(checks)
    bits = [f"{t[PASS]} passed"]
    for k, label in ((FAIL, "failed"), (SUSPECT, "suspect"), (SKIP, "skipped")):
        if t[k]:
            bits.append(f"{t[k]} {label}")
    return f"VERIFY {name}: " + ", ".join(bits)


# --------------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill", nargs="?", help="skill directory name under skills/")
    ap.add_argument("--all", action="store_true", help="every skill that ships something to verify")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--keep", action="store_true", help="keep the throwaway project and print its path")
    ap.add_argument("--work-dir", type=Path, help="build the throwaway project here (implies --keep)")
    ap.add_argument("--godot", default=os.environ.get("GODOT"),
                    help="godot binary (default: godot on PATH, or $GODOT)")
    ap.add_argument("--require-godot", action="store_true",
                    help="exit 2 instead of skipping when godot is not on PATH")
    ap.add_argument("--palette", help="pass --palette to the scaffolder (checks a re-skin too)")
    ap.add_argument("--strict", action="store_true", help="treat SUSPECT (stderr noise) as failure")
    ap.add_argument("--verbose", action="store_true", help="print output of passing checks too")
    ap.add_argument("--mutate", nargs=3, metavar=("RELPATH", "FIND", "REPLACE"),
                    help="patch the scaffolded copy and require the suite to go RED, "
                         "then restore and require GREEN. Exit 0 = the patch was caught.")
    args = ap.parse_args()

    godot = find_godot(args.godot)
    if not godot:
        where = f"{args.godot!r} does not run as Godot" if args.godot else "godot is not on PATH"
        if args.require_godot:
            print(f"error: {where} and --require-godot was given.", file=sys.stderr)
            return 2
        print(f"note: {where} - Godot lanes will be SKIPped, Python lanes still run.\n"
              f"      Point at a binary with --godot or $GODOT to run them.", file=sys.stderr)

    if args.all and args.skill:
        ap.error("give a skill name or --all, not both")
    if not args.all and not args.skill:
        print("usage: verify_skill.py <skill-name> [options]   (or --all)\n")
        print("Skills in this repo and what each ships to verify:\n")
        for name in all_skills():
            d = Discovery(name)
            bits = [p.name for p in d.py_tests] + [p.name for p in d.gd_tests]
            if d.palette_lint:
                bits.append("palette_lint.py")
            print(f"  {name:<26} {', '.join(bits) if bits else '(nothing to verify)'}")
        return 2
    if args.mutate and (args.all or not args.skill):
        ap.error("--mutate needs exactly one skill")

    names = all_skills() if args.all else [args.skill]
    discoveries: list[Discovery] = []
    for name in names:
        try:
            discoveries.append(Discovery(name))
        except LookupError:
            print(f"error: no skill {name!r} in {SKILLS}\n"
                  f"       known: {', '.join(all_skills())}", file=sys.stderr)
            return 2

    work_root = args.work_dir.resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix="verify_skill_"))
    work_root.mkdir(parents=True, exist_ok=True)
    keep = args.keep or bool(args.work_dir)
    report: list[dict] = []
    worst = 0

    try:
        for d in discoveries:
            if d.empty:
                if args.all:
                    continue
                if args.json:
                    report.append({"skill": d.name, "checks": [], "nothing_to_verify": True,
                                   "exit": 0})
                else:
                    print(f"VERIFY {d.name}: nothing to verify - this skill ships no "
                          f"assets/*_test.gd, no scripts/*test*.py and no palette_lint.py.")
                    print("       (a probe-only skill; its scripts are exercised by hand "
                          "against real asset kits)")
                return 0

            try:
                r, checks = verify(d, work_root, godot, args.palette)
            except ValueError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2

            if args.mutate:
                try:
                    red, green, what = mutate_proof(r, *args.mutate)
                except ValueError as exc:
                    print(f"error: {exc}", file=sys.stderr)
                    return 2
                red_states = {FAIL, SUSPECT} if args.strict else {FAIL}
                caught = [c for c in red if c.status in red_states]
                still_green = [c for c in green if c.status in red_states]
                if not args.json:
                    print(f"BASELINE {d.name}")
                    print_checks(checks, args.verbose)
                    print(f"MUTATED  {what}")
                    print_checks(red, args.verbose)
                    print("RESTORED")
                    print_checks(green, args.verbose)
                    if caught and not still_green:
                        print(f"MUTATE: caught by {len(caught)} check(s): "
                              f"{', '.join(c.name for c in caught)}")
                        print("        the patch went red and the restore went green again - "
                              "the assertion is load-bearing.")
                    elif still_green:
                        print("MUTATE: the suite did not recover after the restore - the run is "
                              "not trustworthy, investigate before believing either half.")
                    else:
                        print("MUTATE: NOT CAUGHT. Every check stayed green under the patch, so "
                              "nothing here asserts on it.")
                else:
                    report.append({"skill": d.name, "mode": "mutate", "mutation": what,
                                   "baseline": [c.as_dict() for c in checks],
                                   "mutated": [c.as_dict() for c in red],
                                   "restored": [c.as_dict() for c in green],
                                   "caught_by": [c.name for c in caught],
                                   "recovered": not still_green})
                rc = 0 if (caught and not still_green) else 1
                if args.json:
                    print(json.dumps({"skills": report, "work_dir": str(work_root), "exit": rc},
                                     indent=2))
                return rc

            t = tally(checks)
            bad = t[FAIL] + (t[SUSPECT] if args.strict else 0)
            worst = max(worst, 1 if bad else 0)
            if args.json:
                report.append({"skill": d.name, "checks": [c.as_dict() for c in checks],
                               "tally": t, "exit": 1 if bad else 0})
            else:
                print(f"VERIFYING {d.name}  ({d.dir.relative_to(REPO).as_posix()})")
                print_checks(checks, args.verbose)
                print(summarise(d.name, checks))
                if t[SUSPECT]:
                    print("         SUSPECT = the marker said pass but the engine wrote to "
                          "stderr. Read it above; --strict makes it a failure.")
                if t[PASS] == 0 and t[SKIP]:
                    # Exit 0 on a run where nothing executed is the one way this tool could
                    # manufacture confidence, so it says so out loud.
                    print("         NOTHING ACTUALLY RAN - this is not a green result. "
                          "Use --require-godot to make it exit 2.")
                if len(discoveries) > 1:
                    print()

        if args.json:
            print(json.dumps({"skills": report, "work_dir": str(work_root), "exit": worst}, indent=2))
    finally:
        if keep:
            print(f"kept: {work_root}", file=sys.stderr)
        else:
            shutil.rmtree(work_root, ignore_errors=True)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
