# The gates: reading the output, not the exit code

A gate has three possible outcomes and most runners collapse them into two. **Exit `0`
passed, `1` found something, `2` could not run** — and a `2` means you verified nothing,
not that the tree is clean. Whatever you build, keep that third code and use it.

## Two clocks, two commands

Split the checks by how long they take, not by what they are about:

- **The fast set — every cycle, seconds.** Everything parallel-safe: static checkers,
  linters, name resolution, the unit suite if it is quick. This answers *is the tree clean
  now*.
- **The slow set — every few cycles, or when a rule it surveys has just been broken.**
  History sweeps, anything needing a running process, anything that takes half a minute.
  This answers *how often has this happened*.

Folding the second into the first puts a git-history sweep on every commit and a
needs-a-live-process check into the pool whose defining property is that it needs nothing.
Separate them on measured runtimes, not on taste.

**Make the runner DERIVE its own set** — every script in a directory declaring some house
marker, say — rather than reading a hand-typed list. Then have it print `ran N of M
discovered` plus a classification of every candidate into checker / not-parallel-safe /
known-non-checker / **unclassified**. That last category is the point: a new checker that is
neither derived nor listed fails the run, so a checker can no longer be written and silently
never run. (This is `derive-the-list` applied to the gate set itself.)

## What every gate must print

- **A denominator.** `Selected: N of M`, `Assertions: N executed`, `Suite: N script(s)`,
  `Shaders: N of M compiled`. `Total: 0 | ALL TESTS PASSED` is the worst failure mode a
  suite has, and only a denominator distinguishes it from a real pass. One cycle's heredoc
  ate the leading `#` off a comment block, silently removing 67 tests; the run reported
  `490 | Passed: 490 | Failed: 0 | ALL TESTS PASSED` and only the denominator (490 against
  557) caught it.
- **A `NOT COVERED:` line** naming the defect classes this checker does NOT see. It is the
  sentence printed directly under the clean count that invites the wrong conclusion, which
  makes it the right home for any negative result you paid to learn.
- **Every skipped check, named with its reason.** A check that could not run is named, never
  dropped from the denominator — a consolidated report is the easiest place for a check to
  vanish from.
- **A NEW vs PRE-EXISTING split** against a saved baseline, for anything run over a repo
  with existing debt. That is the number that means "this change" rather than "all repo
  debt". **Never refresh a baseline that still has findings in it** — that accepts them
  silently, and if the baseline is gitignored it destroys the evidence rather than dating it.

## The reads that catch a lying gate

- **A pass on code the run never loaded is a statement about the run, not the code.**
  Intersect the diff against what actually executed — coverage output, a loaded-module list,
  a process snapshot — and report the intersection. "Verified" on an unreached file is the
  most confident wrong claim available.
- **A number that is implausibly small is a broken scan, not a clean result.** Three hits
  over a large codebase invites belief where zero would have invited a second look. Ask
  whether the number is plausible for the question before asking whether the command worked.
- **A count of mentions is not a count of uses.** `grep -c` counts comments, tests and
  strings. When a count decides scope, open a sample of what it counted.
- **"Is this covered?" has one honest answer: delete it and run the suite.** No amount of
  reading the tests produces it. One cycle deleted four call sites and two whole function
  bodies and all 1003 tests stayed green. Reach for this whenever you are about to claim a
  thing is tested — especially where the tests assert CONSTANTS, which is where the gap
  always is.
- **Check `git status` after any run that was killed or timed out**, before believing
  anything it printed. A mutation sweep killed mid-run leaves a modified file that reads
  exactly like a finding. One mutation per foreground call, restore from the copy you made —
  **never with `git checkout --`**, which restores the FILE and silently reverts unrelated
  edits made to it earlier in the same cycle.
- **Pass `-u` (or your language's unbuffered flag) to a long-running child.** A killed batch
  otherwise leaves an EMPTY log, because its stdout was still buffered, which looks like a
  hang with no information at all.

## What no gate here compiles

Know which of your checks actually parse the code. Name-resolution checks, style linters and
grep-shaped checkers all report clean on code that will not compile — and the compile step is
usually the one that is not parallel-safe, because it writes a shared cache. That asymmetry
is why a fan-out lane, which gets no compile, is never "verified". Say so rather than
reporting a green run.
