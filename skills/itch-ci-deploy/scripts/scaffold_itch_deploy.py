#!/usr/bin/env python3
"""Install (or audit) a GitHub Actions workflow that exports a Godot 4 Web build and
pushes it to itch.io with butler on every push to a branch.

    scaffold_itch_deploy.py <godot project> --target user/game:html5 [options]
    scaffold_itch_deploy.py <godot project> --check

The workflow itself is a template (../assets/deploy-to-itchio.yml) with a handful of
placeholders. Everything this script does beyond substitution is *measurement* of the
project the workflow is about to run against, because each of these is a way the first
CI run fails after eight minutes of downloading templates:

  - the Godot version. Read from `config/features` in project.godot, not typed, so the
    editor that wrote the project is the one that exports it. A minor-version mismatch
    exports a build against the wrong templates.
  - the export preset. Godot's headless `--export-release "Web"` needs a preset by that
    exact name in export_presets.cfg; with none, the export prints an error and exits 0.
    A missing preset is written from a known-good template (unless --no-write-preset)
    with `variant/thread_support=false` - itch.io does not serve the cross-origin
    isolation headers a threaded build needs, so a threaded export shows a black canvas
    and a SharedArrayBuffer error in the console.
  - export_presets.cfg's own tracked-ness. If it is gitignored, CI never sees the preset.
  - the export directory. Godot refuses to export into a directory that does not exist,
    and the natural `bin/` is gitignored, so the workflow mkdirs it - but only the one it
    was told about, hence reading `export_path` from the preset rather than assuming.
  - the renderer. Web builds run only on the Compatibility renderer;
    `rendering/renderer/rendering_method.web` defaults to gl_compatibility and is checked
    in case someone overrode it.

Exit 0 = wrote (or --check found nothing wrong); 1 = a finding that would break the
first run; 2 = could not run (not a Godot project, template missing). It prints what it
checked either way, so a clean exit is a list of claims and not a blank.
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "deploy-to-itchio.yml"

WEB_PRESET = """
[preset.{n}]

name="{name}"
platform="Web"
runnable=true
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="{export_path}"
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.{n}.options]

custom_template/debug=""
custom_template/release=""
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/export_icon=true
html/custom_html_shell=""
html/head_include=""
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
html/experimental_virtual_keyboard=false
progressive_web_app/enabled=false
progressive_web_app/ensure_cross_origin_isolation_headers=true
progressive_web_app/offline_page=""
progressive_web_app/display=1
progressive_web_app/orientation=0
progressive_web_app/icon_144x144=""
progressive_web_app/icon_180x180=""
progressive_web_app/icon_512x512=""
progressive_web_app/background_color=Color(0, 0, 0, 1)
"""


class Report:
    def __init__(self):
        self.lines = []
        self.findings = 0

    def ok(self, msg):
        self.lines.append(f"  OK    {msg}")

    def warn(self, msg):
        self.lines.append(f"  WARN  {msg}")

    def fail(self, msg):
        self.findings += 1
        self.lines.append(f"  FAIL  {msg}")

    def dump(self):
        print("\n".join(self.lines))


def godot_version_from_features(text: str):
    m = re.search(r'config/features=PackedStringArray\(([^)]*)\)', text)
    if not m:
        return None
    for tok in re.findall(r'"([^"]*)"', m.group(1)):
        if re.fullmatch(r"\d+\.\d+(\.\d+)?", tok):
            return tok
    return None


def parse_presets(text: str):
    """Return {index: {"name":..., "platform":..., "export_path":..., "options": {...}}}."""
    presets = {}
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.fullmatch(r"\[preset\.(\d+)(\.options)?\]", line)
        if m:
            idx = int(m.group(1))
            presets.setdefault(idx, {"options": {}})
            section = (idx, bool(m.group(2)))
            continue
        if section is None or "=" not in line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        val = val.strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        idx, is_opts = section
        if is_opts:
            presets[idx]["options"][key.strip()] = val
        else:
            presets[idx][key.strip()] = val
    return presets


def gitignore_ignores(project: Path, needle: str) -> bool:
    gi = project / ".gitignore"
    if not gi.is_file():
        return False
    for line in gi.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.lstrip("/").rstrip("/") == needle.rstrip("/"):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project", help="path to the Godot project (dir with project.godot)")
    ap.add_argument("--target", help="butler target, e.g. severalherr/gather:html5")
    ap.add_argument("--preset", default="Web", help="export preset name (default: Web)")
    ap.add_argument("--branch", default="main", help="branch whose pushes deploy (default: main)")
    ap.add_argument("--godot-version",
                    help="release tag, e.g. 4.7-stable (default: <config/features minor>-stable)")
    ap.add_argument("--export-path", default="bin/index.html",
                    help="export_path used if the preset has to be written (default: bin/index.html)")
    ap.add_argument("--no-write-preset", action="store_true",
                    help="do not add a Web preset when none exists; report it instead")
    ap.add_argument("--check", action="store_true",
                    help="audit only; write nothing (also what a --target-less run does)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing workflow file")
    args = ap.parse_args()

    project = Path(args.project).resolve()
    rep = Report()

    pg = project / "project.godot"
    if not pg.is_file():
        print(f"ERROR: {project} has no project.godot", file=sys.stderr)
        return 2
    if not TEMPLATE.is_file():
        print(f"ERROR: template missing at {TEMPLATE}", file=sys.stderr)
        return 2
    text = pg.read_text(encoding="utf-8", errors="replace")

    check_only = args.check or not args.target
    if not args.target and not args.check:
        rep.warn("no --target given; running as --check (nothing will be written)")

    # --- Godot version ---------------------------------------------------------
    feat = godot_version_from_features(text)
    if args.godot_version:
        version = args.godot_version
        rep.ok(f"Godot version {version} (from --godot-version; project features say {feat!r})")
    elif feat:
        version = f"{feat}-stable"
        rep.ok(f"Godot version {version} (from project.godot config/features={feat!r})")
    else:
        version = None
        rep.fail("could not read a Godot version from project.godot config/features; pass --godot-version")
    if version and not re.fullmatch(r"\d+\.\d+(\.\d+)?-(stable|rc\d+|beta\d+|dev\d+)", version):
        rep.fail(f"'{version}' does not look like a Godot release tag (expected e.g. 4.7-stable)")
    template_dir = version.replace("-", ".") if version else None

    # --- renderer ---------------------------------------------------------------
    m = re.search(r'renderer/rendering_method\.web="([^"]*)"', text)
    if m and m.group(1) != "gl_compatibility":
        rep.fail(f"rendering_method.web={m.group(1)!r}; Web export runs only on gl_compatibility")
    else:
        rep.ok("renderer: web builds use gl_compatibility (default or set)")

    # --- export preset ----------------------------------------------------------
    presets_path = project / "export_presets.cfg"
    presets = (parse_presets(presets_path.read_text(encoding="utf-8", errors="replace"))
               if presets_path.is_file() else {})
    match = [(i, p) for i, p in presets.items() if p.get("name") == args.preset]
    export_path = None
    wrote_preset = False
    if match:
        idx, p = match[0]
        export_path = p.get("export_path", "")
        if p.get("platform") != "Web":
            rep.fail(f"preset '{args.preset}' (preset.{idx}) is platform {p.get('platform')!r}, not Web")
        else:
            rep.ok(f"preset '{args.preset}' found (preset.{idx}), export_path={export_path!r}")
        ts = p["options"].get("variant/thread_support")
        if ts == "true":
            rep.fail(f"preset.{idx} has variant/thread_support=true; itch.io serves no COOP/COEP headers, "
                     "so the build will not start (black canvas, SharedArrayBuffer error). Set it false.")
        elif ts is None:
            rep.warn(f"preset.{idx} does not set variant/thread_support; Godot's default is false, "
                     "but write it explicitly so an editor click cannot flip it unnoticed")
        else:
            rep.ok(f"preset.{idx} variant/thread_support=false")
        if not export_path.endswith(".html"):
            rep.fail(f"preset.{idx} export_path {export_path!r} should end in index.html for a Web export")
    else:
        if presets_path.is_file():
            names = [p.get("name") for p in presets.values()]
            msg = f"no preset named '{args.preset}' in export_presets.cfg (have: {names})"
        else:
            msg = "no export_presets.cfg in the project"
        if check_only or args.no_write_preset:
            rep.fail(msg + " - the headless export will print an error and exit 0, producing nothing")
        else:
            n = (max(presets) + 1) if presets else 0
            block = WEB_PRESET.format(n=n, name=args.preset, export_path=args.export_path)
            existed = presets_path.is_file() and presets_path.stat().st_size > 0
            with presets_path.open("a", encoding="utf-8", newline="\n") as fh:
                if existed:
                    fh.write("\n")
                fh.write(block.lstrip("\n"))
            export_path = args.export_path
            wrote_preset = True
            rep.ok(f"{msg}; wrote preset.{n} '{args.preset}' -> {export_path} with thread_support=false")

    if gitignore_ignores(project, "export_presets.cfg"):
        rep.fail(".gitignore ignores export_presets.cfg - CI checks out no preset and the export cannot run")

    export_dir = str(Path(export_path).parent).replace("\\", "/") if export_path else "bin"
    if export_dir in ("", "."):
        rep.warn(f"export_path {export_path!r} is at the project root; the build would be pushed from '.', "
                 "which uploads the whole repo. Use a subdirectory like bin/index.html")
        export_dir = "."
    elif not gitignore_ignores(project, export_dir):
        rep.warn(f"'{export_dir}/' is not in .gitignore; export output will show up as untracked work")
    if not gitignore_ignores(project, ".godot"):
        rep.warn(".godot/ is not gitignored; the workflow's import cache still works, but the repo is "
                 "carrying editor state")

    # --- target -----------------------------------------------------------------
    if args.target:
        if re.fullmatch(r"[a-z0-9_-]+/[a-z0-9_-]+:[a-z0-9_-]+", args.target):
            rep.ok(f"butler target {args.target}")
        else:
            rep.fail(f"--target {args.target!r} must look like user/game:channel (lowercase itch slugs)")

    # --- workflow ---------------------------------------------------------------
    wf_path = project / ".github" / "workflows" / "deploy-to-itchio.yml"
    rel = wf_path.relative_to(project).as_posix()
    if wf_path.is_file():
        existing = wf_path.read_text(encoding="utf-8", errors="replace")
        rep.ok(f"existing workflow at {rel}")
        m = re.search(r"GODOT_VERSION:\s*(\S+)", existing)
        if m and version and m.group(1) != version:
            rep.fail(f"workflow pins GODOT_VERSION {m.group(1)} but the project is {version}")
        if not check_only and not args.force:
            rep.fail("workflow already exists; pass --force to overwrite it")
    elif check_only:
        rep.fail(f"no workflow at {rel}")

    rep.dump()
    if rep.findings or check_only:
        tail = " (the preset was written)" if wrote_preset else ""
        print(f"\n{'CHECK' if check_only else 'ABORTED'}: {rep.findings} finding(s), no workflow written{tail}")
        return 1 if rep.findings else 0

    body = TEMPLATE.read_text(encoding="utf-8")
    subs = {
        "{{BRANCH}}": args.branch,
        "{{GODOT_VERSION}}": version,
        "{{GODOT_TEMPLATE_DIR}}": template_dir,
        "{{PRESET}}": args.preset,
        "{{EXPORT_PATH}}": export_path,
        "{{EXPORT_DIR}}": export_dir,
        "{{ITCH_TARGET}}": args.target,
    }
    for k, v in subs.items():
        body = body.replace(k, v)
    left = re.findall(r"\{\{[A-Z_]+\}\}", body)
    if left:
        print(f"ERROR: unsubstituted placeholders in template: {left}", file=sys.stderr)
        return 2
    wf_path.parent.mkdir(parents=True, exist_ok=True)
    wf_path.write_bytes(body.encode("utf-8"))
    user, _, rest = args.target.partition("/")
    game, _, channel = rest.partition(":")
    print(f"\nWROTE {rel}")
    print(f"""
One-time setup that no workflow can do for you:
  1. Repository secret BUTLER_API_KEY  (GitHub: Settings -> Secrets and variables -> Actions)
     Generate it at https://itch.io/user/settings/api-keys, then:
       gh secret set BUTLER_API_KEY --repo <owner/repo>
  2. The itch.io project must already exist at https://{user}.itch.io/{game}
     (butler creates the '{channel}' channel on the first push, never the game).
  3. After the first successful push, on the itch.io Edit game page set Kind of project
     = HTML and tick "This file will be played in the browser" on the {channel} upload.
     butler cannot set either; the build is invisible to players until you do.
  4. Commit export_presets.cfg and {rel}, push to {args.branch}, watch the Actions tab.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
