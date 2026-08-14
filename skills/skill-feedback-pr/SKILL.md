---
name: skill-feedback-pr
description: Turn a concrete complaint about a skill that just ran into a pull request against the repo that skill ships from — resolve the installed plugin back to its source clone, write the fix in a throwaway git worktree so the user's branch and working tree are never touched, and open the PR with the evidence in the body. Use this after any skill or plugin run that revealed a real defect in the skill itself: a path that did not resolve, a step it omitted, an instruction its own files contradict, a gotcha that cost retries. Also use it when the user says "PR that improvement", "send that back upstream", "fix the skill", "why doesn't the skill know that", or is testing the self-improvement loop. Not for ideas, taste, or missing skills that do not exist yet — those are notes, not diffs.
---

# Skill feedback as a pull request

## What this closes, and what it does not

A skill runs from the **plugin cache**, pinned to a commit — not from any clone you can
edit. `~/.claude/plugins/installed_plugins.json` records both, as `installPath` and
`gitCommitSha`. So the loop is four steps and this skill only performs the middle two:

```
skill runs (cache, pinned)  ->  PR against the source repo  ->  user merges
   ->  version bump + /plugin update  ->  the next run sees the fix
```

Never tell the user the skill "is now improved" once the PR is open. It is improved on a
branch at best, and their next session still loads the old pinned copy. Say the true thing:
the PR is open, and the fix reaches them after a merge and a `/plugin update`.

## Fire only on evidence

One PR per skill per session, and only when all three hold:

- **The skill ran this session** and something concretely went wrong or cost retries. A
  defect you found by reading rather than by running is worth reporting, but say that in
  the PR body — "spotted while reading" and "this broke my run" deserve different scrutiny
  from the reviewer.
- **You can name the fix as one diff.** "This section could be clearer" is a note, not a
  PR. If you cannot write the replacement text, you do not have a PR.
- **It is not already open.** Check before branching; push to the existing branch instead
  of stacking a second PR on the same skill.

Everything else — speculation, taste, ideas for skills that do not exist — stays a note. If
the user keeps a suggestions log (usually a path named in a `CLAUDE.md`), write there too,
whether or not a PR gets opened. The log is the running record; a PR can be closed unmerged.

## 1. Resolve the skill back to a clone

Two files under `~/.claude/plugins/` do it. `installed_plugins.json` maps plugin →
marketplace, install path and pinned sha; `known_marketplaces.json` maps marketplace →
source:

- `"source": "github"` with a `repo` — the clone is normally a directory named after the
  repo in wherever the user keeps checkouts. Confirm with `git -C <path> remote get-url
  origin` rather than trusting the directory name.
- `"source": "directory"` — `installLocation` *is* the clone. It may still have an `origin`
  worth PRing against, so check.

No clone on disk, no `origin`, or an `origin` the user does not own → **stop, and write the
note instead.** Say you skipped the PR and why. Do not clone the repo yourself to route
around it; a fix proposed from a clone the user does not know about is a fix they will
never see.

Skills installed loose under `~/.claude/skills/` have no repo behind them. Offer to edit
those in place instead.

## 2. Write the fix in a worktree

Never `git checkout` in the user's clone. They are usually mid-branch with uncommitted
work, and a feedback PR does not justify disturbing it. A worktree gives a clean checkout
of the default branch somewhere else, with no effect on their tree:

```bash
git -C <clone> fetch origin
git -C <clone> worktree add -b skill-feedback/<skill>-<yyyy-mm-dd> <tmp>/<skill> origin/main
# ... edit inside <tmp>/<skill> ...
git -C <clone> worktree remove <tmp>/<skill>     # always, including after a failure
```

Branch from `origin/main`, not from whatever the local default branch points at — a stale
local main turns the PR diff into a pile of unrelated commits.

**Read the target repo's `CLAUDE.md` before editing.** It carries the rules a plain diff
violates silently. The ones that bite in this repo:

- `ui_theme.gd`, `ui_motion.gd` and `smoke_test.gd` are byte-identical copies in
  `godot-game-ui` and `godot-game-ui-juicy`. A fix to one lands in both, or the copies
  diverge and nobody notices until they behave differently.
- A `SKILL.md` `description` is the whole trigger surface. *Adding* symptom phrases is
  cheap and safe; rewriting or shortening one changes when the skill loads at all. Leave it
  alone unless the defect is the triggering.
- `godot-game-ui/evals/evals.json` asserts what the skill produces. If the fix changes
  that, the assertions change in the same PR.
- Do not bump `version` in `.claude-plugin/plugin.json`. Releasing is a separate deliberate
  step, and a version bump in a feedback PR conflicts with every other open one.

Keep the diff to the defect. A PR that fixes one path and also rewrites three paragraphs is
one the user has to read line by line instead of merging.

Verify what can be verified — the scripts here are stdlib-only and cheap to run. A change
to a `.gd` template cannot be compiled without a real Godot project, so say that in the PR
rather than implying it was tested.

## 3. Open the PR

Check for an existing one first, and reuse its branch if there is one:

```bash
gh pr list --repo <owner/name> --state open --search "skill-feedback <skill>"
gh pr create --repo <owner/name> --base main --head <branch> \
   --title "skill-feedback: <skill> — <the defect in five words>" --body-file <file>
```

Two operational notes. On Windows a `gh` installed by winget is often **not on the PATH**
of the shell tools run in — look in the standard install location before concluding it is
missing. And write the body to a file: multi-line `--body` through PowerShell quoting comes
out mangled.

The body is where the value is; the diff shows *what*, and only the session knows *what
happened*:

```markdown
**Observed** — what was run, and what went wrong, in one or two sentences.

**Cause** — the line or file in the skill that produced it.

**Fix** — what this diff changes, and why that shape.

**Verified** — commands actually run, or "not verified: <reason>".

Ran against `<plugin>@<version>` (`<sha>`), <date>.
```

Name the pinned version and sha. Once a few PRs are in flight, feedback from a stale
install is common, and that line is what lets the reviewer tell "already fixed on main"
from "still broken" without re-reading the skill.

## Guardrails

- Never commit or push to the default branch, never force-push, never merge your own
  feedback PR. These open ready to merge rather than as drafts, so the diff has to be small
  enough to review in one screen.
- Never open a PR against a repo the user does not own.
- One skill per PR. Two skills that both misbehaved get two PRs.
- If the push or the `gh` call fails, leave the branch, remove the worktree, report it. Do
  not retry with different credentials, and do not fall back to committing in the user's
  clone.

## Report back

The URL, one line on what the PR changes, and the honest state of the loop: what still has
to happen (merge, version bump, `/plugin update`) before it takes effect anywhere.
