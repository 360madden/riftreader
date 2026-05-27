# Current RIFT live truth — PID 12148 ProofOnly passed

Updated UTC: `2026-05-27T06:15:00Z`
Repo: `C:\RIFT MODDING\RiftReader`

## Verdict

The current live target is **PID `12148` / HWND `0x640C0C`**. Current-PID coordinate recovery found and validated proof-anchor candidate `api-family-hit-000001` at `0x23863A26E50`, then same-target `ProofOnly` passed at `2026-05-27T06:11:31Z`.

This is current proof-anchor truth for the live target. It is **not** player actor static-chain truth and does not promote a restart-stable actor resolver.

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
| Latest coordinate | `X=7260.705078125`, `Y=821.42822265625`, `Z=2996.458251953125` |
| Coordinate recorded UTC | `2026-05-27T06:11:30.5486225Z` |

## Proof evidence

| Artifact | Path |
|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| ProofOnly run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\proofonly-currentpid-12148-20260527-0208\live-test-ProofOnly-20260527-061052\run-summary.json` |
| Proof-anchor readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-12148-readback-summary-20260527-021125.json` |
| Candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-12148-20260527-060224-849853\api-family-vec3-candidates.jsonl` |
| Movement validation batch | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-060019-832280/05-pose-batch-attempt-01-w-750ms/coordinate-anchor-batch-summary.json` |
| Fast recovery summary | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-060019-832280/summary.json` |
| RiftScan milestone review | `scripts/captures/riftscan-milestone-review-20260527-061154.json` |

## Movement gate

| Field | Value |
|---|---|
| Gate | `allowed-current-target-proofonly-passed` |
| Movement allowed by proof pointer | `true` |
| Movement sent by ProofOnly | `false` |
| Movement sent by recovery validation | `true` |
| Cheat Engine | `not used` |
| x64dbg/debugger attach | `not used` |
| SavedVariables live truth | `not used` |

Any new live movement still requires exact PID/HWND preflight and the normal live-input gate. The passed proof anchor only means the current coordinate gate is no longer blocked by stale PID/HWND drift.

## Actor/static-chain status

| Item | Status |
|---|---|
| Actor static-chain resolver | `not promoted` |
| Static owner chain | `not restart-validated` |
| Current candidate role | `proof-anchor coordinate candidate only` |
| Navigation/route smoke after refresh | `not run` |

Current blockers:

- `actor-static-chain-not-promoted`
- `no-static-resolver-promoted`
- `not-restart-validated-for-static-actor-chain`
- `route-navigation-smoke-not-run-after-current-proof-refresh`

## Historical superseded target

PID `28248` / HWND `0x2302BC` is now historical-only and was superseded by the PID `12148` ProofOnly pass.

| Historical artifact | Path |
|---|---|
| Historical proof pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-proof-anchor-readback-2026-05-27-pid28248-hwnd2302BC-historical.json` |
| Historical current-truth JSON | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-truth-2026-05-27-pid28248-hwnd2302BC-historical-before-pid12148-proof-refresh.json` |
| Historical current-truth Markdown | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-truth-2026-05-27-pid28248-hwnd2302BC-historical-before-pid12148-proof-refresh.md` |

## Safety ledger for latest update

| Operation | Used? |
|---|---:|
| Current-PID movement validation | Yes, bounded `w` 750 ms before promotion |
| Same-target ProofOnly | Yes, no movement sent |
| Current-truth doc/data update | Yes |
| Cheat Engine | No |
| x64dbg/debugger attach | No |
| Memory writes | No |
| Provider writes | No |
| Git push | No |

## Required next step

Keep the proof-anchor gate green. If continuing live movement/navigation work, run exact-target preflight immediately before input and keep actor static-chain recovery separate from this proof-anchor candidate.
