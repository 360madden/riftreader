# RiftReader handoff — current-PID coordinate proof restored

Generated: `2026-05-14T17:11:47Z`

## Verdict

Current restarted RIFT target has a refreshed coordinate proof anchor and a fresh same-target `ProofOnly` pass. Movement is proof-gated again through the current pointer; RiftScan milestone review remains a strategy/read-only gate and does not independently grant movement.

## Current target and proof pointer

| Field | Value |
|---|---|
| Status | `current-target-proofonly-passed` |
| Process | `rift_x64` PID `16536` |
| HWND | `0x1E0D66` |
| Candidate | `snapshot-delta-21487DF8F64-xyz` |
| Address | `0x21487DF8F64` |
| Candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022\delta-analysis\candidate-vec3.json` |
| Latest validation | `valid` |
| Movement allowed by proof pointer | `True` |
| No CE | `True` |

## Fresh validation

| Check | Result | Artifact |
|---|---|---|
| ProofOnly | `passed-proof-only` | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260514-171030\run-summary.json` |
| Target control | `passed-target-control` | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260514-171030\target-control\target-control-status.json` |
| Current coordinate | `x=7404.1396484375, y=871.7135009765625, z=3028.680908203125` | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-16536-readback-summary-20260514-131103.json` |
| RiftScan milestone review | `ready-for-read-only-proof` | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260514-171113.json` |
| Review decision | `proceed-read-only-proof-first` | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260514-171113.md` |

## Code changes in this slice

| Area | Path |
|---|---|
| Snapshot-delta two-reference comparison | `scripts/rift_live_test/coordinate_candidate_compare.py` |
| Candidate readback compatibility fields | `scripts/current_pid_candidate_readback.py` |
| Promotion wrapper encoded-command splatting | `scripts/promote-current-pid-proof-anchor-from-batch.ps1` |
| Snapshot-delta regression | `scripts/test_coordinate_candidate_compare.py` |
| Promotion wrapper regression | `scripts/test_promote_current_pid_proof_anchor_from_batch.py` |
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Historical stale pointer archive | `docs/recovery/historical/current-proof-anchor-readback-2026-05-14-pid2928-hwndC0994-historical.json` |

## Artifact anchors

| Artifact | Path |
|---|---|
| Clean coordinate proof route | `scripts/captures/coordinate-proof-route-20260514-163509-016518/coordinate-proof-route.json` |
| Promotion-ready batch | `scripts/captures/current-pid-coordinate-anchor-batch-16536-live-approved-route-20260514-163620/coordinate-anchor-batch-summary.json` |
| Prior live movement proof | `scripts/captures/live-test-Forward250-20260514-164220/run-summary.json` |
| Fresh ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260514-171030\run-summary.json` |
| RiftScan milestone review | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260514-171113.json` |

## Validation commands run in this recovery lane

- `python .\scripts\live_test.py --profile ProofOnly --pid 16536 --hwnd 0x1E0D66 --process-name rift_x64 --no-gui` -> `passed-proof-only`.
- `python .\scripts\riftscan_milestone_review.py ... --write-summary --write-markdown` -> `ready-for-read-only-proof`.
- `python -m unittest scripts.test_coordinate_candidate_compare scripts.test_manual_displacement_capture scripts.test_coordinate_proof_route scripts.test_current_proof_pointer scripts.test_promote_current_pid_proof_anchor_from_batch` -> `Ran 31 tests ... OK`.
- PowerShell parser check for `scripts\\promote-current-pid-proof-anchor-from-batch.ps1` -> `parse-ok`.
- `git --no-pager diff --check` -> passed with LF/CRLF normalization warnings only.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Start by reading this handoff and `docs/recovery/current-proof-anchor-readback.json`. Treat old historical proof pointers as stale-only. Use current PID `16536` / HWND `0x1E0D66` only if the process epoch still matches; otherwise rerun current-PID family recovery. Before movement, rerun `ProofOnly` against the current target. Do not use CE/x64dbg unless explicitly reauthorized.
