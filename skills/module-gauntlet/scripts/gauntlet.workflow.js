export const meta = {
  name: 'module-gauntlet',
  description: 'Build modules one after another: builder in a worktree, critic merges and scores out of 10, revise to the pass mark, gatekeeper runs the gates and commits; optional screenshot validation loop and final gate',
  whenToUse: 'A plan says "one module per workflow", "critic scores out of 10", "revise until 8.5", "gate and commit", or a batch of feedback needs several small modules built against a written contract',
  phases: [{ title: 'Build' }, { title: 'Score' }, { title: 'Revise' }, { title: 'Gate' }, { title: 'Validate' }, { title: 'Final' }],
}

// Everything project-specific comes in through `args`; see SKILL.md for the full shape.
// Required: repo, branch, modules[{ name, paths, spec }]. Nothing here is hard-coded to a repo.
const A = args || {}
for (const k of ['repo', 'branch', 'modules']) if (!A[k]) throw new Error(`module-gauntlet: args.${k} is required`)
if (!Array.isArray(A.modules) || !A.modules.length) throw new Error('module-gauntlet: args.modules must be a non-empty array')

const REPO = A.repo
const BRANCH = A.branch
const PRODUCT = A.product || 'the project'
const CONTRACT = A.contract || 'ARCHITECTURE.md'
const STATUS = A.statusFile || 'docs/STATUS.json'
const PASS = A.pass ?? 8.5
const MAX_REVISE = A.maxRevise ?? (A.modules.length > 1 ? 2 : 4)
const VAL_PASSES = A.valPasses ?? 0
const GATES = A.gates || ['npm test']
const BAR = A.bar || `the best shipped work in ${PRODUCT}'s category`
const TRAILER = A.trailer ? `\nEnd the commit message with these trailer lines:\n${A.trailer}` : ''
const gateList = (extra) => [...GATES, ...(extra || [])].map((g) => `\`${g}\``).join(', ')

const common = (paths) => `Repo: ${REPO} (branch ${BRANCH}; never touch or push the default branch). Read ${CONTRACT} (the binding contract), ${STATUS} and \`git status\` first; treat uncommitted leftovers as evidence to check, not work to trust. ${A.conventions || ''}
Touch ONLY these paths: ${paths.join(', ')}. Keep files under 500 lines (split one you push over). Every new test must be proven by a mutation: remove or break the fix, show the test go red, restore — report the mutation. If the contract is wrong or missing something, do NOT edit ${CONTRACT}; record it as an assumption in your return.`

const visualFor = (M, dir) => (A.visual && M.visual !== false)
  ? `\nVISUAL CHECK (save output under ${dir}): ${A.visual}\nOpen the images with the Read tool and LOOK at them. Zero console errors is a pass requirement.`
  : ''

const FIND = { type: 'object', properties: {
  score: { type: 'number' },
  findings: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, severity: { type: 'string', enum: ['high', 'medium', 'low'] },
    issue: { type: 'string' }, fix: { type: 'string' }, status: { type: 'string', enum: ['open', 'fixed', 'stale'] },
  }, required: ['id', 'severity', 'issue', 'fix', 'status'] } },
  disproved: { type: 'array', items: { type: 'string' } },
  consoleErrors: { type: 'number' },
  gatesPass: { type: 'boolean' },
}, required: ['score', 'findings', 'disproved', 'gatesPass'] }

const results = []
let carryLows = []

for (const M of A.modules) {
  const C = common(M.paths)
  const spec = M.spec + (carryLows.length
    ? `\nOPEN LOWS FROM THE PREVIOUS MODULE (close the ones inside your paths, leave the rest):\n${JSON.stringify(carryLows, null, 1)}`
    : '')

  phase('Build')
  const built = await agent(`You are the BUILDER for module "${M.name}" of ${PRODUCT}, in your own isolated git worktree (a copy of ${BRANCH}; paths are relative to your worktree root, not ${REPO}). ${C}

MODULE SPEC (the definition of done):
${spec}

Run the gates until green: ${gateList()} (failures outside your paths are not yours — note them).${visualFor(M, `${M.name}-build`)}
FINALLY: \`git add\` only your paths and commit "feat(${M.name}): ..." inside the worktree.${TRAILER}
Return: the commit SHA (\`git rev-parse HEAD\`), the branch name, a summary, every measurement the spec asks for, the mutation proofs, and any assumptions or contract gaps.`,
  { label: `build:${M.name}`, phase: 'Build', isolation: 'worktree' })

  const scorePrompt = (round) => `You are the CRITIC for module "${M.name}" of ${PRODUCT} (round ${round}). Work in ${REPO}. ${C}
${round === 0
  ? `FIRST: the builder committed in a worktree. Its report:\n---\n${built}\n---\nMerge that commit into ${BRANCH} in ${REPO} (\`git merge --no-edit <sha>\`; if the SHA is missing, find the builder's branch with \`git worktree list\` / \`git branch -a\`). Resolve nothing outside ${M.paths.join(', ')}. Then review.`
  : 'Review the current tree, uncommitted revise changes included.'}

MODULE SPEC:
${spec}

Re-check every finding already recorded for this module in ${STATUS} against the current tree and mark each fixed/open/stale. Run ${gateList()}.${visualFor(M, `${M.name}-critic-${round}`)}
Score the module out of 10 against ${BAR} (for non-visual work: correctness, contract conformance, determinism, test depth, edge cases, hot-path cost, readability). Pass = >= ${PASS} with every gate green. Be demanding, but report only real defects you verified; list suspicions that measurement DISPROVED under "disproved" so nobody "fixes" them. Give findings stable ids "${M.name}-N". If the spec names a before/after measurement, compare it to the baseline, not to a floor the builder chose. Then write this module's ${STATUS} entry (score, rounds=${round + 1}, findings, disproved, status "scored") — edit only that entry and keep the file's existing JSON style. Do not edit module source.`

  phase('Score')
  let crit = await agent(scorePrompt(0), { label: `score:${M.name}:0`, phase: 'Score', schema: FIND })
  let round = 0
  const blocking = (c) => c.findings.filter((f) => f.status === 'open' && (f.severity !== 'low' || c.score < PASS))
  const needsWork = (c) => c && (c.score < PASS || !c.gatesPass || blocking(c).length > 0)
  while (needsWork(crit) && round < MAX_REVISE) {
    round++
    const open = blocking(crit)
    log(`${M.name}: score ${crit.score}, ${open.length} to fix — revise ${round}/${MAX_REVISE}`)
    await agent(`You are the BUILDER for module "${M.name}", revising (round ${round}) in ${REPO}. ${C}
MODULE SPEC:
${spec}
Fix ONLY these open critic findings, each with a regression test proven by mutation. Do NOT "fix" these disproved suspicions: ${JSON.stringify(crit.disproved)}
${JSON.stringify(open, null, 1)}
Gates currently failing: ${!crit.gatesPass}. Keep ${gateList()} green.${visualFor(M, `${M.name}-rev-${round}`)}
Do not commit. Return what you changed per finding id, with the mutation proofs.`,
    { label: `revise:${M.name}:${round}`, phase: 'Revise' })
    crit = await agent(scorePrompt(round), { label: `score:${M.name}:${round}`, phase: 'Score', schema: FIND })
  }

  phase('Gate')
  const passed = !!crit && crit.score >= PASS && crit.gatesPass
  const score = crit ? crit.score : 'n/a'
  const gate = await agent(`You are the GATEKEEPER for module "${M.name}" in ${REPO} on ${BRANCH}. Run and record: ${gateList(M.extraGates)}. Update this module's ${STATUS} entry: status ${passed ? '"passed"' : '"blocker"'} (final score ${score} after ${round} revise rounds), gatesNotRun = every gate that did not actually run, with the reason${passed ? '' : ', and the measurement that keeps it failing under "blockers"'}.
If every gate is green, \`git add\` the module paths (${M.paths.join(', ')}) plus ${STATUS} and commit "chore(${M.name}): gate — score ${score}".${TRAILER}
If a gate is red, do NOT commit; say why. Remove the builder's leftover worktree and branch for this module (\`git worktree list\`), but only after \`git merge-base --is-ancestor <sha> HEAD\` shows its commit is merged. Return: gate results, commit SHA or the reason there is none, and the worktree cleanup result.`,
  { label: `gate:${M.name}`, phase: 'Gate' })

  carryLows = crit ? crit.findings.filter((f) => f.status === 'open') : []
  results.push({ module: M.name, finalScore: crit && crit.score, rounds: round, passed, open: carryLows, disproved: crit && crit.disproved, gate })
  log(`${M.name}: ${passed ? 'PASSED' : 'BLOCKER'} at ${score}`)
}

// Optional screenshot validation loop: each pass fixes exactly three things and sees what the
// earlier passes did, so passes neither repeat nor undo each other.
const valDone = []
if (VAL_PASSES > 0 && A.visual) {
  phase('Validate')
  const VAL = { type: 'object', properties: {
    improvements: { type: 'array', items: { type: 'object', properties: {
      what: { type: 'string' }, evidence: { type: 'string' }, done: { type: 'boolean' },
    }, required: ['what', 'evidence', 'done'] } },
    commit: { type: 'string' }, gatesGreen: { type: 'boolean' },
  }, required: ['improvements', 'commit', 'gatesGreen'] }
  const carried = JSON.stringify(results.flatMap((r) => r.open || [])).slice(0, 3000)
  const valPaths = A.validatePaths || A.modules.flatMap((m) => m.paths).concat(STATUS)
  for (let i = 1; i <= VAL_PASSES; i++) {
    const v = await agent(`VALIDATION LOOP pass ${i}/${VAL_PASSES} for ${PRODUCT}, in ${REPO} on ${BRANCH}. ${common([...new Set(valPaths)])}
${visualFor({}, `val-${i}`)}
Find exactly 3 concrete improvements ${BAR} would have${A.valFocus ? `, prioritising: ${A.valFocus}` : ''}. Also eligible: these open lows from the modules: ${carried}.
Already done in earlier passes (do not repeat or undo): ${JSON.stringify(valDone)}.
Implement all 3 as small, cohesive changes with tests for anything testable. Never add a feature or mechanic nobody asked for, and never invent a defect to fill the quota — if there are fewer than 3 real ones, say so. Gate: ${gateList()}. If green, commit "polish(val-${i}): <the 3 items>".${TRAILER}
A change that cannot be made green is reverted and marked done=false. Return the 3 improvements with before/after evidence (image paths), the commit SHA, and gatesGreen.`,
    { label: `validate:${i}`, phase: 'Validate', schema: VAL })
    if (v) valDone.push(...v.improvements.filter((x) => x.done).map((x) => x.what))
    log(`validation ${i}: ${v ? v.improvements.filter((x) => x.done).length : 0}/3 done`)
  }
}

let final = null
if (A.finalGate) {
  phase('Final')
  final = await agent(`FINAL GATE for ${PRODUCT} in ${REPO} on ${BRANCH}. Run and record: ${gateList(A.finalGate.gates)}. Security review of this branch's diff against the default branch (\`git diff <default>...HEAD\`): injection, unescaped dynamic text into HTML, unguarded storage or parsing, path traversal, secrets in the diff, missing authorization checks. Run the package audit and fix vulnerable packages.
Completeness critic: re-read ${CONTRACT} and the user's asks${A.finalGate.asks ? ` (${A.finalGate.asks})` : ''}; for each, cite the screenshot or test that proves it, or say plainly that it is unproven.
Record the results in ${STATUS}${A.date ? ` dated ${A.date}` : ''} and commit "docs: final gate" only when green.${TRAILER}
\`git worktree list\` must show only the main tree afterwards (remove leftovers only after checking they are merged). Return a concise report: gate results, per-ask proof, security notes, remaining lows.`,
  { label: 'final-gate', phase: 'Final' })
}

return { results, validation: valDone, final }
