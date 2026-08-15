# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A content repository, not an application: eight Claude Code skills for indie game development
(Godot 4 UI, itch.io publishing, Kenney assets, Blender asset authoring, seeded game design, and a
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
python skills/godot-game-ui-juicy/scripts/scaffold_juicy_ui.py <godot project>
python skills/itch-store-page/scripts/store_art.py palette|cover|banner --src shot.png
```

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

**The two UI skills share files byte-for-byte.** `ui_theme.gd`, `ui_motion.gd` and
`smoke_test.gd` are identical copies in `godot-game-ui` and `godot-game-ui-juicy`; `hud.gd`,
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
- A change to a `.gd` template is not done until both smoke tests and `juice_test.gd` pass, and
  a new assertion is not done until it has been shown to FAIL against the defect it describes.
  Mutate the scaffolded copy in the throwaway project (never the repo), run, and re-scaffold to
  restore. Three assertions written here initially passed against the bug they were meant to
  catch — one was measuring a Container that is stretched regardless of its own alignment.
- The Godot kit is deliberately asset-free: no `.png`, `.ttf`, `.tres` or `.tscn` — colours come
  from one theme file and icons are drawn in `_draw()`. Eval assertions enforce this.
- `.gitattributes` forces LF; keep scripts POSIX-shebanged and path-agnostic (they run on Windows
  here but are meant to travel).


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
