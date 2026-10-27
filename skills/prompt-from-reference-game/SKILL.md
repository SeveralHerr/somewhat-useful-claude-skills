---
name: prompt-from-reference-game
description: Write the build prompt for a new game that reuses an existing game's assets, art style and hard-won process rules — opening the reference repo instead of describing it from memory, gating on the asset licences, and keeping the constraints an agent cannot discover while leaving design choices to it. Use whenever the user asks to "make a prompt for a new game", "write a PROMPT.md", "use the assets from X", "reuse my other game's art", "follow the style of this prompt", "seed a new repo from my old game", "spin off a game from this one", or hands over a template prompt (often in a README `<details>` block) and a reference repo to fill it from. Also use when a generated prompt came back vague about art ("use a retro style"), cited skills or tools the new repo does not have, pointed at a folder name that does not exist, or would have copied a paid asset pack into a public repo. For turning a blank page or keyboard mash into a game concept, use `game-from-gibberish` instead; this skill starts from a game that already exists.
---

# Prompt from a reference game

The output is a prompt another agent will build a game from, usually in a fresh repo it
has never seen. Everything it cannot discover on its own has to be in the prompt; everything
it can discover should be left out, or the prompt turns into a stale spec it follows
instead of the code in front of it.

## Procedure

1. **Read the template prompt verbatim.** It is often a README `<details>` block or a
   previous `PROMPT.md`. Keep its section order and voice; change content, not shape. The
   user asked for "this style" because that shape already worked for them.
2. **Open the reference repo; do not guess it.** Find the title/start scene and the scripts
   that drive it; look at the actual background, logo and one sprite sheet. Name real file
   paths, fonts, sizes and motion numbers in the prompt ("sways 20 px over 4 s",
   "logo at 2x, nearest-neighbour"). A prompt that says "match the retro style" produces a
   redraw; one that names `art/backgrounds/park_arch.png` produces the asset.
3. **Check the target repo exists under the name given.** If the name does not match a
   folder or remote (`space-ball` vs `space-pinball`), say so and state the assumption in
   the prompt. Silently picking one sends the build to the wrong place.
4. **Licensing is a gate, not a footnote.** Grep the asset packs for ReadMe/licence files
   before listing them. A paid pack that forbids redistribution must not land in a public
   repo, however well it fits. Require a `CREDITS` file and a test that fails on any asset
   without an entry — the test is what keeps the rule true after the fifth asset is added.
5. **Fold in the reference repo's process lessons** (its `CLAUDE.md`, `AGENTS.md`,
   post-mortems): worktree isolation, a commit per module, screenshots that assert their
   subject is actually on screen, re-capture after every fix, measure before fixing,
   expensive gates once at the end. Those rules cost the first game real time; the new game
   should get them for free.
6. **Make every loop concrete.** "Iterate N times" needs its steps spelled out — capture →
   look → measure → fix → re-capture → commit → log — plus an explicit rule against
   inventing defects to hit the quota. Without that rule, pass 30 of 40 "fixes" something
   that was fine.
7. **Keep constraints, drop design.** Name what the agent cannot discover: asset paths,
   licences, gates, pass marks, platform and dependency rules, where it deploys. Leave
   numbers, module lists and file inventories to it — it will read the code better than a
   prompt can describe it, and a hard-coded list goes stale on the first refactor.
8. **Do not cite skills or tools the target repo lacks.** A `/skill` name or a local script
   means nothing in a fresh repo. Spell the process out in a few lines instead, or tell the
   agent to install it first.
9. **Deliver without writing into another repo.** Save the prompt to the scratchpad and
   show it inline; the user decides where it goes.

## Check before handing it over

- Every asset path in the prompt exists (`ls` each one) and has a licence you read.
- The target repo name was verified or the assumption is stated.
- No sentence depends on a skill, script or folder the new repo will not have.
- The prompt contains no design decisions you made up — only the reference's facts and the
  user's asks.
