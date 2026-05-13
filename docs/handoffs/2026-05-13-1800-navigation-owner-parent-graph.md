# Handoff: owner parent graph confirms heap-terminal source lead

Generated: 2026-05-13 18:00 EDT / 2026-05-13 22:00 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`

## TL;DR

Navigation remains **blocked**, but the source-chain map is cleaner. The best
current coordinate lead is still:

```text
rift_x64.exe + 0x26AAE70
  -> owner 0x268D753AE30
  -> [owner + 0x10] = 0x268DF21ED20
```

The new sibling parent-graph comparison shows this owner pattern is
heap-terminal for all three low-noise type instances: each owner has exactly one
heap parent ref, and those parent refs have no parents. So the chain is better
understood, but still has **no static/root parent**.

## Current gate state

| Gate | State |
|---|---|
| Target | `rift_x64.exe` PID `2928`, HWND `0xC0994` |
| ProofOnly | `blocked-target-drift`; stale proof pointer PID `57656`, HWND `0x5417BC` |
| Movement/navigation | Blocked |
| Coordinate proof | Not promoted |
| CE/x64dbg | Not used in this slice |

## What changed in code

| File | Change |
|---|---|
| `scripts/rift_live_test/owner_type_parent_graph.py` | New offline artifact summarizer that combines owner/type inspection and pointer-family scan output into a parent graph. |
| `scripts/owner_type_parent_graph.py` | Thin CLI wrapper. |
| `scripts/test_owner_type_parent_graph.py` | Unit tests for terminal-candidate and parent-search-needed classification. |
| `docs/recovery/current-truth.md` | Updated with parent-graph comparison result. |

## New evidence

| Artifact | Result |
|---|---|
| `scripts/captures/pointer-family-scan-20260513-215713-171510/summary.json` | Scanned all three low-noise `rift_x64.exe+0x26AAE70` owner instances; each had exactly one heap parent ref and no parent-of-parent hits. |
| `scripts/captures/owner-type-parent-graph-20260513-215906-263575/summary.json` | Classified `0x268D753AE30` as `candidate-owner-heap-terminal`. |

## Parent graph

| Owner | Coord pointer | Parent ref | Parent-parent hits | Classification |
|---|---|---|---:|---|
| `0x268D753AE30` | `0x268DF21ED20` | `0x268D7539700` | `0` | `candidate-owner-heap-terminal` |
| `0x268923AF610` | `0x268992CBFB0` | `0x268E2A78628` | `0` | `type-instance-noncoord-or-zero` |
| `0x268C6A10EA0` | `0x268C148E060` | `0x268B0DD1168` | `0` | `coord-like-sibling` |

## Interpretation

| Finding | Meaning |
|---|---|
| Player-candidate owner is heap-terminal | Current exact pointer path stops at a heap parent ref, not a static root. |
| All sibling owners share the one-parent/no-grandparent pattern | The terminal heap-parent pattern is probably normal for this type family, not a unique static-chain clue. |
| Candidate owner remains low-noise and unique | Still the best source-chain seed for future proof-anchor recovery. |
| No module/static parent found | Do not promote; do not navigate. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\rift_live_test\owner_type_parent_graph.py scripts\owner_type_parent_graph.py scripts\test_owner_type_parent_graph.py` | Passed |
| `python scripts\test_owner_type_parent_graph.py -v` | Passed, `2/2` |
| `python scripts\owner_type_parent_graph.py --owner-summary-json ... --pointer-summary-json ... --json` | Passed; wrote parent-graph artifact. |
| `python scripts\navigation_resume_status.py --json` | Expected `blocked-for-live-input`; proof not promoted and ProofOnly still blocked. |
| `python scripts\riftscan_milestone_review.py --compact-json --write-summary --write-markdown` | Expected strategy-blocked result; wrote `scripts/captures/riftscan-milestone-review-20260513-220021.json`. |

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Navigation remains blocked
until same-target `ProofOnly` passes for PID `2928`, HWND `0xC0994`. Current best
source-chain lead is `rift_x64.exe+0x26AAE70 -> 0x268D753AE30 -> [owner+0x10] =
0x268DF21ED20`. Parent graph artifact
`scripts/captures/owner-type-parent-graph-20260513-215906-263575/summary.json`
shows the owner is heap-terminal: parent ref `0x268D7539700` has no parent refs.
Do not navigate or promote; continue looking for durable/static parent evidence
or rebuild proof through a safe broad-family method.

## Next best actions

| # | Action | Why |
|---:|---|---|
| 1 | Keep movement/navigation blocked. | `ProofOnly` is still stale-target blocked. |
| 2 | Preserve `0x268D753AE30 + 0x10 -> 0x268DF21ED20` as the best source-chain lead. | It is low-noise and uniquely tied to the stable family. |
| 3 | Stop expecting exact parent refs to climb directly from `0x268D7539700`. | Parent graph shows it is heap-terminal. |
| 4 | Search for manager/list ownership by structure or code access, not only pointer-to-pointer scans. | Exact pointer scans do not find the static root. |
| 5 | Use another broad movement-vector family snapshot only if more live evidence is needed. | Confirms tracking without narrow offset poking. |
| 6 | Keep `0x268BEF2C000` de-prioritized. | It failed repeat-readback stability. |
| 7 | Avoid identical x64dbg attach retries. | Previous attach attempts failed before attach. |
| 8 | Keep new graph summarizer in the loop after owner/type scans. | It reduces manual artifact scanning. |
| 9 | Run `navigation_resume_status.py` after proof-gate changes. | Keeps live-input gate honest. |
| 10 | Update handoff/current truth before any future live route attempt. | Prevents stale candidate evidence from being mistaken for proof. |
