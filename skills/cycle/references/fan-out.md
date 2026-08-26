# Fanning out a cycle: writing the lanes, and paying for the merge

Read this before spawning two or more agents on tracker items. The merge cost at the bottom
is what decides whether to fan out at all.

**A worktree per lane is the default.** Checkers are parallel-SAFE, not parallel-ISOLATED:
they open no project and take no lock, but they READ THE WORKING TREE, and in one shared
checkout that tree contains every sibling's half-finished edit. Five lanes ran with
worktrees and not one reported a sibling's file.

The prompt-writing IS the skill. One cycle wrote three lane prompts from scratch and they
were 90% identical; the next wrote five that were 90% identical to those. What varies
between lanes is four things — the item, the owned files, the tests, the acceptance — and
everything else is boilerplate that is expensive to omit and free to include.

## 0. Check the worktree base before you trust a single lane report

A worktree branches from **`origin/main`**, not from your local `HEAD`. A repo that batches
pushes is routinely dozens of commits ahead. Measured on the fan-out that produced this
section: **all four lanes were checked out 71 commits behind local `main`.**

That is not cosmetic. On that tree one checker was missing a whole mode, one source file was
missing a feature, and the test suite was missing ten tests. **Every absence claim a stale
lane makes is a fact about the checkout rather than about the repo** — one lane would have
reported "the item's premise is false, the third sighting does not exist" and been wrong.

Before spawning:

```bash
git rev-parse --short origin/main; git rev-parse --short HEAD
git rev-list --count origin/main..HEAD      # 0 means the default base is fine
```

If those differ, put this in **every** lane prompt, verbatim:

> Your worktree may be checked out behind local `main`. Before anything else, run
> `git rev-list --count HEAD..main`. If it is not 0, run `git checkout -B lane/<item-id> main`
> and re-confirm the item's citations against that tree — line numbers and neighbouring code
> have moved. Report your base sha in your final report.

Two of four lanes caught this unprompted; one had to be told mid-flight and redid its work;
the fourth was on main by luck of timing. **Do not rely on the lane noticing** — a lane that
does not notice reports a clean, confident, wrong answer, and its gates all pass because the
stale tree is internally consistent.

## 1. Partition by FILE, not by topic

Two items are one lane if they touch one file. That is the whole rule, and it is cheap to
get wrong because items are written by topic. **Give each agent disjoint files and say so in
its prompt.**

- **Same file, different functions → still fan out, but say which functions.** Two lanes on
  disjoint regions of the same 2000-line file merged without a conflict. Name the exact
  functions each lane owns AND the ones it must not touch, with the sibling's name, so each
  knows a collision is possible.
- **Same file, same region → they are one item.** Give both to one lane, in order, one
  commit each.
- **Same mechanism → they are one item even in different files.** Two items that each add an
  entry to the same registry, enum or one-shot list conflict in spirit even where git merges
  cleanly. This is the one the file rule misses.

**A shared append-only file is not a reason to split.** Every lane appends tests to the same
suite; that conflict is expected, mechanical, and yours. Tell each lane to append at the very
END under a clearly-named section comment, and tell it siblings are doing the same.

**Hold a registry file at the parent.** When several lanes each need one line in one file —
a size row, a corpus entry, a button in a bar — the parent owns that file and writes every
line after the lanes land. That is the one collision that is guaranteed rather than possible.
Tell each lane the file is held and to report the exact line it needs. This is **not** the
same as "they are one item": the work is independent and only the bookkeeping overlaps.

## 2. The blocks every lane prompt needs

Copy these. Omitting one costs more than including it.

**Identity and isolation.** "You are LANE X of a parallel fan-out. You are in your OWN git
worktree, isolated from the other N lanes." A lane that does not know it is one of several
will helpfully fix things outside its remit.

**Confirm before implementing.** "The item is a claim about the repo made at some past
moment. Open the cited lines and verify they say what the item says. If the claim is already
satisfied or wrong, STOP and report that instead of writing code."

**File ownership as a hard boundary.** List what it OWNS, then list what it must NOT edit by
name — including every shared narrative file (the backlog, the cycle log, the tooling log,
the instruction files) and the tracker's own data — plus "do not run any tracker command that
writes; the parent owns the queue." Add: "You may READ anything."

**The gate allowlist, verbatim, and the prohibition.** Name the one command a lane may run,
then say plainly which gates it must NOT: anything that opens a shared project cache, imports,
compiles, or launches the app corrupts sibling lanes when two run at once.

**"A clean name-resolution pass is not a compile."** Say it in every prompt and require the
lane to repeat it in its report. And note that **a fresh worktree usually has no build cache
at all**, so even an opt-in compile flag fabricates errors there — two lanes ran one
independently and both got exit 1 with invented "not declared" errors on lines they had never
touched. The lane gets no compile and must say so rather than claiming "verified".

**"A finding in a file you do not own is not your finding."** Costs a line, still true of
anything shared even under worktree isolation. It is what makes a lane check rather than
trust a clean exit it did not earn.

**The escaping trap.** "Write code with the edit/write tools, NEVER through an unquoted shell
heredoc, and never via a script that writes source. A quoted `<<'EOF'` append to the END of a
file is permitted. If an exact-match edit fails, re-read the exact bytes and edit again, or
write the whole file. When a string literal will not fit one line, close it and concatenate
on the next."

**The skills that match this lane's actual problem** — one or two, named, not the whole list.

**The suite's own traps**, for any lane writing tests — the setup helper that must be used,
the measurement that lies, and **always read stderr, because in many runners an error inside
a test aborts only that method and returns something identical to a pass.**

## 3. Worktree hazards

If the worktrees live INSIDE the repo, that costs twice.

- **A lane's own path contains the worktree directory name**, so any tool excluding nested
  checkouts by testing an ABSOLUTE path excludes the entire repo when run from inside a lane.
  One checker did exactly that: the parent read `298 resolved`, a lane read `260` plus 38
  bogus advisories — the same asymmetry as the original bug, pointing the other way, and
  invisible to whichever side you were not standing on. **Compute exclusions RELATIVE to the
  tool's own root, in one shared helper.**
- **Every tree-walking checker sees N+1 copies of everything during a fan-out, and only the
  PARENT sees them.** A recursive glob does not read `.gitignore`, so five lanes turned every
  citation into a six-way ambiguity — while each lane reported clean. If a tree-walking
  checker starts reporting mass findings mid-cycle, look at the worktree directory before
  believing any of it.
- **Clean up when the lanes land** (`git worktree remove`), or the next cycle inherits the
  ambiguity.

**A lane can die mid-flight, and the worktree it leaves looks like a finished one.** Four
lanes once terminated a minute in on an API error. Each left a registered worktree, checked
out on its branch, with a clean `git status` — exactly what a lane that finished and
committed leaves behind, minus the commit. So:

```bash
git worktree list                       # branch and sha per lane
git log --oneline main..lane/<item-id>  # EMPTY means it committed nothing
```

An empty log is the tell, not `git status`. Clean up with `git worktree remove --force` and
`git branch -D` before re-spawning, or the new lane collides with the old branch name. Two
things worth knowing while you are in there: **`git worktree prune` does not remove a stale
worktree DIRECTORY** whose admin files are already gone (compare `ls` against
`git worktree list`); and **`git -C <dir>` on a directory that is not a worktree silently
resolves to the PARENT repo**, so a loop over the worktree directory reports the parent's
dirty state as if it were a lane's.

## 4. What the parent owes, and it is more than the merge

**Budget for the merge, because that is where the failures are.** Three lanes each ran every
parallel-safe checker clean, and the merge failed FIVE times — a golden array broken by
another lane's growth, a "decide about this" gate tripped by a new entry, a test that funded
a purchase but never unlocked it, a doc string 119 characters over budget. **None was a
mistake by the agent that caused it**; each was a fact about a file it was correctly
forbidden to open. The parent pass is where parallel work integrates, its cost scales with
the number of lanes rather than the size of any one, and it is not optional. Because the
lanes compile nothing, expect the parent pass to find tests green by construction, layouts
with no room, and public surfaces no test names.

**Merge in dependency order, not in finish order**, and re-run the full gates after EACH
lane lands rather than once at the end — otherwise the failure names a symptom in a file
three lanes touched and you have no idea which one owns it.

**Resolve appended-test conflicts by keeping BOTH sides.** Every lane appended at the end of
the same suite; the conflict is two blocks of new tests, not two versions of one. Taking
either side silently deletes a lane's whole test contribution and the suite still passes.
Count the test methods before and after: the total must be the sum.

**The parent owes each lane's wiring, not just its merge.** One lane correctly refused to
touch two parent-owned files and listed seven exact edits it needed there. Skipping them
would have shipped a feature no user could reach — three files of dead code, all gates green.
**A lane that reports "needs these lines in a file I do not own" has not finished until the
parent writes them.**

**Ask for the report you will need at merge time.** A lane's report is the only thing you
have when the merge fails. Require: worktree path, branch, commit sha(s); its base sha per §0;
`git diff --stat`; **whether each item's claims confirmed**, with what it actually read; the
exact functions or line ranges it touched in any file a sibling also owns; which gates ran,
with exit codes and the not-a-compile caveat; **anything it needs in a file it does not own,
as an exact copy-pasteable edit**; the decisions it made that the item left open, and why;
and one sentence of tooling verdict.

**Tell each lane what the OTHER lanes will need from it.** The prompts are not independent
even when the files are. One lane was told a sibling would want a button in the row it owned,
and asked to report the width headroom it left — so the parent learned the row was 43px short
from a lane that never saw the button.

## 5. Decide before you spawn: is this worth a lane?

A lane costs a full prompt, a worktree, a merge, and a parent pass — and **it compiles
nothing**. Fan out when the items are genuinely independent and each is more than a few edits.
Do NOT fan out:

- two items whose only connection is that you thought of them together (still one lane if
  they share a file)
- an item that is mostly a decision rather than mostly typing
- anything needing a running app, a build pass, or a new asset — a lane can do none of those,
  so it will hand the work straight back

Say in the cycle's close which lanes ran together and why they were safe — **and what the
merge cost**, because that is the number that decides whether to do it again.
