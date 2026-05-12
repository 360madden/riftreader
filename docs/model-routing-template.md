---
document_type: model-routing-template
version: 2
as_of: 2026-05-12
---

# Assistant Model-Routing Template (Low-reasoning-first when safe)

Use this when classifying a task before deciding whether to use lower reasoning
or escalate.
For Codex sessions, also apply
`docs/workflow/codex-agent-routing-policy.md`: use lower reasoning only for
bounded, reversible, reviewable work; use subagents up to the practical maximum
for independent non-overlapping tasks; keep live/debugger/proof/truth and
commit/push decisions on the stronger main-agent path.

## 1) Fast task classification

| Item | Answer | Notes |
|---|---|---|
| Scope is docs/status/test-only only? | ☐ Yes / ☐ No | |
| Change is single-file, bounded, and reversible? | ☐ Yes / ☐ No | |
| No live-game/window side effects? | ☐ Yes / ☐ No | |
| Touches movement, forward-hold, coord-anchor proof, or addon validation? | ☐ Yes / ☐ No | |
| Requires reverse-engineering promotion / candidate selection? | ☐ Yes / ☐ No | |
| Touches x64dbg/CE/debugger attach, watchpoints, live process memory, or target control? | ☐ Yes / ☐ No | |
| Can be split into independent read-only or disjoint file-ownership subagents? | ☐ Yes / ☐ No | |
| Would subagents risk overlapping edits, duplicated analysis, or competing live actions? | ☐ Yes / ☐ No | |
| Evidence is clear and non-contradictory? | ☐ Yes / ☐ No | |

## 2) Routing decision

- If **all green checks except risk checks** are “Yes” and all red-risk checks are “No” → `spark`.
- If any red-risk check is “Yes” or any answer is uncertain → `gpt-5.4`.
- If independent read-only or disjoint implementation subtasks exist → spawn
  subagents up to the practical maximum, with explicit scope and file ownership.
- If the next step is the critical-path blocker → keep it local in the main
  agent unless delegation can run in parallel without blocking.

Red-risk checks (hard-blocks for spark):
- Live movement logic
- Anchor/proof migration or watchset promotions
- Multi-file behavioral refactor
- Conflicting or unproven evidence
- High-risk branch merges or broad architecture changes
- x64dbg/CE live attach, debugger control, target selection, coordinate/facing
  truth promotion, and commit/push review

## 3) Safety notes (paste into notes)

- Rollback target: what file(s) should be reverted if this changes behavior?
- Validation plan: what build/test command proves non-regression?
- Escalation trigger: what observed failure moves the task to higher model?

## 4) Required post-routing evidence

- Commands run (if any)
- Files changed
- Validation performed (build/test/dry-run)
- Decision log (why spark or `gpt-5.4` was chosen)
- Subagents spawned, their scope, and how their output was integrated, when
  applicable

## 5) Optional top 5 next actions

Only fill if needed:

1. Verify changed files in a minimal patch.
2. Run targeted validation.
3. Promote/rollback if no measurable improvement.
4. Update relevant handoff/truth docs only when state changes.
5. Leave only evidence-backed changes in `main`.
