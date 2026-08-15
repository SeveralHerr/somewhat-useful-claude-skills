# somewhat-useful-claude-skills

A personal collection of [Claude Code](https://claude.com/claude-code) skills for indie game
development, packaged as a plugin so they follow me between machines.

Everything here is aimed at the same workflow: building small games in **Godot 4**, dressing them
in **Kenney** art, and shipping them to **itch.io**.

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
| `godot-game-ui` | Builds polished in-game UI for Godot 4 — HUDs, pause menus, title screens, results screens, counters, prompts. Ships a Python scaffolder that installs a working UI kit into any Godot project, in one of six palettes picked from the game's tone. |
| `godot-game-ui-juicy` | Everything `godot-game-ui` ships, plus a full motion layer: overshoot entrances, staggered rows, punching counters, shake and screen flash — with a global switch to turn it all off. |
| `itch-store-page` | Sets up or updates an itch.io game page (theme colours, tagline, tags, cover, banner, screenshots) by driving your logged-in Chrome, and generates store art and a palette from gameplay screenshots. |
| `itch-devlog` | Writes and files a short end-of-day devlog as an itch.io draft — pulls the day's work from git, translates it into player-facing bullets, and grabs a fresh screenshot from the running game. |
| `kenney-asset-kit` | Measures a Kenney kit's real grid unit, wall height, pivot convention, model facing, module widths, palette and triangle budget straight out of the glTF instead of guessing, names the module families the kit does *not* ship, and gives a bounding-box-anchored placement pattern (Godot 4 helper included). |
| `blender-mcp-modelling` | Models new 3D assets in a running Blender through the Blender MCP so they match an existing art style and actually load in the engine. Reads the palette and pivot convention out of the reference files, drives a build → render → look → fix loop, and gates the export against the reference set. |
| `game-from-gibberish` | Turns keyboard mash — or a blank page — into a real small game. Rolls the design constraints on dice before any thinking happens, so the randomness actually steers instead of collapsing back into an endless runner. |
| `skill-feedback-issue` | Sends a skill's own defects back here as a GitHub issue — resolves the installed plugin to its source repo, checks for a duplicate, and files what ran, what broke, the pinned version, and the proposed fix. This is what makes the collection self-improving. |

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
```

## Notes

- The two Godot UI skills overlap heavily by design — `-juicy` is the animated superset. If you only
  ever want one, install and ignore the other; they don't conflict.
- `itch-store-page` and `itch-devlog` both drive a real logged-in Chrome session via the Claude in
  Chrome extension. They don't use the itch.io API, because it can't touch page presentation.
- `skill-feedback-issue` closes the loop the other skills open: when one of them gets something
  wrong in a real project, it files the issue against this repo from there — no checkout and no
  write access needed, which is why it can run from wherever the failure actually happened. It
  reports; it never patches. A fix reaches you only after someone acts on it, bumps the version,
  and you `/plugin update` — a skill runs from the plugin cache pinned to a commit, never from
  your checkout.
- `game-from-gibberish` hands the actual building off to the Godot UI skills above and to the
  `godot-selftest-harness` plugin; on its own it only produces the brief. Its wordlists live in
  `references/axes.md` and are meant to be edited —
  that file, not the script, is what decides how strange the results get.
