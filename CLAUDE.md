# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A content repository, not an application: six Claude Code skills for indie game development
(Godot 4 UI, itch.io publishing, Kenney assets, seeded game design), packaged as one installable
plugin. There is nothing to build, no dependency manifest, and no test runner. The deliverable is
Markdown plus a handful of standalone scripts.

## Commands

The scripts are the only executable surface. All are stdlib-only except `store_art.py` (Pillow).

```bash
python skills/game-from-gibberish/scripts/seed.py --seed 41521    # deterministic; use to verify axes.md edits
python skills/kenney-asset-kit/scripts/kenney_probe.py "<kit dir>" [--json]
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

**`seed.py` is driven by `references/axes.md`.** The script parses that Markdown at runtime: every
`- ` bullet under a `## <axis>` heading is one draw candidate, prose between headings is ignored,
and the sections `verb`, `subject`, `resource`, `constraint`, `perspective`, `tone` are required.
Tuning the skill's output means editing the wordlists, not the script.

## Conventions

- Skills document failure *symptoms* and the reason behind a rule, not just the rule. That prose
  is the product; match its density when adding to a `SKILL.md`.
- Refer to a skill's own files as `<skill dir>/scripts/...`. Two SKILL.mds still hardcode
  `~/.claude/skills/<name>/...`, which does not resolve under a plugin install — fix those to
  `<skill dir>` rather than copying the pattern.
- The Godot kit is deliberately asset-free: no `.png`, `.ttf`, `.tres` or `.tscn` — colours come
  from one theme file and icons are drawn in `_draw()`. Eval assertions enforce this.
- `.gitattributes` forces LF; keep scripts POSIX-shebanged and path-agnostic (they run on Windows
  here but are meant to travel).
