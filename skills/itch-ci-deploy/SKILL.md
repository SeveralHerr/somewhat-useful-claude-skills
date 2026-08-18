---
name: itch-ci-deploy
description: Set up continuous deployment of a Godot 4 game to itch.io — a GitHub Actions workflow that exports the Web build headlessly on every push to main and pushes it with butler — and diagnose the ways that pipeline fails. Ships a scaffolder that measures the project (Godot version, export preset, thread support, gitignore, renderer) before writing the workflow, because each of those is a way the first run fails after eight minutes of downloading templates. Use this whenever the user wants their game to deploy, publish, upload or ship to itch.io automatically, mentions butler, wharf, a "deploy workflow", "CI for the web build", "push to itch on commit", or wants to copy another repo's itch deploy — and at the symptoms: the Actions run is green but the itch page shows nothing or an old build, the exported game is a black canvas with a SharedArrayBuffer error, "export produced no index.html", "no export preset named Web", "butler: no credentials", "no credentials and stdin is not a terminal", "invalid game", "itch.io API error (400) /wharf/builds", "the secret is set but butler says it isn't", "the templates are downloaded every run", "the run was cancelled", and when a run went green but the deployed build behaves differently from the editor. For the itch page itself (cover, tags, embed size, theme) use itch-store-page; for a devlog use itch-devlog — this skill only gets the build there.
---

# itch.io continuous deploy for Godot 4

## Start here: what butler can and cannot do

The whole automatable surface of itch.io is one command: `butler push <dir> user/game:channel`.
It uploads or patches a build. It does **not** create the game page, does not mark the
channel as playable in the browser, does not set the embed size, cover, tags or visibility.
So a "deploy" is: a workflow that builds and pushes, plus a short list of one-time clicks
on the itch.io Edit game page that no key can perform. Say that plainly before starting so
nobody expects the workflow alone to make the game appear.

The scaffolder writes the workflow; `itch-store-page` covers every click on the page.

## Procedure

1. **Get the target.** `user/game:channel` — the itch slug from the game's URL
   (`https://severalherr.itch.io/gather` → `severalherr/gather`), channel `html5` for a
   Web build. Slugs are lowercase. If the game page does not exist yet, it must be created
   by hand first (any title, draft visibility is fine); butler creates channels, never games.

   **Do not derive the slug from the repo name.** A first deploy has no URL to read it from,
   and the slug is whatever the user typed into itch's create-project form — usually the
   game's *title-screen* name, not the folder git happens to keep it in (a repo called
   `plant-tower-defense` holding a game called Pest Control has the slug `pest-control`).
   For an existing page, read it off https://itch.io/dashboard: each project's Edit link is
   `/game/edit/<id>`, and the slug is the `user.itch.io/<slug>` URL shown beside it. Or just
   open `https://<user>.itch.io/<slug>` and see whether it 404s. Confirm it before pushing —
   a wrong slug does not fail until the butler step, ten minutes in. The scaffolder WARNs
   when the slug you passed is the project folder's name and `application/config/name` says
   the game is called something else.

2. **Measure, then write:**

   ```bash
   python <skill dir>/scripts/scaffold_itch_deploy.py <project> --check
   python <skill dir>/scripts/scaffold_itch_deploy.py <project> --target user/game:html5
   ```

   `--check` audits an existing setup and writes nothing — run it first on a project that
   already has a workflow, and whenever a deploy "used to work". Without `--check` and with
   a `--target` it writes `.github/workflows/deploy-to-itchio.yml`, and if the project has
   no `Web` export preset it appends one to `export_presets.cfg` (thread support off,
   `bin/index.html`) — that file is what the headless export reads, and Godot with no
   preset by that name prints an error and **exits 0**. Options: `--preset`, `--branch`,
   `--godot-version 4.7-stable` (default is `<config/features minor>-stable`), `--force`.
   Read every `FAIL`/`WARN` line; each is a first-run failure it has seen.

3. **Secret.** Pass the key on the command line — never a bare `gh secret set`:

   ```bash
   gh secret set BUTLER_API_KEY --repo owner/repo --body "$KEY"   # or: echo "$KEY" | gh secret set …
   ```

   Get the key from https://itch.io/user/settings/api-keys. The workflow reads it as
   `BUTLER_API_KEY`, which butler picks up from the environment. Without it, everything
   succeeds until the last step, which fails with butler's own credentials error — after the
   full download+import+export, so check the secret before the first push.

   **A bare `gh secret set BUTLER_API_KEY --repo owner/repo` from any non-interactive shell
   — which is every shell an agent runs in — reads its value from stdin, gets EOF, and
   stores an empty secret. Exit 0, no warning.** `gh secret list` then shows it present,
   so listing is not a check. The failure is indistinguishable from having no secret at all:
   butler prints `Please set BUTLER_API_KEY to your API key … No credentials and stdin is
   not a terminal`. The one tell is in the Actions log above it — the masked value is
   normally `BUTLER_API_KEY: ***`, and an empty secret prints `BUTLER_API_KEY:` with nothing
   after it. Re-set it with `--body` and re-run.

   The scaffolded workflow now checks this in its **first** step, before the engine, the
   templates or the export — an empty or missing key fails in about ten seconds with an
   `::error::` naming the `--body` fix, rather than eight minutes in at the butler push.
   A workflow scaffolded before this was added does not have that step; re-scaffold with
   `--force`, or copy the `Check the itch.io credentials exist` step out of
   `<skill dir>/assets/deploy-to-itchio.yml` to the top of your `steps:`. It has to be
   first to be worth anything — a guard sitting just above `Install Butler` is correct and
   useless, since everything it was meant to save has already run.

4. **Commit `export_presets.cfg` and the workflow, push to `main`.** Watch with
   `gh run watch` or `gh run list --workflow deploy-to-itchio.yml`. Force a run without a
   code change via `gh workflow run deploy-to-itchio.yml` (`workflow_dispatch` is wired).
   The first run takes ~8–10 min (engine ~50 MB, templates ~1 GB, full import); every run
   after that restores all three from cache and takes ~2 min. A later run that is slow again
   means the cache key changed — check `GODOT_VERSION`.

5. **After the first green run, on the itch.io Edit game page:** Kind of project → HTML,
   and on the `html5` upload tick "This file will be played in the browser". itch.io's own
   butler docs say this must be done from the page once the first build is pushed; nothing
   in channel naming does it (only `win`/`linux`/`mac`/`osx`/`android` in a channel name
   auto-tag anything). Until then the run is green and the page shows a downloadable zip
   or nothing. Then set the embed size to the project's viewport (see `itch-store-page`).

6. **Confirm it landed:** `butler status user/game:html5` (with `BUTLER_API_KEY` set
   locally) lists builds with the `--userversion` the workflow passes — the short commit
   SHA — so "is the live build the commit I think it is" is a lookup, not a guess. Or open
   the page and read the version next to the upload.

7. **Then actually play the embed once, in a real browser.** A green run plus a page that
   renders proves the *right bytes* arrived; it proves nothing about what those bytes do.
   An exported template build is not the editor: `OS.has_feature("editor")` and
   `"debug"`/`"release"` flip, `OS.is_debug_build()` flips, autoloads still run their
   `_ready`/entry hooks, `res://` is read-only, and anything behind a devtools or
   `--skip-menu` path can fire for players. The reported case: a devtools autoload's
   `entry_hook` ran inside the exported build and dropped every player straight past the
   title screen — four green runs, a page that looked perfect, and a broken game. So before
   calling it done: load the embed, watch the first ten seconds, open the console, and grep
   the project for `has_feature`, `is_debug_build`, `OS.get_cmdline` and autoload entry
   hooks to see what an export changes. `godot --headless --export-release Web` plus a
   static server locally catches the same class of bug without a CI round trip.

## What the workflow does, and why each step is there

Read `<skill dir>/assets/deploy-to-itchio.yml`; the comments carry the reasons. In short:

- **`concurrency` with `cancel-in-progress`** — only the newest push to main can reach itch,
  so an older in-flight run is cancelled rather than paid for. A "cancelled" run right after
  a second push is this working, not a failure.
- **Three `actions/cache` layers** — engine keyed on version, templates keyed on version,
  `.godot/` import cache keyed on a hash of every `.gd/.tscn/.tres/.import/project.godot`
  with a `restore-keys` prefix so a near-miss seeds from the last cache instead of nothing.
- **`--import` twice, first `|| true`** — a fresh checkout has no `.godot/`; the first pass
  can fail while it is still resolving `class_name` declarations, and an export without an
  import cache produces a broken or empty build with no error.
- **`mkdir -p bin`** — Godot refuses to export into a directory that does not exist, and
  `bin/` is gitignored so it is absent in CI.
- **A file check after export** — Godot's export exits 0 on several failure modes; the
  presence of `index.html` is the actual success signal.
- **`butler push … --userversion ${GITHUB_SHA::7}`** — stamps the build with the commit.

## Gotchas by symptom

- **Black canvas, console says `SharedArrayBuffer is not defined` / cross-origin isolation.**
  `variant/thread_support=true` in the Web preset. itch.io does not serve COOP/COEP headers,
  so a threaded build cannot start there. Set it `false` (single-threaded builds run
  everywhere; the cost is no `Thread` in GDScript on web). The scaffolder fails on it.
- **Green run, page unchanged.** Either step 5 was never done (build is uploaded, not
  embedded), or the browser is showing the cached old build — hard reload. Then
  `butler status` to see whether a new build actually exists on the channel.
- **`itch.io API error (400): /wharf/builds: invalid game`.** The game slug in the target
  does not name a page this key's account can push to: it was guessed (usually from the
  repo folder) and the real page is under another slug, or the page was never created, or
  the user segment is wrong. butler will not create it. Read the slug off
  https://itch.io/dashboard, or check `https://<user>.itch.io/<slug>` for a 404, and fix
  `ITCH_TARGET` in the workflow. Nothing earlier in the run can catch this — the target is
  an opaque string until the upload.
- **`No credentials and stdin is not a terminal`, or `BUTLER_API_KEY:` printing blank in the
  log.** The secret exists but is empty — see step 3. `gh secret list` shows it present
  either way; re-set it with `--body` and re-run. Reaching butler at all means the workflow
  predates the first-step credential check, so re-scaffold while you are there.
- **`BUTLER_API_KEY is unset or empty` in the first ten seconds.** That is the guard doing
  its job, not a new problem — the same empty-secret mistake, caught before the run costs
  anything. The fix is the same `--body` re-set.
- **Green run, page renders, but the game behaves wrong.** The export is not the editor;
  see step 7. Suspect `OS.has_feature`/`is_debug_build` branches and autoload entry hooks
  before you suspect the pipeline, and never treat a green Actions run as a test of the
  build's behaviour — it only tests that a build was produced and uploaded.
- **`Export produced no bin/index.html`.** Read the export step above it. Usual causes: no
  templates for this exact version (a `4.7-stable` engine needs templates under
  `~/.local/share/godot/export_templates/4.7.stable` — the tag and the directory differ only
  by separator, and both env vars in the workflow exist for that reason); the preset name
  differs in case or spacing from `--export-release "Web"`; the import cache was invalid.
- **`Could not find type "X"` cascades in the export.** The import ran once and the class
  cache was not ready; the double `--import` is the fix and should already be there.
- **Templates downloaded on every run.** The cache `key` includes `GODOT_VERSION`; if the
  editor was bumped locally without bumping the workflow, the export runs on the wrong engine
  and the caches miss on the wrong key. `--check` reports a mismatch between the workflow's
  `GODOT_VERSION` and `config/features`.
- **Godot renders nothing / shader errors on web only.** Web runs only the Compatibility
  renderer. `rendering/renderer/rendering_method.web` defaults to `gl_compatibility`; a
  Forward+-only feature (some particle/light/shader paths) will not exist there. Test the
  exported build locally with `godot --headless --path . --export-release Web bin/index.html`
  and a static server before blaming CI.
- **Wrong game got the build.** The target is a string in the workflow's `env` and nothing
  validates it. The slug is the lowercase URL segment — a page titled "Pest Control" can
  live at `/pest-control`, `/pestcontrol` or `/pc-jam`; only the URL is authoritative. If it
  names a real page that is not the one you meant, the push succeeds and lands there.

## Extending it

- **Desktop channels:** add a Windows/Linux preset in the editor, then a second export +
  push pair with `:windows` / `:linux` — those channel names are auto-tagged by butler as
  the platform. Zip is not needed; butler pushes a directory.
- **Only deploy on tags / a release branch:** change `on.push.branches` (`--branch`) or add
  `tags: ['v*']`; keep `workflow_dispatch` for a manual re-run.
- **A different host than GitHub:** the shell in each step is host-agnostic; only the
  `actions/cache` and `actions/checkout` lines and the secret plumbing are GitHub-specific.
