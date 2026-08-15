---
name: skill-feedback-issue
description: File a GitHub issue against the repo a skill ships from when that skill got something wrong — resolve the installed plugin back to its source repo, check for a duplicate, and open an issue carrying what was run, what broke, the pinned version and sha, and the proposed fix. Use this after any skill or plugin run that revealed a defect in the skill itself: a path that did not resolve, a step it omitted, an instruction its own files contradict, a gotcha that cost retries, guidance that turned out to be wrong. Also use it when the user says "file that", "log that against the skill", "send that back upstream", "the skill should have known that", "why didn't it warn me", or is testing the self-improvement loop. Files a report, not a patch — nothing is committed, pushed or merged.
---

# Skill feedback as a GitHub issue

## What this closes, and what it does not

A skill runs from the **plugin cache**, pinned to a commit — not from any clone you can
edit. `~/.claude/plugins/installed_plugins.json` records both, as `installPath` and
`gitCommitSha`. So the loop has four steps and this skill performs only the first:

```
skill runs (cache, pinned)  ->  issue on the source repo  ->  someone fixes and merges
   ->  version bump + /plugin update  ->  the next run sees the fix
```

Never say the skill "is now fixed" once the issue is open. Nothing has changed anywhere.
An issue is a report; say that plainly, and give the URL.

The advantage over opening a pull request is that this needs no checkout, no branch and no
write access to anything but the issue tracker — so it works from whatever project the
skill actually broke in, which is the only place the evidence exists.

## Fire only on evidence

One issue per skill per session, and only when both hold:

- **Something concretely went wrong.** The skill ran and cost retries, sent you to a path
  that does not exist, omitted a step you had to discover, or stated something its own
  files contradict. A defect spotted while reading rather than running is still worth
  filing — say which it was, because it changes how the reader triages it.
- **You can state the fix.** Not necessarily as a diff — an issue can carry "this section
  never says X, and it should" — but "this could be better" with no proposal is noise. If
  you cannot name what should change, you do not have an issue.

Ideas for skills that do not exist, taste, and preferences are not issues against a skill.
If the user keeps a suggestions log (usually a path named in a `CLAUDE.md`), those go
there — as does a copy of anything filed, since the log is the running record.

## 1. Resolve the skill to a repo, and to the tree that actually ran

Run this first. It answers both questions and will not let the second one go unasked:

```bash
python <skill dir>/scripts/resolve_skill.py <skill> --ran-from "<the base directory the harness announced>"
```

It prints the `owner/name` slug to file against, the version and sha to stamp on the report,
every version sitting in the cache, and whether the tree that ran is the tree
`installed_plugins.json` records.

The slug comes from two files under `~/.claude/plugins/`. `installed_plugins.json` maps
plugin → marketplace, install path and pinned sha; `known_marketplaces.json` maps
marketplace → source:

- `"source": "github"` — `repo` is the slug. Done; no clone required.
- `"source": "directory"` — the slug is that directory's `origin`
  (`git -C <path> remote get-url origin`). A local-only marketplace with no remote has
  nowhere to file; say so and write the note instead.

Skills installed loose under `~/.claude/skills/` have no repo behind them. Offer to edit
those in place instead of filing anything.

**`installPath` is not necessarily the directory the skill ran from, and that distinction is
this skill's entire subject matter.** The cache keeps every version ever installed side by
side — `…/cache/<marketplace>/<plugin>/<version>/` — and a session can be loaded from an
older tree while `installed_plugins.json` already records a newer one. Eight versions of one
plugin and nine of another were sitting in this machine's cache when that was last checked.
When the harness announces a base directory, take the version out of *that* path and pass it
as `--ran-from`. If the two disagree, verify against the one that ran and name both in the
Environment line: a line number confirmed in a tree that did not execute is precisely the
false alarm the next paragraph exists to prevent, arriving through the front door. The script
settles it by comparing the skill's own files between the two trees — two versions of a
plugin nearly always differ somewhere, and the only question that matters is whether they
differ *here*.

**Then re-verify each finding against the version that ran.** Findings usually arrive from
an earlier session, and the install may have moved since — a defect fixed between versions is
the most common wasted issue in this loop. Open the skill's own source, confirm each claim at
a line number, and say in the Environment line which ones were re-checked. Withdraw the ones
that no longer reproduce; it is normal for one of four to go. This step is also where
near-miss claims get corrected — "the counter never punches" turned out to be a different
function from the one that refuses, and the issue was better for reporting the contradiction
rather than the guess.

**While you have the source open, find the place the repo already applies your proposed rule
somewhere else, and cite it.** This is the step's larger payoff and it is easy to miss,
because the step is framed as a defence. Conventions get stated once and then not carried
across: the principle your fix depends on is usually already written down in the target repo,
argued better than you would argue it, and applied to a neighbouring case. A report that
quotes the maintainer's own words back at them, from their own file at a line number, gets
acted on where an outsider's reasoning gets debated. On the run that prompted this paragraph,
two such passages turned up — one in the target's `REFERENCE.md`, one in a linter's own
comments — and both went to the top of the issue. In this repo the same thing happened in
reverse: a screen script carried a comment explaining that ink must be derived from its fill,
while the screen one file over hard-coded exactly that ink.

## 2. Check for a duplicate first

The failure mode of an automatic reporter is ten issues describing one defect. Search
before filing, and prefer commenting on what is already open:

```bash
gh issue list --repo <owner/name> --state open --search "<skill> <distinctive phrase>"
```

If an open issue covers it, add a comment with this run's version, sha and symptom rather
than opening a second one — a second data point on a known bug is more useful than a
duplicate, and it shows whether the bug survived a release.

On Windows a `gh` installed by winget is frequently **not on the PATH** of the shell the
tools run in. Check the standard install location before concluding it is missing.

## 3. File it

```bash
gh issue create --repo <owner/name> \
  --title "skill-feedback: <skill> — <the defect in about five words>" \
  --body-file <file>
```

Write the body to a file; multi-line `--body` through PowerShell quoting comes out mangled.
Add `--label skill-feedback` only if that label exists — `gh` fails the whole call on an
unknown label, and the title prefix is doing the real work.

The body is the entire value of this skill. The reader is deciding whether to act, and they
cannot see the session:

```markdown
**What ran** — the command or request, and what the skill was asked to do.

**What happened** — the symptom, concretely. Error text, wrong output, or the number of
retries it cost.

**Where it comes from** — the file and line in the skill that produced it, if you found it.

**Proposed fix** — what should change. A diff if you have one, prose if you do not.

**Environment** — `<plugin>@<version>` (`<sha>`), <OS>, <date>. Spotted by running it /
by reading it.
```

Name the pinned version and sha every time. Feedback from a stale install is the most
common false alarm in this loop, and that line is what lets the reader tell "already fixed
on main" from "still broken" without re-reading the skill.

When step 1 found a disagreement, that line carries **both** versions and says which one the
claims were checked against — `@0.9.0 (<sha>) per installed_plugins.json; executed from the
0.6.0 cache directory, which is where the line numbers below were confirmed`. A maintainer
who cannot tell those apart has to re-derive the whole report before trusting any of it.

Quote what you actually saw. A paraphrased error is a search term that will never match.

## Guardrails

- **This files a report, and nothing else.** Do not branch, commit, push, or edit the skill
  in the repo — and never edit the plugin cache, which the next `/plugin update` overwrites,
  losing the fix and leaving the issue looking resolved when it is not.
- One skill per issue. Two skills that both misbehaved get two issues. Several defects in
  *one* skill belong in one issue, ordered worst first, saying what they share if anything
  does — a maintainer reading five separate issues about the same file cannot see that four
  of them have one cause.
- Never file against a repo the user does not own without saying so first — an issue is
  public on a public repo, and it carries the user's name.
- Do not paste the project's source, paths, or anything else from the session that the
  defect does not require. The issue is about the skill.
- If `gh` fails, report it and write the note. Do not retry with different credentials.

## Report back

The issue URL, one line on what it says, and the honest state of the loop: nothing is fixed
yet, and a fix reaches this machine only after a merge, a version bump and a
`/plugin update`.
