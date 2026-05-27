# Current RIFT live truth — PID 12148 route smoke passed, x64dbg attach blocked

Updated UTC: `2026-05-27T06:56:25Z`
Repo: `C:\RIFT MODDING\RiftReader`

## Verdict

The current live target is **PID `12148` / HWND `0x640C0C`**. Current-PID coordinate recovery validated proof-anchor candidate `api-family-hit-000001` at `0x23863A26E50`; post-waypoint `ProofOnly` passed at `2026-05-27T06:36:08.616053+00:00` after a bounded observed-forward route smoke.

This is current proof-anchor and route-smoke truth for the live target. It is **not** player actor static-chain truth and does not promote a restart-stable actor resolver.

The bounded x64dbg access-provenance lane was approved and attempted after
no-attach readiness passed, but the `stop-context` attach failed before a debug
session started. Read-only target recovery then found an existing debug
object/debug port on PID `12148`, so x64dbg provenance remains blocked unless a
separate detach/`DebugActiveProcessStop` decision is approved.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Process start UTC | `2026-05-27T01:17:01.2653526Z` |
| Module base | `0x7FF77AF40000` |
| Proof anchor | `0x23863A26E50` |
| ProofOnly status | `passed-proof-only` |
| Latest coordinate | `X=7261.8330078125`, `Y=821.7017822265625`, `Z=3003.057861328125` |
| Coordinate recorded UTC | `2026-05-27T06:36:07.8790417Z` |

## Proof evidence

| Artifact | Path |
|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Post-waypoint ProofOnly run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-12148-20260527-0227\post-waypoint-proofonly\live-test-ProofOnly-20260527-063521\run-summary.json` |
| Proof-anchor readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-12148-readback-summary-20260527-023602.json` |
| Candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-12148-20260527-060224-849853\api-family-vec3-candidates.jsonl` |
| Movement validation batch | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-060019-832280/05-pose-batch-attempt-01-w-750ms/coordinate-anchor-batch-summary.json` |
| RiftScan milestone review | `scripts/captures/riftscan-milestone-review-20260527-065906.json` |

## Route/navigation smoke

| Field | Value |
|---|---|
| Status | `success` |
| Route type | `observed-forward-no-turn waypoint smoke` |
| Route file | `scripts/captures/navigation-smoke-currentpid-12148-20260527-0227/route/smoke-test-waypoints-2m-observed-forward.json` |
| Run summary | `scripts/captures/navigation-smoke-currentpid-12148-20260527-0227/route/navigate-waypoints-run-summary.json` |
| Movement backend | `native-window-message` |
| ForwardSeries3x250 result | `passed`, `3/3` pulses, planar `5.024164820532755` m |
| Initial route distance | `1.999999999999778` m |
| Final route distance | `0.32886291685124763` m |
| Pulse count | `1` |
| Stop reason | `arrived` |
| Visual frame change | ForwardSeries `35.5972%`; route smoke `27.9722%` |
| Post-smoke ProofOnly | `passed-proof-only`, no movement sent |

## Movement gate

| Field | Value |
|---|---|
| Gate | `allowed-current-target-proofonly-passed-route-smoke-passed` |
| Movement allowed by proof pointer | `true` |
| ForwardSeries movement sent | `true` |
| Waypoint smoke movement sent | `true` |
| Movement sent by post-smoke ProofOnly | `false` |
| Cheat Engine | `not used` |
| x64dbg/debugger attach | `attempted stop-context; failed before debug session` |
| SavedVariables live truth | `not used` |

Any new live movement still requires exact PID/HWND preflight and the normal live-input gate. The passed proof anchor and route smoke mean current-coordinate navigation is green for this process epoch only.

## Actor/static-chain status

| Item | Status |
|---|---|
| Actor static-chain resolver | `not promoted` |
| Static owner chain | `not restart-validated` |
| Current candidate role | `proof-anchor coordinate candidate only` |
| Navigation/route smoke after refresh | `passed` |
| x64dbg no-attach readiness | `passed` |
| x64dbg stop-context attach | `failed-before-debug-session` |
| Debug object/debug port | `present on PID 12148` |

## x64dbg attach evidence

| Evidence | Path |
|---|---|
| No-attach readiness packet | `scripts/captures/x64dbg-no-attach-readiness-packet-20260527-065241-005785/summary.json` |
| Attach environment probe | `scripts/captures/x64dbg-attach-environment-probe-20260527-065315-816903/summary.json` |
| Stop-context attempt summary | `scripts/captures/x64dbg-live-access-capture-20260527-065357-522442/summary.json` |
| Target recovery/debug-state summary | `scripts/captures/x64dbg-target-recovery-20260527-065545-618096/summary.json` |

Stop-context result:

- Attach command variants were rejected before debug session start:
  - `attach 0x2f74`
  - `attach 2f74`
  - `AttachDebugger 2f74`
- No breakpoint/watchpoint was set.
- No target memory was written.
- No game input or movement was sent.
- Post-attempt preflight still passed for PID `12148` / HWND `0x640C0C`.
- Read-only recovery reported `processDebugPort=0xFFFFFFFFFFFFFFFF`,
  `processDebugFlags=0`, `processDebugObjectHandle=0x250`, and
  `debuggerLikelyAttached=true`.

Current blockers:

- `actor-static-chain-not-promoted`
- `blocked-no-debugger-access-provenance`
- `x64dbg-attach-blocked-existing-debug-object`
- `no-static-resolver-promoted`
- `not-restart-validated-for-static-actor-chain`

## Historical superseded target

PID `28248` / HWND `0x2302BC` is historical-only and was superseded by the PID `12148` proof/route-smoke pass.

| Historical artifact | Path |
|---|---|
| Historical proof pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-proof-anchor-readback-2026-05-27-pid28248-hwnd2302BC-historical.json` |
| Historical current-truth JSON | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-truth-2026-05-27-pid28248-hwnd2302BC-historical-before-pid12148-proof-refresh.json` |
| Historical current-truth Markdown | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-truth-2026-05-27-pid28248-hwnd2302BC-historical-before-pid12148-proof-refresh.md` |

## Safety ledger for latest update

| Operation | Used? |
|---|---:|
| Fresh exact-target ProofOnly before movement | Yes |
| ForwardSeries3x250 observed-forward movement | Yes, bounded `3 x 250 ms` |
| 2m observed-forward waypoint smoke | Yes, arrived in `1` pulse |
| Post-waypoint ProofOnly | Yes, no movement sent |
| Current-truth doc/data update | Yes |
| Cheat Engine | No |
| x64dbg/debugger attach | Attempted, blocked before debug session |
| Breakpoints/watchpoints | No |
| Memory writes | No |
| Provider writes | No |
| Git push | No |

## Required next step

Route smoke is green. Keep the proof-anchor gate fresh before any further live
movement. Actor/static-chain recovery remains separate and is currently blocked
at x64dbg attach by the existing debug object/debug port. Ask before detaching
that debug object with `DebugActiveProcessStop`; otherwise continue no-debug
actor/static evidence work.
