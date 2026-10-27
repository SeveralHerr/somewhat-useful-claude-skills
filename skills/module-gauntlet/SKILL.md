---
name: module-gauntlet
description: Build a multi-module game or app one module at a time through a scored gauntlet run by the Workflow tool — a builder in its own git worktree, a critic that merges it and scores it out of 10 against a written contract, revise rounds until it clears the pass mark (8.5 by default) with no open high or medium finding, then a gatekeeper that runs the gates and commits — with scores and findings recorded in a STATUS file, lows forwarded into the next module's spec, an optional screenshot validation loop that fixes exactly three things per pass, and a final security and completeness gate. Ships the parameterized workflow script. Use whenever a plan or prompt says "one module per workflow", "critic scores out of 10", "revise until 8.5", "gate and commit", "builder / critic / gatekeeper", "waves of modules", or "build against ARCHITECTURE.md"; when a playtest review or feedback list with several small asks needs turning into modules ("lite gauntlet", "run the feedback through the gauntlet"); and at the symptoms of running that loop by hand — a critic score that passed while a flow count regressed, a builder that lowered a validator floor to just under its own regression, tests that stay green with the fix removed, worktrees left behind after a merge, a module that could not see the previous module's work. For a tracker-driven loop that works issues one at a time without a critic score, use `cycle` instead.
---

# Module gauntlet

`<skill dir>/scripts/gauntlet.workflow.js` is a ready Workflow script. Everything
project-specific arrives through `args`; nothing in it names a repo. It needs the Workflow
tool (Claude Code's scripted multi-agent runner) and git worktrees.

Two ways to run it, same script:

- **Full** — one module per run, up to 4 revise rounds. You read each result before
  launching the next, so you can fix a medium yourself, re-plan, or stop. Use it for a first
  build against a new contract, where each module changes what the next one needs.
- **Lite** — the whole batch in one run, up to 2 revise rounds each, with the lead's
  between-module work (forwarding lows) encoded in the script, then an optional validation
  loop and final gate. Use it for a feedback round of several small, independent asks.

```js
Workflow({ scriptPath: "<skill dir>/scripts/gauntlet.workflow.js", args: {
  repo: "/abs/path/to/repo",            // required
  branch: "feedback/round-3",          // required; never the branch that deploys
  modules: [{ name: "fb3-hud", paths: ["src/ui/", "styles.css"], spec: "…", extraGates: ["npm run validate"] }],
  product: "a web pinball game",       // used in every prompt
  conventions: "Plain ES modules, JSDoc-typed, node:test files beside the code. Dynamic text only via textContent.",
  gates: ["npm test", "npm run typecheck", "npm audit"],
  visual: "`SHOT_DIR=shots/<dir> npm run shot` screenshots desktop 1440x900 and phone 390x844; look at game-phone.png first.",
  bar: "top-tier web arcade games",    // what the critic scores against
  contract: "ARCHITECTURE.md §11", statusFile: "docs/STATUS.json",
  pass: 8.5, maxRevise: 2,             // default 4 for one module, 2 for a batch
  valPasses: 10, valFocus: "the playtester's themes: ball never hidden by UI, no duplicate readouts",
  finalGate: { gates: ["npm run stress"], asks: "callouts off the playfield; no duplicate score" },
  trailer: "Co-Authored-By: …",        // appended to every commit the agents make
  date: "2026-09-29"                    // scripts cannot call new Date(); pass it in
}})
```

Per module, the script runs: **builder** (worktree, commits there) → **critic** (merges the
builder's SHA into `branch`, runs the gates, scores, writes the module's STATUS entry) →
**revise** while score < pass, a gate is red, *or any high/medium is open* → **gatekeeper**
(runs gates plus `extraGates`, commits module paths + STATUS only when green, removes the
merged worktree). Open lows of module *i* are appended to module *i+1*'s spec.

## Before the first module

1. **Decide the platform before the art.** Renderer, runtime-dependency rules, engine. A
   round of mockups had to be redone once "3D" met "zero runtime deps"; the contract written
   on top of them went with it.
2. **Write the contract** (`ARCHITECTURE.md` or equivalent): folders, allowed imports, event
   vocabulary, data shapes, and per module a *measurable* "done means". Add one STATUS
   entry per module (score, rounds, findings, disproved, status).
3. **Take the baseline.** Run the gates and the screenshot tool once and keep the images:
   they are the critic's "before" evidence. Map every user complaint to a pixel region.
4. **Branch off the deploying branch and commit everything.** Worktree builders branch from
   `HEAD`; an uncommitted contract or scaffold does not exist for them.
5. **Write the specs from the user's words.** Quote the complaint, name the baseline image,
   and give before/after numbers for anything measured. Order modules so later ones see
   earlier geometry: layout → overlays → renderer → boot.

## Lessons the spec has to carry

- **Floors come from targets, not measurements.** A builder set a validator floor just under
  its own regressed ramp count (543) and passed; only a critic comparing to the previous
  round caught it. Put the baseline count in the spec and say the floor may not move.
- **Every new test is proven by a mutation** — remove the fix, watch it go red. In one polish
  pass 3 of 8 "fixed" lows were tests that stayed green with the fix deleted. The prompts
  already demand the proof; reject a return that does not report one.
- **Derive "every X" test lists from the source.** A placement test that listed its cases by
  hand missed the one case where the medium bug lived (`derive-the-list`).
- **Critics list what they disproved.** A suspicion ruled out by measurement goes in
  `disproved` and is passed to the reviser as "do not fix" — this saved whole revise rounds.
- **Bisect a regression by measurement.** Revert one change at a time in a scratch copy and
  re-run the validator; one bank angle turned out to cost 60 % of ramp traffic, which no
  argument predicted.
- **Visual modules need real viewports.** Headless Chrome will not render narrower than
  ~500 px, so phone sizes go in an iframe wrapper. Test the viewport a phone actually has
  (browser chrome plus an embed header left 390x797, not 390x844) — a card collapsed to
  46 px there with every size test green.

## After each run (full mode) — cheap, high-value lead work

- **Fix open mediums yourself** with a regression test and mark them `fixed` in STATUS.
  That beats paying for another revise round. Batch lows into an integrator/polish pass.
- **Check `git worktree list`.** A gatekeeper can be blocked by a permission prompt when
  removing its worktree; remove it yourself after `git merge-base --is-ancestor <sha> HEAD`.
- **Open one or two screenshots yourself.** Do not trust the score alone.
- **Integrate before polish.** Get a playable build with an autoplay screenshot before the
  juice/UI modules, so their critics judge effects in the real product, not in mocks.
- **Contract additions** (a new event, a snapshot field) arrive as builder assumptions;
  fold them into the contract in an integrator step, not mid-module.
- **A user-named complaint the critic still sees gets its own follow-up module** now,
  instead of waiting for the next round.

## After a lite run

Read the final gate's per-ask proof — each ask cites a test or image, or is marked
unproven. `git worktree list` must show only the main tree. Open two images yourself.
Merge to the deploying branch only with the user's go-ahead.

## Known quirks

- Gatekeepers sometimes "correct" `rounds` in STATUS to their own count — harmless; note it.
- Rewriting STATUS with a different JSON writer re-escapes unicode and reformats the file;
  the prompts ask agents to keep the existing style.
- Keys that start the game also acting inside it (start key = plunger, tap-to-skip starting
  a run) slip past every module; ask for a smoke test that presses them on the title screen.
- `Image.decode()` never settles in a hidden document (background tab, headless embed);
  boot code that awaits it hangs only in production. Bound it with the `load` event.
- The script cannot call `Date.now()`, `Math.random()` or `new Date()` (they would break
  resume). Pass the date in `args.date`.
