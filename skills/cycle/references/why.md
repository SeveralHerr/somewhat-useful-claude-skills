# Why each step says what it says

`SKILL.md` is the loop. This file is the long form: the rule, and the cycle that paid for it.
Open the step you are on when the one-line version is not enough — in particular before
writing a backlog entry or an item description (steps 3 and 6), before running the gates by
hand (step 2), and any time you are about to change the loop itself (step 5), because most of
these rules were added by a cycle that had just broken them.

Everything below was paid for in one repo over ~180 cycles. The nouns were a game engine, a
tracker CLI and a self-test harness; the failures were not about any of those.

## Before step 0: the two standing biases

**The user-facing bias.** Tooling, audits and checkers are how a project stays honest, and
they had taken most of ten consecutive cycles — five shipping nothing a user could see, one
shipping no code at all. A checker is still the right call when it is the right call. But a
cycle that ships nothing user-facing owes one sentence saying why, and two in a row means the
next cycle takes a user-facing item whatever else is ready.

**"Simple" is a constraint on the loop file itself.** It reached 826 lines by growing a
little almost every cycle, each addition individually justified — which is how a file nothing
reviews gets to a size nobody reads. That is why the loop and its evidence are split: the
skill is what you follow, this is what you consult. Step 5 may spend its one change on
DELETING a rule that has stopped earning its place, and should prefer that to adding a
twelfth. An addition belongs here, not there, unless it changes what you actually do.

**The tracker and the cycle log are not two lists of the same thing.** Status, priority,
blocked state, dependencies and close reasons are real fields in a tracker, and they were
being copied by hand into a markdown checklist that could drift from them. The cycle log
holds only what a tracker structurally cannot: the counter, the pattern the last cycle
taught, what is waiting on the user, and how to restart. It is what a human reads without
running a command.

## §0 — pre-flight

**Report four NAMED values.** Four cycles running each reported an exit code, a ready count
and a skills listing and **silently dropped the backlog read** — the one item with no exit
code, and therefore the only one a habit of running commands cannot cover. A line with three
values in it looks exactly like a line with four.

**Why the step exists at all.** The reflection steps are end-of-cycle WRITES; nothing was
ever a start-of-cycle READ, so they filled up and never came back. Measured at the end of the
first 33 cycles: the skills directory did not exist at all, despite a standing instruction to
create skills there, and one skill had been named as missing three separate times without
once being built.

**Read in-progress separately.** A ready list excludes an in-progress item; a blocked list
prints the dependency rather than its state. One half-finished item blocked three others for
many cycles while carrying an accurate `STILL OPEN:` list in its own notes. The expensive
half was already done — that is the cheapest work in the queue, not the stalest.

**Match a missing skill on what it DOES, not on its name.** A log entry asked for
`audit-a-category`; `derive-the-list` was already that skill and its description opened with
the same recipe. Two independent identifications of the same missing skill means build it.

**The thing that quietly EMPTIES, not the list that quietly fills.** Every other pre-flight
item is a list that grows unread. Add here whatever can be silently deleted: a mirrored
instruction block, a pointer, a managed region. The block pointing at this loop was deleted
twice — the second time by the very commit that wrote the note warning about it, leaving the
note dangling above nothing. It was a hand-run `diff` for one cycle and a tool after that,
which immediately caught a one-sided edit nobody planted: the commit that registered the tool.

**Do not refresh an evidence snapshot that is not clean.** One cycle added the snapshot line
and refreshed unconditionally at the END of the cycle "so the next one starts clean", which
banked 98 drifted citations in one stroke — the baseline-write trap arriving inside the rule
meant to prevent it. Recovering them needed a worktree at the snapshot's exact epoch. If it
is not clean, the drift IS the work.

**Derive the counter.** The first draft of that command used `grep -c` and got 72, because a
count is not an index and early commits are worded differently — caught within a minute by
running it, which is the argument for a derived check being a command you run rather than a
number you write down. The file and the commits later disagreed by three, because the work
had started calling itself "round 11".."round 15" somewhere else and the bump step stopped
being run. If they disagree, the first thing the cycle writes is the missing sections.

Pre-flight REPORTS AND FILES; it does not block. The tooling is judged in step 4, after use.

## §2 — do the items

**`confirm` before `claim`.** The loop said "claim the item, write the code" for 88 cycles.
Four items were claimed whose factual premise was already false, and one was shipped **by the
cycle that filed it** — the function it claimed was missing returned the right thing twenty
lines below the line the claim was read from, and the test its acceptance asked for was
written the same day. An item is a claim about the repo made at some past cycle, and the repo
has moved.

**A SIZE is a claim too, and a `grep -c` is not one.** One cycle measured a feature at "78
references to three constants", concluded it was a whole cycle's work, and declined to start.
The next did it as one item: the 78 were overwhelmingly comments and tests; the runtime sites
were about eight. Counting mentions and calling them uses is the same wrong-set failure with
a consequence the others do not have — **it does not send you at the wrong thing, it defers
the right thing**, and a deferral leaves no evidence behind to be caught by.

**The suspicion runs the other way too.** A derivation returning almost NOTHING over a large
codebase is more likely a broken scan than a clean result. One sweep blanked string bodies
while scanning and found three readers — while the state it was chasing crossed the boundary
as dictionary KEYS, which the blanking had hollowed out. Three is worse than zero: a
plausible small number invites belief where an empty one invites a second look.

**Enumerate the category from the code, not from the item.** This was the deciding move in
five consecutive cycles and was rediscovered rather than followed every time. The clearest
case had a well-written item: *"audit every tip for whether it names a verb the user can
perform"*, with the producers listed and a per-tip verdict as acceptance. Working that list
took twenty minutes and produced five passes and nothing to ship. **The tips were not the
set.** The same message function had 23 call sites, and the ones that mattered were the
**refusals** — the message shown to someone who has just been stopped and is looking for what
to do instead. The item named none of them. They held three defects: every refusal rendered
in Title Case because the capitalize call title-cases every word; a duplicated literal under
a comment asserting it was not duplicated; and a width budget that had never priced any of
them.

> **The tell is the word in the item, not a feeling about the item.** "Every", "all", "each",
> "the N X's" — any of them claims the author knew the boundary of the set. Spend one grep on
> the boundary before spending an hour inside it. If the derived set matches, that is a
> two-minute confirmation and the audit proceeds with a denominator it can state. If it does
> not, the difference is usually the work.

**An item covering two things can ship one of them — note the half, never force the close.**
One item covered a difficulty picker and a board picker; the tracker refused the close
because the second half was blocked by an item that would produce a second board to pick. The
refusal was right. A forced close would have closed the board half by assertion, describing
work that does not exist in the field the next reader trusts most.

**If the method is "look at it", do not change what you did not look at.** A sweep rendering
screens and reading them as a user found a badly-paired button on one card, fixed it, then
renamed the matching button on a screen it never rendered because the rename seemed to follow.
It probably does. But a method is a promise about the evidence, and mixing in a different
kind of evidence spends the promise. Either reach the surface or leave it and file it.

**A gate letting through what you expected it to catch is itself a finding.** One cycle wrote
a call to a method that does not exist, ran the name checker, got `errors: 0`, found the
mistake by reading, and could have moved on. Asking "why did that not fire?" cost three
mutations and turned up a defect class invisible to three separate gates. Most rules here are
about not believing a pass; this one is about not shrugging off a pass that surprised you.

**Put a negative result where the next person will be standing.** One cycle measured that the
compiler's own warnings could not close a gate's blind spot. In a closed item that is
invisible — nobody re-reads a closed item before trying something. In a chronological log it
is unfindable. It went into the checker's own `NOT COVERED` line instead, printed directly
under the clean count that invites the wrong conclusion.

**When a constant is pinned by a test, check whether the pinned copy is the only copy.** One
cycle found a magic number in two user-facing strings: one gated against the constant for
cycles, one gated by nothing. That is worse than gating neither — move the constant, the
checked copy fails, somebody fixes it, and the silent copy is then the only version left
saying the old number with nothing pointing at it.

**When a tool declines to check something, find out what it is PRESERVING before building
the check.** A cycle set out to make the linter capture a warning and found there was none:
the analyzer stays silent on an unknown method for any object-typed receiver BY DESIGN,
because a method may arrive at runtime. Two cycles had treated that silence as an oversight.
Knowing the reason produced a checker that says which SLICE it is safe on and prints the size
of what it skipped. A gate built without that question either false-positives on the case the
silence was protecting — 29 of them, on the first draft — or checks nothing and says so.

**Split what the arithmetic can decide from what only the picture can, and say which is
which.** One cycle computed a colour from a contrast table before launching anything, so the
VALUE was settled without a screenshot; the launch answered exactly one question the table
could not. A run that cannot name the question it is for is the run that ends up `overkill`.

**When a checker hands you a denominator, walk the whole list once.** One scan priced all 25
world-space colours against both backgrounds and found one that clears NEITHER, which nothing
had prompted anyone to look at. The alternative is discovering the list's members one incident
at a time.

**A computed failure is a claim, and its reachability is part of it.** A sweep produced two
numbers under the floor; one described a combination refused at both its call sites in as
many words, the other priced a road-only mark against grass. A number out of a table looks
like evidence in a way an argument does not, which is exactly why it needs the same check.

**When the project already solved this somewhere, the fix is there, not in your head.** Three
cycles of contrast arithmetic arrived at a fix documented four lines below the defect: a
neighbouring constant's header already said a bare yellow dot dissolves into that background
and a rim is what keeps it legible. Before designing a fix, look at the nearest thing that
does the same job and see what treatment it carries.

**"Is this covered?" has one honest answer: delete it and run the suite.** One cycle asked
whether 24 rows of a table were backed by anything and found that deleting four call sites —
plus two whole function bodies — left all 1003 tests green. No amount of reading the tests
produces that.

**Never author code inside an unquoted shell heredoc.** A heredoc silently eats a level of
backslash escaping and has stripped the leading `#` off comment blocks four separate times.
One instance produced a test file that would not compile and the suite reported
`490 | Passed: 490 | Failed: 0 | ALL TESTS PASSED` — 67 tests silently absent, reported as a
clean run. Only the denominator and the exit code caught it.

- **The one narrowing.** A *quoted* heredoc (`<<'EOF'`) performs no expansion or backslash
  processing at all, so it cannot eat anything. Every instance this rule ever paid for was an
  unquoted `<<EOF` or a script writing source. A quoted heredoc appending to the END of a
  file is permitted.
- **And that has to be said, because the absolute form gets broken silently.** "Use `<<'EOF'`"
  is unusable the moment the block needs one shell variable, so the reach is for an unquoted
  delimiter and then every backtick inside becomes command substitution. One cycle wrote a
  comment naming four identifiers in backticks and got `the match in  is what decides` in the
  file, plus four `command not found` lines lost in the noise. **Pass the variable through the
  ENVIRONMENT** (`VAR="$x" python - <<'PY'`), which no quoting touches — as a command PREFIX,
  never a separate statement. Better still: `cd` there first and remove the variable.
- **The escape hatch is for running an interpreter, never for delivering source.** Having a
  sanctioned heredoc pattern made a heredoc feel like the tool for a 180-line test file, and
  the shell rejected the whole command with `unexpected EOF while looking for matching` —
  which is the GOOD version. The bad version works and eats something. Write the file, then
  append.
- **The mechanism is not the defect.** One cycle put a real newline inside a string literal
  through a plain edit tool, with no heredoc anywhere near it. What breaks is *a string
  literal containing a newline* and *a comment block that lost its leading `#`*, and both are
  reachable by hand. When a string will not fit one line, close it and concatenate. Know what
  will catch it: name resolution reports it CLEAN, because every name in it resolves. Only a
  real compile finds it — and the compile is the gate that is not parallel-safe, which is
  exactly why a fan-out lane is not "verified".

**Never batch long work that mutates the tree.** A six-mutation sweep run as one background
command was KILLED mid-mutation, twice, each time leaving a source file modified with a
`.bak` beside it. A mutated working tree reads exactly like a finding, and any gate run
against it reports a defect that does not exist. One mutation per FOREGROUND call, verify the
restore before the next, and **restore from the copy you made, never with `git checkout --`**
— which restores the FILE, and the file is not what you mutated: one such restore silently
reverted an unrelated correction made to the same file earlier in the same cycle, and nothing
caught it because the suite was green either way.

**Read `git diff --stat` before every commit.** Not the diff — the shape: how many files, how
many lines each way. It costs one command and it is the ONLY gate a docs-only change has. One
cycle cut three sections out of a markdown file using an index on a heading that turns out to
appear twice; the intended cut was 85 lines and the diff said **1937**.

**A reasoned EXCLUSION is a claim, and gets the same check as a citation.** Citation rules
cover what you assert and say nothing about what you deliberately leave OUT, and an exclusion
arrives wearing the costume of rigour — "this does not cover that case, and that is correct
rather than a compromise, for the same reason the sweep names one background per row". A
cycle wrote exactly that sentence, with a precedent cited, and the screenshot taken minutes
later showed the marker lying across the excluded case. **Every number said the exclusion was
safe and the picture said otherwise.** When you catch yourself justifying a case you are not
covering, that case is the one to go and look at.

**Evidence about a run lands before the commit, and evidence about a live process lands while
that process is still up.** A record taken after the commit sees an empty diff and reads
`reached 0/0 changed file(s)`, indistinguishable from a run that never started. And **one
capture at the end is not enough**: a screen you opened, drove, measured and then closed
before capturing reads exactly like a screen you never opened. One cycle measured nine labels
on a screen, backed out, captured, and got `NOT reached` for the file it had just spent ten
calls inside. The deadline is per screen, not per run.

**A diff confined to a surface the entry path never opens reaches NOTHING, and the run looks
clean while doing it.** One cycle changed four files across three screens, launched, got
`0 findings across 5 of 5 checks`, and recorded `reached 0/4 changed file(s)` — nothing in
the verify flow navigates. Decide before launching how each surface will be reached.

**Whether to launch at all is a triage decision, not a mood.** Six cycles launched in four,
and in two of those the record's own "cheaper alternative" field says the launch only
re-confirmed what a headless test had already asserted. The question that decides it: **name
the claim the launch will make that the suite structurally cannot.** "The frame swaps when a
REAL event fires, not when a test writes the field" is such a claim. "The label says the right
string" is not, when a test already instantiates the scene and reads that label.

**And launch at the moment the runtime question is ready, not one step earlier.** A live
process spends state while you work. One cycle launched before finishing its tests and came
back to `refused: the run is over` — the scenario had to be rebuilt from a fresh launch.
Another lost a 4-second armed window to four round-trips and misread the result as a defect.
Finish the headless work, decide the question, then launch, and set the scenario up in as few
round trips as possible: reading a predicate and then acting on it is two different games.

## §3 — add to the backlog

**Snapshot citations BEFORE the code edits and check them after.** The entries you write cite
code you changed an hour ago, and your own edits move the lines out from under them. It has
happened in two cycles — five citations, one drifting by 39 lines — and the checker reported
clean both times, correctly, because each landed somewhere real. Deciding whether a line
SUPPORTS a claim cannot be automated; noticing it is not the line you cited can.

**Cover every place your evidence lands, not just the obvious file.** One checker read the
backlog file and nothing else for eleven cycles while ~500 citations accumulated in tracker
descriptions and close reasons, where nothing looked. With the tracker included the snapshot
went from 352 citations to 880.

**Relocating a drifted citation by OFFSET satisfies the check without making it correct, and
this is where the real findings are.** A text-comparing check will match a blank line, a bare
`##` or a closing brace anywhere, so a uniform `+N` restore carries it forward looking clean.
Three consecutive cycles found citations that were already wrong *before* that cycle touched
anything — ten in total, every one found by reading the landing rather than by any tool. One
had 114 candidate lines. Two had drifted in SUBSTANCE (a count written out in prose; a
function that no longer exists), which no line-number check can ever see. If the code a
citation described is gone rather than moved, say so instead of repointing it at the nearest
survivor.

**The citation rules themselves** — cite a `file:line` for every claim about code as it is
now; search for the BEHAVIOUR, not one implementation of it; enumerate a pattern rather than
exampling it; cite BOTH halves of a comparison; read a collection's SHAPE before claiming
membership in it. Taste needs no citation: assert a preference plainly and let it be argued
with.

## §4 — reflect on the tooling

This comes after the work and not before, because "did the tooling earn its keep" is a
question about a run that has happened.

**Was it worth it?** `warranted` (runtime produced a claim reading the diff could not — name
it) / `overkill` (everything passed and confirmed what was already known) / `insufficient`
(it ran but never reached or asserted what mattered) / `inconclusive`. **`overkill` is a
useful entry, not an admission**, and it is the one that goes unwritten, because a run that
passed feels like a run that helped. Record the cheapest thing that would have given the same
confidence, and count a bug you fixed mid-run — every other field describes how the run
ENDED, so a defect surfaced at minute four and repaired by minute six vanishes otherwise.

**What was missing?** File it with a stable id that is never reused, and bump a `seen:` count
rather than filing a second entry for the same gap. If it is concrete enough to name what
should change and it ships from a repo you own, file it upstream as well.

**Reconcile old gaps from their LAST mention.** The format records status per entry, so a gap
fixed later still carries its original `open` line — `grep -c "status: open"` counts LINES and
said 61 when the answer was 44. Do not rewrite old entries; append the new status and let a
tool resolve it. And an id **cited** in an upstream release is not thereby fixed: 43 ids
appeared in one release and 29 of those were only in that release's copy of this very log.

## §5 — reflect on the workflow

The steps are the thing most likely to be quietly wrong, because nothing else reviews them.
Ask what actually happened: did a step get skipped, did one produce nothing, did the real work
happen somewhere these steps do not describe?

**Change at most one thing per cycle and write down why.** A workflow that rewrites itself
freely drifts; one that changes deliberately and records the reason can be read back.

**Edit the loop where the loop lives** — never in a pointer block elsewhere, and never inside
a region some scaffolder regenerates, where the edit is silently lost on the next refresh.

**If nothing needs changing, say so explicitly.** "The steps held this cycle" is a real
answer; silence is indistinguishable from not having looked.

## §6 — refill the queue

**File 3–8 concrete items, naming which SOURCE each came from.** This step once said "out of
the backlog's ideas", and that single filename is what made every other source invisible for
33 cycles. Never end a cycle with nothing ready.

**A source pointing at an already-open item gets a note on that item.** Four consecutive
cycles each filed an item whose own description said "duplicate of the open X, filed only to
record the second identification", then closed it in the same breath. The evidence is worth
recording and the item is not — a note puts it where the person working X will read it, keeps
the ready count honest, and can raise the priority, which a closed duplicate cannot.

**Never put prose in ANY tracker field as a shell argument.** Backticks are command
substitution: the word vanishes and the only tell is an unrelated `command not found` on
stderr, easy to miss beside the tracker's own chatter — and **a word that is also a valid
command is substituted silently, with its output landing in the field.** It happened in four
cycles, each time *after* a standing note said not to. The rule once named only the create
flag, so a close reason containing backticks read as covered and landed as "whose  MEANT one
kind" — a sentence that is still grammatical, which is the whole problem. Use `--body-file`,
`--stdin`, or `"$(cat PATH)"`. A file written with an editor tool never touches a shell, so
quoting, escaping and `file:line` citations all survive.

**An item description is where claims actually get acted on.** A factual sentence there is
read by whoever claims it, usually cycles later, and is trusted because it looks like a
finding rather than a memory. Three cycles running, an absence claim written into an item was
wrong, and each was written in the same breath as filing it. A description that says "verified
unbuilt" and does not say **how** is a memory wearing a finding's clothes.

**An acceptance criterion must be something the closing commit can produce**, or you have
written two items and filed one. One asked that two states be distinguishable on screen "and
a screenshot proves it". The code half shipped in the cycle that filed it; the evidence half
needed a running app and a rendered frame, so the item sat ready for **twelve cycles** looking
like unbuilt work while the feature was already shipped.

**Where the item proposes an ACTION, let the criterion accept "no, and here is why".** One
item asked that a drift bearing be recorded for every file before overwriting anything, and
said the bearings were most of the value either way; the bearings then showed the overwrite
would revert a shipped fix. A criterion that only accepts the action makes the cycle that
discovers otherwise look like a failed cycle, which is how a bad action gets taken on
schedule.

**At least one item from OUTSIDE this cycle's neighbourhood.** Five cycles shipped one
user-facing change and eleven correctness or tooling ones, and the cause is structural: the
queue is refilled from what the last cycle's work exposed, and the cite-a-`file:line` rule —
which is right — makes citing easiest for the file you already have open. So the loop keeps
finding real work three feet from where it just stood.

**And at least one a USER would notice** — added fifty cycles after the rule above, and the
same finding one layer down. That rule fixed *where* items come from and left *what kind*
alone, so the queue kept growing in one direction: 85 ready items, and a read of the first
forty found audits, checkers and "decide whether" almost throughout. **A steer at selection
time and no steer at filing time is a thermostat wired to nothing.** While filing the 3–8, ask
of each "could I show this to somebody using it?", and if the answer is no for all of them, go
and find one.

**Then rewrite the cycle log**: bump the number, what THIS cycle taught in a sentence or two,
what is waiting on the user and why. Short, and prose — the moment it grows a checklist it has
started duplicating the tracker. Keep the cycle number on the top line so the count survives a
context compaction.

## After step 7 — skills

**Identifying a skill twice without building it is the failure mode.** The first 33 cycles
named one missing skill three separate times and created nothing, because "identify a missing
skill" was an end-of-cycle note and never a start-of-cycle job. Step 0 reads that directory; a
skill named twice and absent from it is work, not an observation.

**Then USE it in the same cycle, on code you did not write it about.** A skill built and never
applied fails the same way a skill identified and never built does — it becomes prose nobody
has tested. One cycle built `scope-vs-claim` and turned it on the budget system inside twenty
minutes: a budget still missing five of eight producers a full cycle after being "fixed", a
table asserted in one direction only, a second hand-list nobody knew was a second list, and a
stale sentence in the cycle log itself. **The first application is what tells you whether the
skill is a recipe or an essay.**
