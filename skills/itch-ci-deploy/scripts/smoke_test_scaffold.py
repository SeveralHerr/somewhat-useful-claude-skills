#!/usr/bin/env python3
"""Prove scaffold_itch_deploy.py can both write and FAIL. Builds a throwaway Godot-shaped
project in a temp dir and drives the scaffolder through the cases a first CI run breaks
on. Prints SMOKE: ALL PASS and exits 0, or the first failing case and exits 1.

    python scripts/smoke_test_scaffold.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAFFOLD = HERE / "scaffold_itch_deploy.py"

PROJECT_GODOT = """config_version=5

[application]

config/name="Probe"
config/features=PackedStringArray("4.7", "Forward Plus")
"""


def run(project, *args):
    p = subprocess.run([sys.executable, str(SCAFFOLD), str(project), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def main():
    fails = []

    def check(name, cond, out=""):
        print(("  PASS  " if cond else "  FAIL  ") + name)
        if not cond:
            fails.append((name, out))

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "probe"
        proj.mkdir()
        (proj / "project.godot").write_text(PROJECT_GODOT, encoding="utf-8")
        (proj / ".gitignore").write_text(".godot/\nbin/\n", encoding="utf-8")

        rc, out = run(proj, "--check")
        check("--check on a bare project exits 1 (no preset, no workflow)", rc == 1 and "no export_presets.cfg" in out, out)
        check("--check writes nothing", not (proj / "export_presets.cfg").exists(), out)

        rc, out = run(proj, "--target", "someone/probe:html5")
        wf = proj / ".github" / "workflows" / "deploy-to-itchio.yml"
        check("write run exits 0", rc == 0, out)
        check("workflow written", wf.is_file(), out)
        check("preset written", (proj / "export_presets.cfg").is_file(), out)
        body = wf.read_text(encoding="utf-8") if wf.is_file() else ""
        check("no placeholders left (GitHub ${{ }} expressions are not placeholders)", not re.search(r"\{\{[A-Z_]+\}\}", body), body)
        check("version substituted from config/features", "GODOT_VERSION: 4.7-stable" in body and "GODOT_TEMPLATE_DIR: 4.7.stable" in body, body)
        check("target substituted", "ITCH_TARGET: someone/probe:html5" in body, body)
        preset = (proj / "export_presets.cfg").read_text(encoding="utf-8")
        check("preset has thread_support=false", "variant/thread_support=false" in preset, preset)

        rc, out = run(proj, "--check")
        check("--check on the written setup exits 0", rc == 0, out)

        rc, out = run(proj, "--target", "someone/probe:html5")
        check("re-run without --force refuses", rc == 1 and "--force" in out, out)

        # Mutate: the itch-breaking setting. The check must go red.
        (proj / "export_presets.cfg").write_text(preset.replace("thread_support=false", "thread_support=true"), encoding="utf-8")
        rc, out = run(proj, "--check")
        check("thread_support=true is a FAIL", rc == 1 and "thread_support=true" in out, out)
        (proj / "export_presets.cfg").write_text(preset, encoding="utf-8")

        # Mutate: workflow pinned to a different engine than the project.
        wf.write_text(body.replace("GODOT_VERSION: 4.7-stable", "GODOT_VERSION: 4.6-stable"), encoding="utf-8")
        rc, out = run(proj, "--check")
        check("workflow/project version mismatch is a FAIL", rc == 1 and "pins GODOT_VERSION" in out, out)
        wf.write_text(body, encoding="utf-8")

        # Mutate: preset file ignored by git.
        (proj / ".gitignore").write_text(".godot/\nbin/\nexport_presets.cfg\n", encoding="utf-8")
        rc, out = run(proj, "--check")
        check("gitignored export_presets.cfg is a FAIL", rc == 1 and "ignores export_presets.cfg" in out, out)
        (proj / ".gitignore").write_text(".godot/\nbin/\n", encoding="utf-8")

        rc, out = run(proj, "--target", "Someone/Probe:html5", "--force")
        check("uppercase target is a FAIL", rc == 1 and "user/game:channel" in out, out)

        rc, out = run(Path(td), "--check")
        check("not a Godot project exits 2", rc == 2, out)

    # --- the guessed-slug WARN -----------------------------------------------------
    # The defect: a slug copied off the repo folder when the game is called something
    # else - `plant-tower-defense/pest-control` in the report, which failed only at the
    # butler step with `/wharf/builds: invalid game`. Everything below that is a
    # legitimate slug and must stay silent, because a warning that fires on correct
    # input gets ignored on the one run where it was right.
    def slug_case(name, dirname, project_godot, target, expect_warn):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / dirname
            proj.mkdir()
            data = project_godot if isinstance(project_godot, bytes) else project_godot.encode("utf-8")
            (proj / "project.godot").write_bytes(data)
            (proj / ".gitignore").write_text(".godot/\nbin/\n", encoding="utf-8")
            rc, out = run(proj, "--target", target, "--check")
            warned = "is the project folder's name" in out
            check(name, warned == expect_warn and rc in (0, 1) and "Traceback" not in out, out)

    named = 'config_version=5\n\n[application]\n\nconfig/name="Pest Control"\nconfig/features=PackedStringArray("4.7")\n'
    same = 'config_version=5\n\n[application]\n\nconfig/name="Plant Tower Defense"\nconfig/features=PackedStringArray("4.7")\n'
    nameless = 'config_version=5\n\n[application]\n\nconfig/features=PackedStringArray("4.7")\n'
    localized = ('config_version=5\n\n[application]\n\n'
                 'config/name_localized={\n"en": "Pest Control"\n}\n'
                 'config/features=PackedStringArray("4.7")\n')

    slug_case("guessed slug (== dir, != slugified title) WARNs",
              "plant-tower-defense", named, "someone/plant-tower-defense:html5", True)
    slug_case("slug matching the slugified title is silent",
              "plant-tower-defense", named, "someone/pest-control:html5", False)
    slug_case("slug matching BOTH dir and slugified title is silent",
              "pest-control", named, "someone/pest-control:html5", False)
    slug_case("slug matching a slugified title with punctuation is silent",
              "repo-dir", 'config_version=5\n\n[application]\n\nconfig/name="Pest  Control!"\n'
              'config/features=PackedStringArray("4.7")\n', "someone/pest-control:html5", False)
    slug_case("slug == dir and title slugifies to the dir name is silent",
              "plant-tower-defense", same, "someone/plant-tower-defense:html5", False)
    slug_case("dir name in Title Case still matches its own slug (silent)",
              "Plant Tower Defense", same, "someone/plant-tower-defense:html5", False)
    slug_case("no config/name is silent",
              "plant-tower-defense", nameless, "someone/plant-tower-defense:html5", False)
    slug_case("empty config/name is silent",
              "plant-tower-defense",
              'config_version=5\n\n[application]\n\nconfig/name=""\nconfig/features=PackedStringArray("4.7")\n',
              "someone/plant-tower-defense:html5", False)
    slug_case("config/name_localized is not a title (silent)",
              "plant-tower-defense", localized, "someone/plant-tower-defense:html5", False)
    slug_case("a slug that is neither the dir nor the title is silent",
              "plant-tower-defense", named, "someone/pc-jam-build:html5", False)
    slug_case("a malformed target is a FAIL, not a slug WARN",
              "plant-tower-defense", named, "someone/Plant-Tower-Defense:html5", False)
    slug_case("an unreadable project.godot is silent, not a crash",
              "plant-tower-defense", b"\x00\xff\xfe binary junk, no [application]\x00",
              "someone/plant-tower-defense:html5", False)

    # And the WARN must not change the exit code: same project, same target, only the
    # title differs, so any exit-code difference is the warning leaking into `findings`.
    with tempfile.TemporaryDirectory() as td:
        codes = {}
        for tag, pg in (("warn", named), ("quiet", same)):
            proj = Path(td) / tag / "plant-tower-defense"
            proj.mkdir(parents=True)
            (proj / "project.godot").write_text(pg, encoding="utf-8")
            (proj / ".gitignore").write_text(".godot/\nbin/\n", encoding="utf-8")
            rc, out = run(proj, "--target", "someone/plant-tower-defense:html5")
            codes[tag] = (rc, (proj / ".github" / "workflows" / "deploy-to-itchio.yml").is_file(), out)
        check("the WARN does not change the exit code",
              codes["warn"][0] == codes["quiet"][0] == 0, codes["warn"][2])
        check("the WARN does not block scaffolding",
              codes["warn"][1] and "WARN  game slug" in codes["warn"][2], codes["warn"][2])

    if fails:
        name, out = fails[0]
        print(f"\nSMOKE: {len(fails)} FAILED; first: {name}\n{out}")
        return 1
    print("\nSMOKE: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
