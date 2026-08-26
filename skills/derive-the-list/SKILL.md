---
name: derive-the-list
description: Replace a hand-written list of cases — a lookup table, a needle list, a set of "the ones that matter" — with one derived from the source of truth, and gate it in BOTH directions so it cannot drift. Use whenever you are about to type a constant array or dictionary of names, masks, ids, paths or colours; whenever a check needs "all the X that Y"; when a bug turns out to be a case missing from such a list; when adding an entry to one; and when writing a test that iterates a recorded set. Also use when a list-driven check reports clean and you cannot say what it would have missed. Its counterpart for claims about combinations is `enumerate-the-pairs`; for whether the prose beside the list is still true, `scope-vs-claim`.
---

# Derive the list, then plant both directions

The recurring bug is not a wrong entry. It is a **missing** one, in a list nobody can tell
is incomplete by looking at it, checked by a test that iterates the list and therefore
cannot see past its end.

## The shape

1. **Ask whether a rule exists at all.** Before deriving, check that the list *has* a
   generating rule — "every Control under the HUD layer", "every function that reaches
   `_save()`", "every four-neighbour tile mask a level can produce". If the membership is a
   taste call ("the five starting weapons that feel good early"), it is not derivable and
   this recipe does not apply. Stop here rather than inventing a rule that fits today's
   list.

   **But "stop" is not the whole answer**, because the original problem is still there — a
   hand-written list that goes stale silently. A taste-call list gets step 3 without step 2:
   **keep it recorded, and assert the PROPERTY it claims** rather than its membership. That
   is what makes it a cache instead of a second source of truth.

   Worked example, and why this paragraph exists. A test fixture's seven-turret garden
   looked derivable — "turrets covering every road cell" is a rule, and greedy set cover
   computes it. Deriving it produced a *better* cover (five turrets reach all 32 road cells)
   and broke two tests, because the list's real content is calibrated **firepower**: a
   turret shoots only the furthest-along enemy in range, so a minimal cover is strictly
   weaker than a redundant one over identical cells. Seven is a judgement about how much is
   enough.

   So it stayed recorded and gained a test asserting the properties it claims — every unit
   can stand where it is put, the whole-road fixture reaches all of the road, the mixed one
   reaches most but not all. Three mutations kill that test, including a fixture cell that
   has silently become impassable terrain: the exact defect a level reshape had caused a
   week earlier, turning a six-unit fixture into five while every downstream ratio kept
   reporting a number.

   **The tell that you are looking at a taste call**: the derivation succeeds, produces
   something objectively better by its stated rule, and the tests get *worse*. The stated
   rule was never the whole requirement.
2. **Derive the set from the source of truth**, in code, at check time.

   **When the source of truth is "which files call a thing", the derivation is a source
   scan, and a raw substring scan is wrong.** The set is not a table you can read; it is the
   set of files that actually *reach* a symbol. In the project this came from, three of
   eight unit scripts read one particular field — and **all three also named it in a doc
   comment beside the line that reads it**, as did files that only discussed it. So
   `grep -l` credits a future file whose header merely mentions the field, and the gate
   silently widens.

   Blank comments and string bodies before matching (preserving offsets, so line numbers
   still point at something), and write that pass **once** for the repo. Six checkers there
   each rolled their own version of it and disagreed four ways.
3. **Assert the recorded list EQUALS the derived set** — not "contains", not "is a subset
   of".
4. **Plant both directions** and watch each fail. Add a member to the source that the list
   lacks; remove a member the list has. Both must go red, for different reasons.

## Step 4 is the one that gets skipped, and here is what it costs

A `GRASS_EDGE_TILE` table mapped a four-neighbour dirt/grass mask to an art tile. It was
properly derived — its header says how, by sampling the midpoint of each edge of all 299 kit
PNGs — and it was properly tested:

```gdscript
err = _T.assert_true(GRASS_EDGE_TILE.has(mask),
	"cell %s needs edge mask %d, which the kit has no tile for" % [cell, mask])
```

That is **one direction**. It fails when the level grows a shape the table cannot draw,
which is the direction that produces a visible bug, so it feels like the whole check. It
cannot fail when the table carries an entry no level can ever produce — a mask left over
from a road that was reshaped, pointing at a tile nobody has looked at in months. Nothing
says whether the nine entries there are nine or seven.

The second direction costs three lines beside the first: collect the masks the sweep
actually produced, and assert the table's keys equal them. If a legitimately unreachable
entry exists (kept for a level shape that is coming), the assertion is where that gets
written down, which is strictly better than it being invisible.

## Record the list, or derive it at check time?

The choice is not stylistic:

- **Derive at check time, keep no list.** A save-persistence checker walks backwards from
  `_save()` to a fixpoint on every run, so there is nothing to drift and a new persisting
  method joins the set the moment it is written. Choose this when the derivation is cheap,
  total, and needs no human judgement. Its predecessor was a hand-typed needle list of seven
  methods, blind to every caller that reached them indirectly — which is the whole reason
  the tool exists.
- **Record the list and assert equality.** Choose this when the derivation is expensive (299
  PNGs), when a human has to read the result, or when the mapping's *values* are a choice
  even though its *keys* are derivable. The recorded list is then a cache, and the equality
  assertion is what makes it a cache rather than a second source of truth.

The failure mode is a third option nobody chooses on purpose: a recorded list with a
one-directional test, which is a second source of truth wearing a checked list's clothes.

## Guard against the vacuous pass

A derivation over an empty input produces an empty set, which equals a list you forgot to
populate. Every sweep needs a denominator assertion:

```gdscript
return _T.assert_gt(checked, 60, "the sweep actually visited the grass (empty sweep = vacuous pass)")
```

Pick the threshold from what the input actually contains, not `> 0`. "More than nothing" is
true in exactly the situation you are guarding against.

## Two ways an enumeration is silently short

Neither shows up as an error. Both produce a list that is complete-looking and wrong, and a
wrong list is worse than no list because it gets cited.

**1. The wrong mechanism.** A survey asked "does any unit animate while idle?", enumerated
every `create_tween()` call across every unit file, found all eight event-driven, and wrote
down "verified unbuilt". Both idle animations in that game were `_process`-driven sinusoids
— a census of tweens cannot see them at any level of thoroughness. **Search for the PROPERTY
the behaviour would move (`rotation`, `scale`, `sin(`), not for the one API you imagine it
using.** If you can only name one implementation of the thing, you are enumerating your own
assumption.

**2. The wrong granularity of match.** A sound-call census used a line-oriented extraction,
piping `grep -rn` through a `sed` substitution to pull the event constant off each line. It
reported one event id as declared and never played. It is played —
`Sfx.play(Sfx.RUN_WON if victory else Sfx.RUN_LOST)` — and a `sed` substitution captures
**one match per line**, so the second constant in a ternary vanished. The corrected sweep
(`grep -o`, or a `re.findall` per file) found every id used, and turned up the finding that
actually shipped. **When the token you are counting can appear twice in one statement, count
tokens, not lines.**

The general form of both: an enumeration has an input set and a matcher, and only the
matcher's failures announce themselves. Before trusting a census, ask what a member would
look like that your matcher would step over.

## When the derived rule over-fires

If the derived set is much larger than the recorded one and the difference is all *true but
harmless*, do not weaken the rule — **raise its granularity**. The save-persistence checker
asked "can this function reach the writer" and got 62 findings over a suite that provably
writes nothing, because every write along those chains was conditional. Asking it once per
*file* instead of once per function gave five findings, each with one fix, and made the
conditionality moot rather than trying to evaluate it. A rule that fires on everything gets
waived on everything, and a waiver list is the hand-maintained list you were removing.

## When NOT to derive: a list that exists to disagree

Read alone, this skill says "always derive". That is wrong for one specific and common case,
and getting it wrong quietly destroys a working test.

A test held a hand-written list of the seven budget names a reporting command should emit,
and asserted the command reports exactly those. Adding an eighth budget breaks it. That
looks exactly like the smell this whole skill is about — a hand-maintained list, drifting
from the code — and it is the opposite.

**The test:** if you derive the list from the same source the code reads, does the assertion
still have two independent sides?

- **Yes → derive it.** The save checker derives the persisting set from `_save()` because
  the *checker* is the second side: the code says what persists, the rule says what tests
  must therefore redirect.
- **No → the hand-typing IS the check.** Deriving the budget names from the budget table
  would leave the command reporting what the command reports. The list is a tripwire
  pointing the other way: a budget declared and never wired into the report is invisible
  everywhere else, and one wired in that nobody meant to add shows up here as a number that
  moved.

The cost of updating such a list by hand is not a defect to be engineered away — **it is the
feature**, because paying it is what makes someone notice the set changed. Say so in a
comment beside the list, or the next reader will "fix" it.

## What derivation cannot do

It cannot tell you the list is the RIGHT list — only that it matches its rule. A derivation
of "every Control under the HUD layer" is exactly as correct as the claim that HUD-ness is
what the check is about. State the rule in a sentence in the code; if the sentence needs an
"except", the exception belongs in the assertion, not in a quietly missing entry.
