---
name: scope-vs-claim
description: Compare what a check SAYS it covers against what it actually covers, before trusting it. Use when writing or reading anything that describes its own coverage — a test name, a docstring, an evidence string beside a measured budget, a checker scoped by a marker or delimiter, a hand-enumerated set of cases, a denominator that can be zero for more than one reason — and whenever a check has reported clean for a long time and you cannot say what it would have missed. Symptoms it fits: "that test passed, so the layout is fine", "the linter is green", "we sweep every X" where X grew, "the budget says there is headroom". Pairs with `derive-the-list` (is the SET right?) and `extract-a-testable-seam` (can this assertion fail at all?); prefer this one when the code is fine and the sentence beside it is what you are relying on.
---

# The description is the half that cannot fail

A check has two halves. It **covers** a scope, in code. It **states** a scope, in prose —
a test name, a docstring, an evidence string, a `NOT COVERED:` line. A reader trusts the
prose, because reading it is cheap and reading the code is not.

Nothing compares the two. So when they drift apart, the check goes on reporting clean and
the sentence goes on being read, and there is no moment at which anything is wrong enough
to notice. **The code can fail. The sentence cannot.** That asymmetry is the whole defect
class.

The five shapes below are each drawn from a real incident in one Godot game project, over
about a year. They are not Godot-specific; nothing here depends on an engine, a language or
a test runner.

## The five shapes, and the cheap test for each

### 1. A free-text corpus string

A UI budget measured the widest message a HUD row could hold, and described itself as
sweeping *"every plant name and corn level"*. True the day it was written. Then a second
kind of message started sharing that row, and at 570px became the widest thing on it
against the plant messages' 534. The budget was wrong by 36px for seven weeks **while
reporting green**, because a budget computed over a subset always reports more headroom
than exists.

> **Test:** read the sentence, then ask *what else falls inside the thing it names?* Here
> the sentence named the corpus ("every plant name and corn level") but the **row** was the
> scope. Anything that can appear in the row belongs in the sweep.

### 2. A region delimited by a marker

A mirror-check compared the text between a `# workflow` heading and an end marker, and that
marker list contained `\n---\n` — ordinary Markdown. A horizontal rule inside the block ends
the block early **in both files equally**, so two 21-character stubs compared identical and
the check reported clean over a fraction of the text.

> **Test:** can the region be smaller than intended, and would that read as clean? If the
> delimiter is a string that can legitimately occur *inside* the content, the answer is yes.
> Assert the region's size, or detect the ambiguity and say so.

### 3. A hand-enumerated set of cases

A `_update_facing()` mapped four cardinal directions to sprite orientations. The suite
asserted `+X` in a gait test, `-X` incidentally via a corpse test, used `+Y` without ever
checking its value, and never mentioned `UP` at all. Three of four covered *by accident*;
the fourth by nothing. No test was named in a way that revealed the set had four members,
so nothing showed the gap.

> **Test:** is the set enumerated **anywhere in one place**, or only implied by scattered
> coverage? Coverage spread across N tests written for other reasons is not a statement
> about the set — it cannot be read, so it cannot be read as incomplete. (`derive-the-list`
> is the fix; `enumerate-the-pairs` is the fix when the claim is about combinations.)

### 4. A denominator that can be zero for two reasons

A checker's `autoload_names()` returned an empty map both when a project genuinely declares
no autoloads and when the config section was absent, renamed or unparseable. An empty map
just resolves fewer names, silently, and the run stays green.

> **Test:** for every zero the check can produce, name **all** the states that produce it.
> If there is more than one and they mean different things, the zero is not a result. Print
> the count, and print it loudly when it is zero.

### 5. A test's NAME — the claim most people read and least people check

`test_the_road_is_still_the_road_the_constants_were_measured_against` existed to fire when
the game's road changed. A later change replaced the road completely — every corner, a whole
new leg — and it passed, correctly. What it actually asserts is the road's **length and cell
count**, which were deliberately preserved; it says nothing about shape.

Both halves are right. The test is right to pass and the road is right to have changed. The
defect is that a reader trusting the name would conclude the road was untouched, and a name
is the cheapest thing to read and the most expensive thing to verify.

The fix was a rename to
`test_the_road_still_has_the_length_and_cell_count_the_constants_were_measured_against`,
plus a header naming the sibling tests that do guard the shape.

> **Test:** read the name alone, say what would have to be true for it to fail, then read
> the assertions. A name that describes a stronger claim than the body checks is the
> commonest form of this whole defect, because a test that passes is never re-read.

## Doing the audit

Read the sentence first, then the code, in that order — the reverse re-derives the sentence
from the code and always agrees with itself.

1. **Say the scope out loud in your own words**, from the prose alone.
2. **Ask what else falls inside it.** Not "is the code correct" — "is the *set* right".
3. **Then read the code** and list what it actually visits.
4. **Where they differ, fix whichever is wrong.** Sometimes the sentence was aspirational
   and the code is right, in which case correct the sentence. A description narrowed to
   match reality is a real fix; it is what makes the next reader's trust warranted.

Fixing only the code and leaving a now-stale sentence is how shape 1 happened in the first
place.

## Where this sits next to its neighbours

- **`derive-the-list`** asks *should this set be computed rather than typed?* It is about
  the set's **source**.
- **`enumerate-the-pairs`** asks the same question one level up, where the claim is about a
  relation between members rather than the members themselves.
- **`extract-a-testable-seam`** asks whether the assertion is reachable at all.
- **This** asks whether the sentence and the code agree. It is about the **gap between
  them**, and it applies even when the list is correctly derived and the denominator is
  correctly printed — a truthful denominator over the wrong region is still the wrong
  answer, confidently stated.

## The tell

**A check that has reported clean for a long time, where you cannot say what it would have
caught.** That is not evidence of health; it is the absence of evidence either way, and it
is exactly what all five incidents above looked like from outside on the day before they
were found.
