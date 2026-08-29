# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A content repository, not an application: sixteen Claude Code skills for indie game development
(Godot 4 UI, itch.io publishing and CI deploy, Kenney assets, Blender asset authoring, seeded game design, and a
self-improvement loop), packaged as one installable plugin. There is nothing to build, no dependency
manifest, and no test runner. The deliverable is Markdown plus a handful of standalone scripts.

## Commands

The scripts are the only executable surface. All are stdlib-only except `store_art.py` (Pillow).

```bash
python skills/game-from-gibberish/scripts/seed.py --seed 41521    # deterministic; use to verify axes.md edits
python skills/kenney-asset-kit/scripts/kenney_probe.py "<kit dir>" [--json]
python skills/kenney-asset-kit/scripts/kenney_probe2d.py "<2D pack dir>" [--check FILE] [--json]
python skills/blender-mcp-modelling/scripts/style_probe.py "<ref dir>" [--check FILE] [--json]
python skills/godot-game-ui/scripts/scaffold_ui.py <godot project> [--only theme,hud] [--dest ui] [--force]
python skills/godot-game-ui/scripts/palette_lint.py [<dir with ui_theme.gd>] [--contrast-table] [--json]
python skills/skill-feedback-issue/scripts/resolve_skill.py <skill> [--ran-from <dir>] [--json]
python skills/godot-game-ui-juicy/scripts/scaffold_juicy_ui.py <godot project>
python skills/itch-store-page/scripts/store_art.py palette|cover|banner --src shot.png
python skills/itch-ci-deploy/scripts/scaffold_itch_deploy.py <godot project> --target user/game:html5 [--check]
python skills/itch-ci-deploy/scripts/smoke_test_scaffold.py                     # SMOKE: ALL PASS; proves the checks can fail
```

`tools/` is repo maintenance — the only scripts here that do **not** ship to a user:

```bash
python tools/verify_skill.py <skill> [--all] [--json] [--keep] [--strict]   # every test that skill ships
python tools/verify_skill.py <skill> --mutate <file> <find> <replace>       # prove an assertion can fail
python tools/lint_markdown.py [<file.md>|<dir>] [--json]   # default: skills/*/SKILL.md + root *.md
python tools/release_check.py [--release] [--baseline VERSION] [--json]
python tools/smoke_test_tools.py                           # SMOKE: ALL PASS; proves both checks can fail
```

`lint_markdown.py` exits 1 on Markdown that renders as something other than what it says — a
bold paragraph swallowed by the bullet above it, an unclosed fence, a heading with no blank
line over it. SKILL.md *is* the product, so a rendering bug is a defect in the deliverable.
Its lazy-continuation rule is deliberately narrow: indentation cannot separate the bug from a
wrapped bullet line, since both sit at column 0, so it fires only on block-shaped leads
CommonMark cannot start mid-paragraph (`**strong**`, a table row, a link reference definition).
Wrapped prose is exempt *by rule*, which is why there is no ignore pragma — and why a plain
prose paragraph glued to a bullet is a documented miss rather than an oversight.

`release_check.py` exits 1 when the hand-synced descriptions and keywords in `plugin.json` and
`marketplace.json` have drifted, a `SKILL.md`'s frontmatter is not exactly `name` + `description`
with `name` equal to its directory, or a skill is missing from README.md's table — and exits
**2**, distinctly, when everything agrees but `--release` was passed and the version was not
bumped past HEAD's. The default mode treats an unbumped version as a note, because a check that
reddens on every non-release day gets switched off.

Verifying a change to the Godot templates requires a real Godot 4 project — the templates are
`.gd` files this repo never compiles:

```bash
python skills/godot-game-ui/scripts/scaffold_ui.py /tmp/probe-project
godot --headless --path /tmp/probe-project --import          # rebuilds the global class cache
cp skills/godot-game-ui/assets/smoke_test.gd /tmp/probe-project/
godot --headless --path /tmp/probe-project --script res://smoke_test.gd   # prints SMOKE: ALL PASS
```

`godot-game-ui-juicy` additionally ships `assets/juice_test.gd`, run the same way. Skipping the
`--import` pass is the usual cause of a parse-error cascade in files nobody touched.

**`tools/verify_skill.py` is that whole loop**, and is what you should actually run — it writes
the minimal `project.godot` the scaffolders require but never create, always imports, then runs
every `assets/*_test.gd` plus `palette_lint.py` over both the templates and the scaffolded
`scripts/ui`. It judges a run on its marker line *and* its exit code *and* its stderr, because
none of the three is sufficient alone. The import is a type rather than a step: `run_godot_script`
takes an `ImportedProject` that only `godot_import` can construct, so the "Could not find type
GameHud" cascade is unreachable rather than merely discouraged. The block above is kept because
it is what the tool does, and you will need it the day the tool is what is broken.

```bash
python tools/verify_skill.py godot-game-ui-juicy   # SMOKE / JUICE / PALETTE, one command
python tools/verify_skill.py --all                 # the shared-file check: both UI kits at once
```

The other half of the convention below — an assertion is not done until it has been shown to FAIL
— is `--mutate`, which patches the *scaffolded* copy, requires the suite to go red, restores, and
requires green again. Its exit code answers "can this assertion fail?": 0 = caught, 1 = the suite
stayed green and the assertion is decorative.

`godot-2d-placement-audit` is checked the same way and needs no scaffolder — copy both files into
any Godot 4 project and run the test, which prints `SMOKE: ALL PASS` and exits 0:

```bash
cp skills/godot-2d-placement-audit/scripts/placement_audit_2d.gd /tmp/probe-project/
cp skills/godot-2d-placement-audit/assets/smoke_test.gd /tmp/probe-project/
godot --headless --path /tmp/probe-project --import
godot --headless --path /tmp/probe-project --script res://smoke_test.gd
```

Read stderr on that run, not just the exit code. GDScript's `%` operator supports fewer specifiers
than C's — `%g` is not among them — and an unsupported one yields an empty string plus a stderr
line rather than an error, so a check keeps "passing" while reporting nothing. The smoke test
asserts every message is non-empty for that reason.

The exit code alone is not enough either, and this is not hypothetical: `juice_test.gd` used to
end by returning `true` from a `SceneTree`'s `_process`, which quits with 0 no matter what, so it
printed `JUICE: 1 FAILED` and still exited green. It calls `quit(0)`/`quit(1)` now, the way
`smoke_test.gd` always has — but any *new* test script inherits the trap, so make a new suite
prove it can exit non-zero before you trust it.

`skills/godot-game-ui/evals/evals.json` is a `skill-creator` eval set (`skill_name` + `evals[]`
of `prompt` / `expected_output` / `assertions`); run it through the `skill-creator` skill. It is
the only skill with evals — new eval sets should follow that file's shape.

## Architecture

**Plugin packaging.** `.claude-plugin/marketplace.json` declares the marketplace; it points at a
single plugin whose `source` is `./`, so `.claude-plugin/plugin.json` bundles *everything* under
`skills/`. Adding a skill is therefore just creating `skills/<name>/SKILL.md` — there is no
manifest listing skills and nothing to register. What does need touching on a release: `version`
in `plugin.json`, the description/keywords in both JSON files (kept in sync by hand), and the
table in `README.md`.

**Skill anatomy.** `SKILL.md` frontmatter is `name` + `description` only. The `description` is the
whole trigger surface — Claude matches against it to decide whether to load the skill — so it is
written as a long list of symptom phrases a user would actually type ("the lamp is floating", "the
menu just pops in"), not as a summary. Where two skills overlap, each description names the other
and says when to prefer it (`itch-devlog` ↔ `itch-store-page`, the two UI skills).

The body is progressive disclosure. `SKILL.md` holds the reasoning and the gotchas; the
subdirectories are pulled in only when needed:

- `scripts/` — run, not read. They exist to replace guessing with measurement: `kenney_probe.py`
  reads real glTF node transforms instead of trusting a remembered convention, `seed.py` rolls
  design constraints on dice because a model asked to "interpret" gibberish filters toward the
  ordinary. Preserve that property when editing them.
- `assets/templates/` — copied verbatim into a user's project by the scaffolders, then edited
  there. They are a starting point, not a library, and are commented with *why*.
- `references/` — read on demand while adapting.

**`palette_lint.py` is the only check that can see a hard-coded colour.** Against the shipped
palette, `Color(0.06, 0.05, 0.07, 1.0)` is *numerically identical* to the constant it should
have read, so a Godot test that walks the built tree reads the same `ColorRect.color` either
way and cannot distinguish "reads `UiTheme.BACKDROP`" from "retyped its value". The difference
exists only in the source, which is why this one is a Python lint and not an assertion in
`smoke_test.gd`. Three rules: no chromatic literal outside `ui_theme.gd`; no literal anywhere
repeating a palette constant's RGB; no chromatic literal in `ui_theme.gd` *below* the PALETTE
block, since `--palette` substitutes the sixteen constants and nothing else — that third rule
is the one that caught `style_button`, `slot_box` and `badge_box` keeping their fills as
literals, which put `clinical` at 1.41:1 text-on-button contrast. Achromatic literals
(`r == g == b`) are exempt by rule rather than by allowlist: a drop shadow, the white flash and
a luminance-picked ink stay correct under every palette. Run it over a scaffolded project's
`scripts/ui` too — the rules are the same there, which is what makes it a user tool rather than
a repo-only lint.

**It has a second arm: contrast.** Reachability and legibility are different failures — a
hand-written palette can route every colour through `ui_theme.gd` correctly and still be
unreadable — so `--contrast-table` measures sixteen ink/surface pairs and exits 1 under WCAG AA
(4.5, and 3.0 for the `TEXT_DIM`/`TEXT_FAINT` tiers the design deliberately whispers with; that
is why a fact must never appear *only* in those tiers). Two things make this measurable rather
than a matter of taste, and both had to be settled before the check could exist:

- **Composite, do not read `bg_color`.** The naive figure condemns five of six shipped palettes
  — amber's secondary button is 4.00 raw and 11.32 composited — and a check that fires on
  correct code is switched off within a week. Secondary buttons sit at 0.95 over a 0.88 panel
  over a 0.86 backdrop, so gameplay leakage into that pixel is 0.084%, below one 8-bit step.
  Where leakage is real (the HUD pill, 32%) the pair is evaluated over *both* black and white
  and judged on the worse end, which bounds it with no assumption about the game underneath.
- **Use the real sRGB transform.** The figures that opened this investigation were computed by
  weighting raw sRGB components as if already linear — `Color.get_luminance()`'s maths, not
  WCAG's piecewise one. Under the correct transform candy is 5.09, not 2.78. Exactly one of
  the original numbers survived: `bloodmoon`'s primary button really was broken at 3.47:1
  hover, because a saturated red takes neither black nor white ink, and its `ACCENT` was
  deepened to fix it.

Some things have no ratio at all — the crosshair ring and any bare `Glyph` draw straight onto
gameplay with no surface behind them. The kit answers those with geometry (outline, shadow, ring
thickness), and the SKILL.mds say so rather than implying the table covers everything.

**The two UI skills share files byte-for-byte.** `ui_theme.gd`, `ui_motion.gd`,
`smoke_test.gd` and `palette_lint.py` are identical copies in `godot-game-ui` and
`godot-game-ui-juicy`; `hud.gd`,
`pause_menu.gd`, `title_screen.gd` and `results_screen.gd` have diverged (juicy is the animated
superset, and adds `ui_juice.gd`). There is no shared source — a fix to a shared file must be
applied to both copies, and the two scaffolders' `PIECES` dependency tables kept parallel.

**`blender-mcp-modelling` pairs with `kenney-asset-kit`** — the same measurement idea pointed the
other way. `kenney_probe.py` measures a kit so you can *place* models from it; `style_probe.py`
measures a reference set so you can *author* a new model into it, and its `--check` mode re-derives
that contract to gate an export (exit 1 on a mismatch). `--check` deliberately excludes the
candidate from the reference scan: a new asset sitting in the kit folder would otherwise help
define the contract it is being judged against.

`kenney-asset-kit`'s own `kenney_probe2d.py` is the third of that family and the 2D arm of it:
survey a 2D pack, or `--check` one sprite against it, same excluded-candidate rule, exit 1 on a
mismatch. It decodes PNG itself (zlib + struct — no Pillow, so the stdlib-only property holds)
and covers every colour type and bit depth Kenney ships. Its load-bearing idea is that
**"on-palette" is distance to the nearest segment between two palette entries, not equality**:
Kenney's vector art is anti-aliased, so a seam pixel between two flat fills lands part-way along
the line between them, and exact membership false-fails on Kenney's own sprites. The same metric
derives the palette (frequency alone cannot separate a fill from an anti-aliased shade of it).
Tolerance 12 was set against a leave-one-out sweep: worst legitimate blend ~7, magenta control
188, zero false failures over five packs. Changing that constant means re-running that sweep.

Its `assets/bmcp_helpers.py` breaks the `assets/` convention below and the deviation is the point:
it is never copied into a project. Blender reads it **off disk itself** via
`importlib.util.spec_from_file_location` and keeps it in `sys.modules`, because each
`execute_blender_code` call gets a fresh namespace while `sys.modules` and the `bpy` scene persist.
That keeps the helper source out of the conversation entirely. It imports `bpy`/`bmesh`/`mathutils`
at module level, so it cannot be imported outside Blender — to syntax-check it here, stub those
three modules in `sys.modules` first, which is enough to exercise the pure functions
(`palette_from_dir`, `box`, `taper_box`).

**`resolve_skill.py` is the fourth of the measurement family**, pointed at the install rather
than at any asset. `skill-feedback-issue` used to ask the reader to hand-cross-reference
`installed_plugins.json` and `known_marketplaces.json`, which produced the slug fine and hid
the harder question: the cache keeps *every version ever installed* side by side, and the tree
a skill loads from is not guaranteed to be the one `installPath` names. That is a latent trap
in every skill and the front door in this one, whose whole premise is that stale installs
cause false alarms. `--ran-from` settles it by comparing the skill's own files between the two
trees — plugin versions nearly always differ somewhere, so the only useful question is whether
they differ *in the skill being reported on*. Note that it looks for both layouts a skill can
ship in, `skills/<name>/` and `commands/<name>.md`; a plugin installed on this machine uses
the second, and checking only the first reports "no plugin carries this skill" for one that
plainly ran.

**`seed.py` is driven by `references/axes.md`.** The script parses that Markdown at runtime: every
`- ` bullet under a `## <axis>` heading is one draw candidate, prose between headings is ignored,
and the sections `verb`, `subject`, `resource`, `constraint`, `perspective`, `tone` are required.
Tuning the skill's output means editing the wordlists, not the script.

## Conventions

- Skills document failure *symptoms* and the reason behind a rule, not just the rule. That prose
  is the product; match its density when adding to a `SKILL.md`.
- Refer to a skill's own files as `<skill dir>/scripts/...`, never `~/.claude/skills/<name>/...`,
  which only resolves for a loose install and not under the plugin cache. The only remaining
  mention of that path is in `skill-feedback-issue`, where it is deliberate — it is describing
  loose installs.
- A change to a `.gd` template is not done until both smoke tests, `juice_test.gd` and
  `palette_lint.py` pass, and a new assertion is not done until it has been shown to FAIL
  against the defect it describes.
  Mutate the scaffolded copy in the throwaway project (never the repo), run, and re-scaffold to
  restore. Three assertions written here initially passed against the bug they were meant to
  catch — one was measuring a Container that is stretched regardless of its own alignment.
  A check also is not done until its *exemptions* have been shown to stay quiet: `palette_lint`
  was proved on three injected leaks and then separately proved silent on the achromatic shapes
  and the `# palette-lint: ignore` pragma. A check that fires correctly but also fires on
  legitimate code gets switched off within a week, which costs more than never shipping it.
- The Godot kit is deliberately asset-free: no `.png`, `.ttf`, `.tres` or `.tscn` — colours come
  from one theme file and icons are drawn in `_draw()`. Eval assertions enforce this.
- `.gitattributes` forces LF; keep scripts POSIX-shebanged and path-agnostic (they run on Windows
  here but are meant to travel). Patching a file from a throwaway Python script needs
  `write_bytes` or `newline="\n"` — `write_text` emits CRLF on Windows, git normalises it on
  checkin so it never appears in a diff, and the working copy is left disagreeing with the repo.
  That matters here because two byte-identity assertions between the UI skills compare files
  directly and will report a difference that `git diff` denies.


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->
