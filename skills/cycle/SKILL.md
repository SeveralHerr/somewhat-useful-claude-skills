---
name: cycle
description: A development loop that runs end to end and repeats until the user stops you — pre-flight reads, then tracker items one at a time (confirm → claim → implement → verify → commit → close against the acceptance), then add to the idea backlog, reflect on the tooling, reflect on the loop itself, refill the queue, bump the cycle log, and go again. Use whenever the user says run a cycle, work the queue, do the next item, keep going, work through the backlog, loop, work indefinitely, or never stop — and for the parallel form, when several items are fanned out to agents in worktrees. Engine- and language-agnostic; assumes an issue tracker CLI (`bd`, `gh issue`, anything), a gate you can run, and a repo you can commit to.
---

# The cycle

**This is a loop. It does not end. Keep going until the user stops you.**

Keep the loop simple and meaningful. Reflect on the product, the tools, the workflow and
your skills, and find meaningful ways to evolve all four.

**The TRACKER is the work queue. The CYCLE LOG is the narrative.** Every item lives in the
tracker and nowhere else — status, priority, blockers and close reasons are real fields
there. `cycle-log.md` (name it what you like; one file, at the repo root) holds only what
the tracker structurally cannot: the cycle counter, what the last cycle taught, what is
waiting on the user. Never write a work checklist into it, and never keep the queue in a
todo tool — those evaporate between sessions, which is the whole reason the tracker exists.

**Bias step 2 toward what a USER would notice.** Tooling, audits and checkers are how a
project stays honest, and they will happily eat whole runs of cycles. A checker is still
the right call when it is the right call — this is a bias, not a ban. But a cycle that
ships nothing user-facing owes one sentence in its close saying why, and two in a row means
the next cycle takes a user-facing item whatever else is ready.

## The three files

| File | What it is |
|---|---|
| `SKILL.md` (this one) | the loop, and only the loop |
| `references/why.md` | the long form of every step: the rule, and the cycle that paid for it |
| `references/gates.md` | how to read a gate's output, and why the exit code is not enough |
| `references/fan-out.md` | writing lane prompts, and the merge, when a cycle runs in parallel |

Read the step's section in `why.md` when the one-line version below is not enough. Most of
those rules were written by a cycle that had just broken them, so the reasons are worth more
than the instructions.

**Adapt the nouns, keep the shape.** `bd` below is one tracker CLI; `gh issue`, Linear or a
`.md` per item all work. "The gates" is whatever your repo can run in seconds. The loop's
value is the ORDER and the reads, not the tool names.

## The steps

**0. Pre-flight — read four things and report them as four NAMED values**, because a line
with three values in it looks exactly like a line with four: `items=N ready`,
`skills=N (none named twice)`, `backlog=<the section you looked at>`, `gates=clean`.

- **Open items**, in three reads, not one: ready, open, and **in progress**. The third is
  the one worth reading — a ready list excludes an in-progress item and a blocked list
  prints the dependency rather than its state, so a half-finished item that blocks others is
  invisible to both. One such item blocked three others for many cycles with its first half
  shipped and its own notes carrying an accurate `STILL OPEN:` list. **Someone already did
  the expensive half** — that makes it the cheapest work in the queue, not the stalest.
- **Skill ideas you have logged**, against the skills that exist. Named twice and absent
  means build it, not identify it again — and **"absent" is matched on what the skill DOES,
  against the descriptions, not on the name the log happened to invent.** One cycle logged
  `audit-a-category` as missing; `derive-the-list` is that skill, and its own description
  opens with the same recipe. Names differ, recipes do not.
- **The idea backlog** — recent sections plus whatever you are about to mine. Assume half of
  a long backlog's historical entries are stale, and audit a section before promoting
  anything out of it.
- **Whatever guards your own instructions from silent deletion.** If a pointer, a mirrored
  block or a managed region can be quietly emptied by an unrelated edit, check it here — the
  block pointing at this loop was silently deleted twice, once by the very commit that wrote
  the note warning about it.
- **Any evidence snapshot the later steps compare against — check it BEFORE re-taking it,
  and only re-take it if it is clean.** Overwriting a baseline that still has drift in it
  ACCEPTS that drift, and if the snapshot is gitignored the evidence is destroyed rather
  than dated. One cycle added a "refresh at the end so the next one starts clean" line and
  banked 98 drifted citations in a single stroke. **If it is not clean, the drift is the
  work** — leave the snapshot alone so the next cycle can still see it.
- **The cycle counter, DERIVED not read** — from the commits, not from the log file:
  ```bash
  git log --oneline | grep -oE "Close cycle [0-9]+" | awk '{print $3}' | sort -n | tail -1
  ```
  The MAX, not a count: a count is not an index, and early commits are worded differently.
  If the derived number and the log file disagree, fix that first — the counter is what
  every other retrospective in the loop is indexed by.

Pre-flight reports and files; it does not block. The tooling is judged in step 4, after it
has been used. → `why.md` §0

**1. Read the cycle log for context, then the ready queue for the work.** The log carries
the cycle number and what the last cycle learned; the tracker is the queue and there is
nothing to transcribe.

**2. Do the items one at a time: confirm → claim → implement → verify → commit → close
against the ACCEPTANCE.** One commit per item, never batched.

The last step is a distinct act: re-read the acceptance criteria **against what shipped**,
not against what you built. Those feel identical and are not. One item asked that a user
"can find out which difficulty a run is on *without leaving it*"; the work named the
difficulty on the title screen, and that read as satisfying it right up until the words were
read again. It took a second commit.

- **`confirm` comes before `claim`.** An item is a claim about the repo made at some past
  cycle, and the repo has moved. Four items in the source project were claimed whose premise
  was already false; one had been shipped by the cycle that filed it. **A SIZE is a claim
  too, and a `grep -c` is not one** — one cycle measured a feature at "78 references",
  called it a whole cycle's work and declined it; the next did it as one item, because the
  78 were overwhelmingly comments and tests and the real call sites were eight.
- **If the item names a CATEGORY, enumerate the category from the code.** "every tip", "all
  the cues", "each of the X" — the item's own list is a snapshot of what its author could
  see, and five cycles running the derived list was bigger than it. One tip audit found
  nothing in the tips and three defects in the **refusals**, the sibling class the item never
  mentioned. → `why.md` §2
- **An item covering two things can ship one of them. Note the half, leave it open, never
  force the close.** An item is a unit of CLAIM, not a unit of work, and half a claim closed
  is worse than an open one — the close reason would describe work that does not exist, in
  the field the next reader trusts most.
- **If the method is "look at it", do not change what you did not look at.** A sweep whose
  whole claim is "I rendered these and read them" cannot make a change on reasoning without
  quietly changing what the claim means. A method is a promise about the evidence.
- **A gate letting through something you expected it to catch is itself a finding**, and the
  moment you notice is the cheapest it will ever be to chase. Most rules here are about not
  believing a pass; this one is about not shrugging off a pass that surprised you — the
  surprise means your model of what the gates cover is wrong, which is worth more than the
  bug that revealed it.
- **Put a negative result where the next person will be standing when they have the idea** —
  next to the temptation, not next to the attempt. A "we tried this, it does not work"
  buried in a closed item is invisible; the same sentence under the clean count that invites
  the wrong conclusion is read every time.
- **Run independent items in parallel** when their files do not overlap. Two items that want
  the same file are one item. Lane prompts, the gate allowlist, the worktree traps and the
  merge: `references/fan-out.md`.
- **If the last two cycles worked the same SUBSYSTEM, take something else.** Ask what the
  last two cycles were ABOUT, not which files they opened — a 4000-line file is not a
  subsystem. **When this collides with the user-facing steer, the steer wins**: a stale
  neighbourhood costs a cycle of tunnel vision, a stalled product costs the product. Say in
  the close which rule you overrode, either way.
- **Never author code inside an unquoted shell heredoc, and keep every string literal on one
  line.** A newline inside a string literal compiles, passes, and is invisible to every gate
  but a real compile. Editing through a *script* is fine and is often better: a Python
  `str.replace` guarded by `assert t.count(old) == 1` cannot half-apply or silently no-op,
  which an exact-match edit can only promise for one match. The rule is about who escapes
  the string, not which tool touches the file. → `why.md` §2
- **Read `git diff --stat` before every commit** and check the shape is the one you meant.
  It is the only gate a docs-only change has. One cycle intended an 85-line cut and the diff
  said 1937.
- **Any evidence a run produces lands BEFORE the commit**, and evidence about a running
  process lands while that process is still up. After the commit the diff is empty, and a
  record taken then is indistinguishable from a run that never happened.

**3. Add to the idea backlog before reflecting** — features, UX, polish, docs, or a concrete
improvement. Then check your citations against the snapshot step 0 took.

Cite a `file:line` for every claim about the code as it is now; taste needs no citation.
Your own edits an hour ago moved lines out from under the entries you are writing, and a
citation that still resolves is not thereby correct — a line-number check proves a line
EXISTS, never that it supports the claim.

**If more than about ten citations have drifted, the relocation is a WORK ITEM, not part of
this step.** Fix what your own entries cite, file the rest, and say in the close how many you
left. Two cycles each absorbed this silently and each spent about a third of the cycle on it,
because the count is set by how many lines the feature happened to insert — nothing to do
with what the cycle is for. **Every one of those was already wrong before the cycle that
found it**, so it is real work and deserves to be scheduled rather than to arrive as a tax on
whichever feature touched a busy file. → `why.md` §3

**4. Reflect on the TOOLING, now that you have used it.** Was it worth it —
`warranted` / `overkill` / `insufficient` / `inconclusive`, with the reason, written down
where the next session will read it. `overkill` is a useful answer and the one that goes
unwritten, because a run that passed feels like a run that helped. What was missing gets
filed with a stable id; if it is concrete enough to name what should change and it ships from
a repo you own, file it upstream too (`skill-feedback-issue` does that from wherever the
failure happened). Reconcile the old gaps from their LAST mention, not their first — and
never rewrite an old entry to update it. → `why.md` §4

**5. Reflect on THIS WORKFLOW and tweak it.** Change at most one thing per cycle and say why
in the commit message. Prefer DELETING a rule that has stopped earning its place to adding a
twelfth. Edit it **here**, in this skill — never in a pointer block elsewhere, and never
inside a managed region some scaffolder regenerates. If nothing needs changing, say so
explicitly — silence is indistinguishable from not having looked. → `why.md` §5

**6. Refill the queue, then update the log.** File 3–8 concrete items drawn from step 0's
sources plus what steps 4 and 5 produced, **naming which source each came from**. At least
one must come from outside this cycle's neighbourhood, **and at least one must be something a
USER would notice** — step 2's bias is worthless over a queue with nothing to bias toward,
and a queue of 85 that is nearly all audits and "decide whether" is what fifty cycles of
refilling from reflection produces. → `why.md` §6

- **Never put prose in ANY tracker field as a shell argument** — backticks are command
  substitution, and a word that is also a command (`date`, `test`, `find`) lands its output
  in the field silently, leaving a sentence that is still grammatical. Write a file and use
  `--body-file` / `--stdin` / `"$(cat PATH)"`.
- A source pointing at an already-open item gets a note on that item, not a duplicate. A
  second identification is also a reason to raise the priority, which a closed duplicate
  cannot do.
- **An acceptance criterion must be something the closing commit can produce**, or you have
  written two items and filed one. One item whose criterion required a rendered screenshot
  sat ready for twelve cycles looking like unbuilt work while the feature was already
  shipped. **And where the item proposes an ACTION, the criterion should permit "no, and here
  is why" as a pass** — name what evidence would settle it and what recording that evidence
  is worth on its own. A criterion that only accepts the action makes the cycle that
  discovers otherwise look like a failed cycle, which is how a bad action gets taken on
  schedule.
- Then rewrite the cycle log: bump the number, a sentence or two on what this cycle taught,
  refresh what is waiting on the user. Prose, not a checklist — the moment it grows a
  checklist it has started duplicating the tracker.

**7. Go straight back to step 1. Do not stop, do not ask whether to continue, do not say
"next session" — you are the next session.** The only reasons to stop are the user saying
so, or a genuine block only they can unblock.

## Gates

Run everything cheap and parallel-safe every cycle; run the slow surveys on their own clock.
**Read the denominators, not the exit code** — a suite reporting `ALL TESTS PASSED` over 490
of 557 tests looks identical to a clean run. → `references/gates.md`

## Skills

When a skill would have been useful, create it — **identifying it twice without building it
is the failure mode.** Then USE it in the same cycle, on real code you did not write it
about; the first application is what tells you whether it is a recipe or an essay. One cycle
built `scope-vs-claim` and turned it on its own budget system inside twenty minutes: a budget
still missing five of eight producers a full cycle after being "fixed", a table asserted in
one direction only, a second hand-list nobody knew was a second list, and a stale sentence in
the cycle log itself. None of that surfaces from writing the skill well.
