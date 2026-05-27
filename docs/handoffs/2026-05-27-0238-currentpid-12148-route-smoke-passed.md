# RiftReader handoff — PID 12148 observed-forward route smoke passed

Created local: `2026-05-27T02:38:00-04:00`
Created UTC: `2026-05-27T06:38:00Z`

## Direct result

Live target `rift_x64` PID `12148` / HWND `0x640C0C` is current-session movement/navigation green for the bounded no-turn observed-forward lane.

The run sequence was: fresh exact-target `ProofOnly` → `ForwardSeries3x250` → fresh post-series `ProofOnly` → 2m observed-forward route build → read-only route checks → bounded `navigate-waypoints` smoke → post-waypoint `ProofOnly`.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Title | `RIFT` |
| Process start UTC | `2026-05-27T01:17:01.2653526Z` |
| Proof anchor | `api-family-hit-000001` at `0x23863A26E50` |
| Current coordinate | `X=7261.8330078125`, `Y=821.7017822265625`, `Z=3003.057861328125` |
| Coordinate timestamp | `2026-05-27T06:36:07.8790417Z` |

## Live route-smoke evidence

| Check | Result |
|---|---|
| Pre-navigation ProofOnly | `passed-proof-only`, no movement sent |
| ForwardSeries3x250 | `passed`, `3/3` pulses, planar `5.024164820532755` m |
| Post-series ProofOnly | `passed-proof-only`, no movement sent |
| Route plan | one 2m segment; initial distance `1.999999999999778` m |
| Read-only current check | anchor source `coord-trace-anchor`, outside arrival radius before movement |
| Waypoint smoke | `success`, stop reason `arrived`, pulse count `1` |
| Final route distance | `0.32886291685124763` m |
| Movement backend | `native-window-message` |
| Post-waypoint ProofOnly | `passed-proof-only`, no movement sent |
| RiftScan milestone review | `ready-for-read-only-proof` |

## Key artifacts

| Artifact | Path |
|---|---|
| Current truth JSON | `docs/recovery/current-truth.json` |
| Current truth Markdown | `docs/recovery/current-truth.md` |
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Pre-navigation ProofOnly | `scripts/captures/navigation-smoke-currentpid-12148-20260527-0227/pre-proofonly/live-test-ProofOnly-20260527-062748/run-summary.json` |
| ForwardSeries3x250 | `scripts/captures/navigation-smoke-currentpid-12148-20260527-0227/forward-series/live-test-ForwardSeries3x250-20260527-062854/run-summary.json` |
| Post-series ProofOnly | `scripts/captures/navigation-smoke-currentpid-12148-20260527-0227/post-series-proofonly/live-test-ProofOnly-20260527-063304/run-summary.json` |
| Route file | `scripts/captures/navigation-smoke-currentpid-12148-20260527-0227/route/smoke-test-waypoints-2m-observed-forward.json` |
| Waypoint smoke summary | `scripts/captures/navigation-smoke-currentpid-12148-20260527-0227/route/navigate-waypoints-run-summary.json` |
| Post-waypoint ProofOnly | `scripts/captures/navigation-smoke-currentpid-12148-20260527-0227/post-waypoint-proofonly/live-test-ProofOnly-20260527-063521/run-summary.json` |
| RiftScan milestone review | `scripts/captures/riftscan-milestone-review-20260527-063740.json` |

## Safety ledger

| Operation | Status |
|---|---|
| Exact PID/HWND binding | passed for PID `12148` / HWND `0x640C0C` |
| Live movement/input | approved; bounded to observed-forward and waypoint smoke |
| Cheat Engine | not used |
| x64dbg/debugger attach | not used |
| Breakpoints/watchpoints | not used |
| SavedVariables as live truth | not used |
| Provider writes | not used |
| Git push | not used |

## Remaining blockers

| Blocker | Meaning |
|---|---|
| `actor-static-chain-not-promoted` | The current coordinate proof anchor is not an actor static-chain resolver. |
| `no-static-resolver-promoted` | No restart-stable actor/static resolver has been promoted. |
| `not-restart-validated-for-static-actor-chain` | Current proof is live-target proof, not restart-stable static-chain proof. |

## Recommended next gate

The useful next gate depends on the lane:

| Gate | Requires approval | Why |
|---|---|---|
| Longer/route-chain navigation smoke | live input / movement | Expands from a 2m no-turn pass to a stronger navigation proof. |
| Bounded debugger access-provenance step | x64dbg/debugger | Needed to advance actor/static-chain provenance beyond proof-anchor evidence. |
| Push local commits | remote mutation | Local branch is ahead of origin and should be published only with explicit approval. |

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Keep PID `12148` / HWND `0x640C0C` as the only current target. | All fresh proof and route-smoke evidence is exact for that epoch. |
| 2 | Commit this route-smoke truth update after validation. | The local docs should match the live milestone. |
| 3 | Push local commits only if explicitly approved. | Remote mutation remains a separate gate. |
| 4 | For more navigation confidence, run a longer no-turn or route-chain smoke after fresh ProofOnly. | The 2m waypoint smoke is green but still a bounded first pass. |
| 5 | Keep actor/static-chain recovery separate. | The proof anchor is not a restart-stable actor resolver. |
| 6 | If actor truth is the goal, ask for one bounded debugger access-provenance step. | No-debug actor-chain status remains blocked. |
| 7 | Re-run exact target preflight before any further input. | Prevents PID/HWND drift. |
| 8 | Keep CE disabled. | The current proof and route lane succeeded without CE. |
| 9 | Keep RiftScan read-only unless separately authorized. | Current evidence came from RiftReader-owned artifacts and explicit candidate files. |
| 10 | Preserve all generated capture artifacts as ignored evidence. | They are needed for handoff/resume but should not be staged wholesale. |
