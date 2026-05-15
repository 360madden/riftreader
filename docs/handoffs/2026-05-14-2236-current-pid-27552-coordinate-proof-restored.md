# Handoff — PID 27552 coordinate proof restored

Generated: `2026-05-15T02:37:34.800792Z`
Repo: `C:\RIFT MODDING\RiftReader`
Target: `rift_x64` PID `27552` / HWND `0x3411E2`

## TL;DR

Current coordinate proof has been reacquired and promoted for PID `27552`.
`ProofOnly` refreshed at `2026-05-15T03:17:54.890733+00:00` with `movementSent=false`, then `Forward250` passed with planar delta `1.6640269674169994`.
The current proof anchor is `api-family-hit-000001 @ 0x27B1ED850C0`.

## Current truth

| Field | Value |
|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Pointer status | `current-target-proofonly-passed` |
| Candidate | `api-family-hit-000001` |
| Address | `0x27B1ED850C0` |
| Support poses | `4` |
| Recovery movement pulses | `3` |
| Latest ProofOnly | `passed-proof-only` |
| Latest Forward250 smoke | `passed`, planar delta `1.6640269674169994` |
| Latest coordinate | `x=7325.35888671875, y=874.0448608398438, z=3053.77490234375` |
| No Cheat Engine | `true` |
| SavedVariables live truth | `false` |

## What changed in this recovery slice

1. Treated the PID `23496` proof pointer as stale for PID `27552`.
2. Verified live target identity and visual/target-control.
3. Ran the current-PID scan-plan path instead of old-address probing.
4. Found `api-family-hit-000001 @ 0x27B1ED850C0` in current PID memory.
5. Validated that same candidate across four poses with three bounded W pulses.
6. Promoted the candidate into the proof anchor/readback pointer.
7. Reran `ProofOnly`; it passed and updated `docs/recovery/current-proof-anchor-readback.json`.
8. Updated `docs/recovery/current-truth.md` and `docs/recovery/current-truth.json` to mark PID `27552` current.

## Evidence artifacts

| Purpose | Artifact |
|---|---|
| Target/debugger preflight | `scripts\captures\recovery-pid27552-factor-doc-20260514-221120\preflight\summary.json` |
| Target + visual gate | `scripts\captures\recovery-pid27552-factor-doc-20260514-221120\target-visual-gate\visual-gate-target-control-status.json` |
| Initial broad scan, no hit before time budget | `scripts\captures\family-scan-currentpid-27552-20260515-021223-345938\family-scan-summary.json` |
| Memory region inventory | `scripts\captures\memory-region-inventory-currentpid-27552-20260515-021811-284049\summary.json` |
| Scan-plan batch hit | `scripts\captures\coordinate-scan-plan-batch-currentpid-27552-20260515-022007-801670\summary.json` |
| Candidate file | `scripts\captures\family-scan-currentpid-27552-20260515-022029-063377\api-family-vec3-candidates.jsonl` |
| Multi-pose promotion batch | `scripts\captures\current-pid-coordinate-anchor-batch-27552-factor-doc-20260514-222116\coordinate-anchor-batch-summary.json` |
| Promotion result | `scripts\captures\proof-anchor-promote-currentpid-27552-20260514-223017\promotion-result.json` |
| Promotion readback assert | `scripts\captures\proof-anchor-promote-currentpid-27552-20260514-223017\proof-anchor-currentpid-27552-readback-summary-20260514-223020.json` |
| Latest ProofOnly | `scripts\captures\work-1-10-pid27552-refresh-20260514-231658\proofonly\live-test-ProofOnly-20260515-031659\run-summary.json` |
| Latest readback | `scripts\captures\proof-anchor-currentpid-27552-readback-summary-20260514-231748.json` |
| Forward250 smoke | `scripts\captures\work-1-10-pid27552-forward250-20260514-231815\live-test-Forward250-20260515-031816\run-summary.json` |
| RiftScan milestone review | `scripts\captures\riftscan-milestone-review-20260515-023350.json` |
| RiftScan coordination validation | `scripts\captures\riftscan-validation-20260515-023843.json` |

## Important interpretation notes

- The current proof is **movement-grade only through the same-PID/HWND proof pointer and ProofOnly gates**.
- The absolute address `0x27B1ED850C0` must become historical if RIFT restarts or PID/HWND changes.
- The previous addresses `0x27236F46750` and `0x21487DF8F64` are stale/historical only.
- The milestone review blocked RiftScan provider-candidate consumption because this run used a RiftReader-owned candidate file, not a RiftScan provider match. That is a coordination caveat, not a failed ProofOnly.
- Static owner/source-chain provenance remains unresolved.

## Resume prompt

```text
Resume RiftReader from docs/handoffs/2026-05-14-2236-current-pid-27552-coordinate-proof-restored.md. Current proof anchor is api-family-hit-000001 @ 0x27B1ED850C0 for PID 27552 / HWND 0x3411E2. First rerun exact target-control and ProofOnly if any time has passed. Do not use stale PID23496/PID16536 addresses as current truth. Work on movement/static-chain only after proof freshness is reconfirmed.
```
