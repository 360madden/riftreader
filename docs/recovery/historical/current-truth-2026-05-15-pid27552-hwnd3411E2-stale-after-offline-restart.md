# RiftReader Current Truth

_Last updated: 2026-05-15T03:20:52.926653Z._

## Verdict

**Coordinate proof is restored for the current RIFT process.** The active target is PID `27552` / HWND `0x3411E2`, and `ProofOnly` passed after promoting the current-PID proof anchor `api-family-hit-000001 @ 0x27B1ED850C0`.

Movement is no longer blocked by missing coordinate proof, but every movement run still needs exact target-control, proof-age/readback gates, and the profile-specific input safety gate.

## Current target and proof

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `27552` |
| HWND | `0x3411E2` |
| Window title | `RIFT` |
| Process start | `2026-05-15T01:11:57.750696Z` |
| Module base | `0x7FF71CD90000` |
| Target-control | `passed-target-control` / `exact-hwnd-foreground` |
| ProofOnly | `passed-proof-only` |
| Movement allowed by coord proof | `true` |
| Latest coordinate | `x=7325.35888671875, y=874.0448608398438, z=3053.77490234375` |
| Coordinate recorded | `2026-05-15T03:19:32.4433262Z` |

## Promoted proof anchor

| Field | Value |
|---|---|
| Candidate | `api-family-hit-000001` |
| Address | `0x27B1ED850C0` |
| Axis order | `xyz` |
| Candidate source | `scripts\captures\family-scan-currentpid-27552-20260515-022029-063377\api-family-vec3-candidates.jsonl` |
| Support poses | `4` |
| Movement pulses in recovery batch | `3` |
| Max API/readback abs delta | `0.004589843750181899` |
| Average planar readback distance | `0.0035424785720255003` |
| Promotion batch | `scripts\captures\current-pid-coordinate-anchor-batch-27552-factor-doc-20260514-222116\coordinate-anchor-batch-summary.json` |
| Proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| ProofOnly run | `scripts\captures\work-1-10-pid27552-refresh-20260514-231658\proofonly\live-test-ProofOnly-20260515-031659\run-summary.json` |
| Readback summary | `scripts\captures\proof-anchor-currentpid-27552-readback-summary-20260514-231748.json` |

## Recovery workflow just completed

| Step | Result | Artifact |
|---:|---|---|
| 1 | Kept stale PID `23496` pointer blocked and archived. | `docs\recovery\historical\current-proof-anchor-readback-2026-05-15-pid23496-hwnd2C1024-historical.json` |
| 2 | Verified exact live target PID/HWND/start/module and no debugger/RiftErrorHandler. | `scripts\captures\recovery-pid27552-factor-doc-20260514-221120\preflight\summary.json` |
| 3 | Passed target-control + visual gate at 640x360 client. | `scripts\captures\recovery-pid27552-factor-doc-20260514-221120\target-visual-gate\visual-gate-target-control-status.json` |
| 4 | Initial low-address broad scan timed out/blocked with no hits, so recovery pivoted to region inventory/scan-plan. | `scripts\captures\family-scan-currentpid-27552-20260515-021223-345938\family-scan-summary.json` |
| 5 | Built current-PID memory-region inventory and scan plan. | `scripts\captures\memory-region-inventory-currentpid-27552-20260515-021811-284049\summary.json` |
| 6 | Scanned current-PID plan ranges; found one API-near XYZ candidate in range rank 5. | `scripts\captures\coordinate-scan-plan-batch-currentpid-27552-20260515-022007-801670\summary.json` |
| 7 | Ran 4-pose displacement/readback batch with 3 bounded W pulses through C# SendInput ScanCode. | `scripts\captures\current-pid-coordinate-anchor-batch-27552-factor-doc-20260514-222116\coordinate-anchor-batch-summary.json` |
| 8 | Promoted the supported candidate and asserted readback. | `scripts\captures\proof-anchor-promote-currentpid-27552-20260514-223017\promotion-result.json` |
| 9 | Reran ProofOnly; passed with `movementSent=false`. | `scripts\captures\work-1-10-pid27552-refresh-20260514-231658\proofonly\live-test-ProofOnly-20260515-031659\run-summary.json` |
| 10 | Ran RiftScan milestone review; it is blocked only for provider-candidate consumption because this proof used a RiftReader-owned candidate file. | `scripts\captures\riftscan-milestone-review-20260515-023350.json` |
| 11 | Ran RiftScan coordination validation; quick no-CE/read-only suite passed. | `scripts\captures\riftscan-validation-20260515-023843.json` |


## Proof-gated movement smoke

| Field | Value |
|---|---|
| Profile | `Forward250` |
| Status | `passed` |
| Movement sent | `true` |
| Planar distance | `1.6640269674169994` |
| Spatial distance | `1.6747150196950644` |
| Final coordinate | `x=7325.35888671875, y=874.0448608398438, z=3053.77490234375` |
| Run summary | `scripts\captures\work-1-10-pid27552-forward250-20260514-231815\live-test-Forward250-20260515-031816\run-summary.json` |

## Historical / stale proof pointers

| Epoch | Candidate/address | Status | Reuse policy |
|---|---|---|---|
| PID `23496` / HWND `0x2C1024` | `api-family-hit-000005 @ 0x27236F46750` | Historical/stale after PID `27552` recovery. | Recovery evidence only; never current movement truth. |
| PID `16536` / HWND `0x1E0D66` | `snapshot-delta-21487DF8F64-xyz @ 0x21487DF8F64` | Historical/stale after game close. | Access-path/static-chain research seed only. |
| PID `2928` / HWND `0xC0994` | `api-family-hit-000001 @ 0x268E2BC09E0` | Historical/stale candidate-only lane. | Audit/history only. |

## Current caveats

- This is **current-PID proof**, not a restart-stable static pointer chain.
- The proof anchor is valid only while PID `27552` / HWND `0x3411E2` remains the same target epoch.
- SavedVariables were not used as live truth.
- x64dbg/CE were not used for this recovery.
- Static owner/source-chain provenance is still unresolved.
- `scripts/riftscan_milestone_review.py` blocked RiftScan-provider consumption with `no_supported_candidate_schema`; this is expected for a RiftReader-owned candidate-file recovery and does not contradict the same-target ProofOnly pass.

## Next required before movement profiles

1. Reconfirm exact PID/HWND target-control.
2. Reconfirm proof-anchor age/readback budget or rerun `ProofOnly` if stale.
3. Use only the current proof pointer for movement polling.
4. Keep stale PID `23496`, `16536`, and `2928` addresses historical-only.
5. Defer x64dbg/static-chain work unless the fast proof lane fails or owner provenance is explicitly requested.
