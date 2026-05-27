# RiftReader handoff — PID 12148 ProofOnly passed; actor chain remains gated

Created local: `2026-05-27T02:18:00-04:00`
Created UTC: `2026-05-27T06:18:00Z`

## Direct result

Current-PID proof-anchor recovery succeeded for live RIFT target PID `12148` /
HWND `0x640C0C`.

The current proof pointer and current-truth docs now record a same-target
ProofOnly pass for candidate `api-family-hit-000001` at `0x23863A26E50`.

Actor/static-chain truth is still **not promoted**. The next actor-chain progress
requires either new static evidence or explicit approval for a bounded debugger
access-provenance step.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Title | `RIFT` |
| Process start UTC | `2026-05-27T01:17:01.2653526Z` |
| Module base | `0x7FF77AF40000` |
| Proof status | `current-target-proofonly-passed` |

## Proof anchor

| Field | Value |
|---|---|
| Candidate ID | `api-family-hit-000001` |
| Address | `0x23863A26E50` |
| Candidate file | `scripts/captures/family-scan-currentpid-12148-20260527-060224-849853/api-family-vec3-candidates.jsonl` |
| ProofOnly run | `scripts/captures/proofonly-currentpid-12148-20260527-0208/live-test-ProofOnly-20260527-061052/run-summary.json` |
| Proof readback | `scripts/captures/proof-anchor-currentpid-12148-readback-summary-20260527-021125.json` |
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Current truth JSON | `docs/recovery/current-truth.json` |
| Current truth Markdown | `docs/recovery/current-truth.md` |

## Validation summary

| Check | Result |
|---|---|
| Current-truth contract | passed |
| Coordinate recovery status | passed |
| Decision packet target epoch | `current` |
| RiftScan milestone review | `ready-for-read-only-proof` |
| Policy lint changed scope | passed |
| Diff hygiene | passed |
| Safe decision checks | internal validations passed; packet remains blocked only on actor/static-chain blockers |
| Actor-chain no-debug status | diagnostic passed; verdict `candidate-only-no-debug-root-blocked` |

## Commits made locally

| Commit | Purpose |
|---|---|
| `54b6a0b` | Document no-movement current-PID recovery lane |
| `748e2e6` | Record current PID 12148 recovery handoffs |
| `66738aa` | Refresh current proof truth for PID 12148 |

Branch state after the truth commit: `main...origin/main [ahead 3]`.
No push has been performed.

## Safety ledger

| Operation | Status |
|---|---|
| Bounded movement/displacement validation | used once, `w` 750 ms, approved |
| ProofOnly | passed, no movement sent |
| Cheat Engine | not used |
| x64dbg/debugger attach | not used |
| Breakpoints/watchpoints | not used |
| Memory writes | not used |
| Provider writes | not used |
| Git push | not used |

## Remaining blockers

| Blocker | Meaning |
|---|---|
| `actor-static-chain-not-promoted` | The current coordinate proof anchor is not an actor static-chain resolver. |
| `no-static-resolver-promoted` | No restart-stable actor/static resolver has been promoted. |
| `not-restart-validated-for-static-actor-chain` | Current proof is live-target proof, not restart-stable static-chain proof. |
| `route-navigation-smoke-not-run-after-current-proof-refresh` | No route/navigation smoke has been run after this proof refresh. |
| `actor-candidate-readback-not-passed` | No current actor-chain candidate readback exists in the no-debug status packet. |

## Recommended next gate

There are two useful next gates, depending on the desired lane:

| Gate | Requires approval | Why |
|---|---|---|
| Bounded route/navigation smoke | live input / movement | Tests whether the refreshed proof anchor supports the next live navigation workflow. |
| Bounded debugger access-provenance step | x64dbg/debugger | Needed to advance actor/static-chain provenance beyond proof-anchor evidence. |

Do not run either without explicit approval after a fresh exact-target preflight.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Keep PID `12148` / HWND `0x640C0C` as the only current target. | The proof pointer and current truth are now exact for this epoch. |
| 2 | Push the three local commits only if explicitly approved. | Remote mutation remains a separate gate. |
| 3 | If the goal is navigation, ask for a bounded route/navigation smoke gate next. | Current proof is green; route behavior still needs live validation. |
| 4 | If the goal is actor/static-chain truth, ask for one bounded debugger access-provenance step. | No-debug actor-chain status is blocked without access provenance. |
| 5 | Re-run exact target preflight before any live input or debugger attach. | Prevents PID/HWND drift. |
| 6 | Keep CE disabled. | The current lane succeeded without CE and policy remains no-CE by default. |
| 7 | Keep RiftScan read-only unless separately authorized. | Current milestone review is ready for read-only proof and no provider write is needed. |
| 8 | Do not treat `0x23863A26E50` as actor static-chain truth. | It is a proof-anchor coordinate candidate only. |
| 9 | Preserve PID `28248` archives as historical audit context. | They are useful reacquisition evidence but not current truth. |
| 10 | After any new code change, run targeted tests plus the strongest practical repo validation. | Required defensive programming / CI discipline. |
