# somewhat-useful-claude-skills

A personal collection of [Claude Code](https://claude.com/claude-code) skills for indie game
development, packaged as a plugin so they follow me between machines.

Most of it is aimed at the same workflow: building small games in **Godot 4**, dressing them
in **Kenney** art, and shipping them to **itch.io**. Four of them are engine-agnostic
verification discipline, and travel to any repo.

## Install

```
/plugin marketplace add SeveralHerr/somewhat-useful-claude-skills
/plugin install somewhat-useful-claude-skills
```

To update later, `/plugin marketplace update somewhat-useful-claude-skills`.

For local development against a checkout instead of GitHub, point the marketplace at the directory:

```
/plugin marketplace add /path/to/somewhat-useful-claude-skills
```

## What's in here

| Skill | What it does |
| --- | --- |
| `godot-game-ui` | Builds polished in-game UI for Godot 4 — HUDs, pause menus, title screens, results screens, counters, prompts. Ships a Python scaffolder that installs a working UI kit into any Godot project, in one of six palettes picked from the game's tone, plus a lint that proves the palette really is the whole art direction and measures every ink/surface pair against WCAG AA. |
| `godot-game-ui-juicy` | Everything `godot-game-ui` ships, plus a full motion layer: overshoot entrances, staggered rows, punching counters, shake and screen flash — with a global switch to turn it all off. |
| `itch-store-page` | Sets up or updates an itch.io game page (theme colours, tagline, tags, cover, banner, screenshots) by driving your logged-in Chrome, and generates store art and a palette from gameplay screenshots. |
| `itch-ci-deploy` | Sets up continuous deployment of a Godot 4 Web build to itch.io — a GitHub Actions workflow that exports headlessly on every push and pushes with butler, cached so runs after the first take ~2 min. Its scaffolder measures the project first (Godot version, export preset, thread support, gitignore, renderer) and fails on the things that break the first run, and `--check` audits a pipeline that used to work. |
| `itch-devlog` | Writes and files a short end-of-day devlog as an itch.io draft — pulls the day's work from git, translates it into player-facing bullets, and grabs a fresh screenshot from the running game. |
| `godot-2d-placement-audit` | Asserts a Godot 4 2D layout numerically instead of trusting a screenshot or a green test suite — whether a spawn actually leaves its spawner, whether a radius reaches the tile beside it, whether every tile mask the level produces has a table entry, and whether sprites stay on their grid. Exists because these bugs present as "the tower doesn't shoot", never as an error, and the usual unit test hosts everything at the origin, where they cannot be reproduced. |
| `kenney-asset-kit` | Measures a Kenney kit's real grid unit, wall height, pivot convention, model facing, module widths, palette and triangle budget straight out of the glTF instead of guessing, names the module families the kit does *not* ship, and gives a bounding-box-anchored placement pattern (Godot 4 helper included). A second probe does the same for the 2D packs — canvas size, retina ratio, content box and clustered palette — and gates a new sprite against them. |
| `blender-mcp-modelling` | Models new 3D assets in a running Blender through the Blender MCP so they match an existing art style and actually load in the engine. Reads the palette and pivot convention out of the reference files, drives a build → render → look → fix loop, and gates the export against the reference set. |
| `game-from-gibberish` | Turns keyboard mash — or a blank page — into a real small game. Rolls the design constraints on dice before any thinking happens, so the randomness actually steers instead of collapsing back into an endless runner. |
| `skill-feedback-issue` | Sends a skill's own defects back here as a GitHub issue — resolves the installed plugin to its source repo *and to the cached tree that actually ran*, checks for a duplicate, and files what ran, what broke, the pinned version, and the proposed fix. This is what makes the collection self-improving. |
| `derive-the-list` | Replaces a hand-typed list of cases — a lookup table, a needle list, "the ones that matter" — with one derived from the source of truth, and gates it in *both* directions, because the one-directional test everyone writes cannot see an entry the list is missing. Includes the case where deriving is wrong: a taste call, and a hand-typed list whose maintenance cost *is* the check. |
| `enumerate-the-pairs` | Tests a claim about a *relation* — a precedence ladder, an override rule, a tie-break, a compatibility matrix — by looping the cross product instead of writing two or three examples. *n* members have *n²* ordered pairs, and the examples people write are the ones they were already thinking about. |
| `extract-a-testable-seam` | Makes a behaviour assertable when it lives past a gate the suite never opens — headless, muted, animations-off, a platform branch. Everything past that gate is unreachable code to a headless runner, so the test asserts the early return and an obviously fatal mutation survives. Move the composition out; leave the gate where it is. |
| `scope-vs-claim` | Compares what a check *says* it covers against what it actually covers. The code can fail; the sentence beside it cannot, so the two drift and the check reports clean forever. Five shapes with a cheap test each — including the commonest, a test name that claims more than its assertions check. |

The last four are the odd ones out: no Godot, no itch, no assets. They are verification
discipline — the ways a green check comes to mean nothing — and they apply to any repo in any
language. The worked examples in them come from a Godot game because that is where they were
paid for.

Skills load themselves when they're relevant — you generally don't need to invoke them by name.
Each one's `description` in its `SKILL.md` frontmatter is what Claude matches against.

## Layout

```
.claude-plugin/
  marketplace.json   # makes this repo an installable marketplace
  plugin.json        # the single plugin, which bundles every skill
skills/
  <skill-name>/
    SKILL.md         # frontmatter (name, description) + instructions
    scripts/         # optional executables the skill calls
    assets/          # optional templates the skill copies into a project
    references/      # optional docs the skill reads on demand
tools/               # repo maintenance; the only scripts here that don't ship to you
```

## Notes

- The two Godot UI skills overlap heavily by design — `-juicy` is the animated superset. If you only
  ever want one, install and ignore the other; they don't conflict.
- `itch-ci-deploy` is the third itch skill and the only one that does not open a browser: butler can
  push a build and nothing else, so it writes the workflow and hands you the short list of clicks the
  page still needs.
- `itch-store-page` and `itch-devlog` both drive a real logged-in Chrome session via the Claude in
  Chrome extension. They don't use the itch.io API, because it can't touch page presentation.
- `skill-feedback-issue` closes the loop the other skills open: when one of them gets something
  wrong in a real project, it files the issue against this repo from there — no checkout and no
  write access needed, which is why it can run from wherever the failure actually happened. It
  reports; it never patches. A fix reaches you only after someone acts on it, bumps the version,
  and you `/plugin update` — a skill runs from the plugin cache pinned to a commit, never from
  your checkout.
- `tools/` is not part of the plugin — nothing in it is installed. `verify_skill.py <skill>` runs
  every test a skill ships (it writes the throwaway Godot project itself); `lint_markdown.py` and
  `release_check.py` guard the deliverable and the release metadata. If you fork this, they are
  what tells you a change is safe.
- `game-from-gibberish` hands the actual building off to the Godot UI skills above and to the
  `godot-selftest-harness` plugin; on its own it only produces the brief. Its wordlists live in
  `references/axes.md` and are meant to be edited —
  that file, not the script, is what decides how strange the results get.
