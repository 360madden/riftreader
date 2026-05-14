# RiftReader handoff — current-PID coordinate proof restored

Generated: `2026-05-14T17:11:47Z`
Updated: `2026-05-14T21:03:41.227934Z`

## Current state override — newest

As of `2026-05-14T21:03:41.227934Z`, the active current coordinate proof target is PID `23496` / HWND `0x2C1024`, not PID `16536`. Candidate `api-family-hit-000005` at `0x27236F46750` passed same-target `ProofOnly` with `movementSent=false`. PID `16536` address `0x21487DF8F64` remains historical/stale only. Older sections below are chronological recovery history and may be superseded by this newest update.

<!-- PID16536_CLOSED_AFTER_X64DBG_UPDATE -->

## Update — game closed after x64dbg access capture

Updated: `2026-05-14T20:04:04Z`

The operator closed RIFT after the x64dbg access capture/logged-out close-only state. PID `16536` / HWND `0x1E0D66` and proof pointer `0x21487DF8F64` are now **historical/stale for movement and live coordinate truth**. The x64dbg access proof remains valuable recovery evidence only.

| Item | Status |
|---|---|
| Active RIFT process | `none observed` |
| Movement allowed | `false` |
| Current proof pointer | `blocked-target-closed-game-closed-after-x64dbg-capture` |
| Historical PID `16536` truth archive | `docs/recovery/historical/current-truth-2026-05-14-pid16536-hwnd1E0D66-closed-after-x64dbg.md` |
| Historical PID `16536` proof archive | `docs/recovery/historical/current-proof-anchor-readback-2026-05-14-pid16536-hwnd1E0D66-closed-after-x64dbg.json` |
| Decoded access proof | `scripts/captures/owner-access-path-21487DF8F64-currentpid-16536-decoded-access-20260514-1956/decoded-access-summary.json` |

Before any future movement or current-truth use: restart RIFT, get the character in-world, rediscover the exact target, and rerun fresh same-target `ProofOnly`.

## Verdict

Current restarted RIFT target has a refreshed coordinate proof anchor and a fresh same-target `ProofOnly` pass. PID `16536` / HWND `0x1E0D66` is the current coordinate proof target. PID `2928` / HWND `0xC0994` is historical/stale only.

Movement is proof-gated through the current pointer; RiftScan milestone review remains a strategy/read-only gate and does not independently grant movement. Before any new movement, re-check exact target and rerun `ProofOnly` if target identity or proof age is not fresh.

## Current target and proof pointer

| Field | Value |
|---|---|
| Status | `current-target-proofonly-passed` |
| Process | `rift_x64` PID `16536` |
| HWND | `0x1E0D66` |
| Process start | `2026-05-14T14:10:35.2003782Z` |
| Module base | `0x7FF71CD90000` |
| Candidate | `snapshot-delta-21487DF8F64-xyz` |
| Address | `0x21487DF8F64` |
| Candidate file | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/candidate-vec3.json` |
| Latest validation | `valid` |
| Movement allowed by proof pointer | `True` |
| Latest ProofOnly movement sent | `False` |
| No CE | `True` |

## Fresh validation

| Check | Result | Artifact |
|---|---|---|
| Latest ProofOnly | `passed-proof-only` | `scripts/captures/live-test-ProofOnly-20260514-174521/run-summary.json` |
| Target control | `passed-target-control` / `exact-hwnd-foreground` | `scripts/captures/live-test-ProofOnly-20260514-174521/target-control/target-control-status.json` |
| Current coordinate | `x=7404.44091796875, y=871.7135009765625, z=3028.63232421875` | `scripts/captures/proof-anchor-currentpid-16536-readback-summary-20260514-134617.json` |
| Coordinate recorded | `2026-05-14T17:46:22.1910144Z` | `scripts/captures/proof-anchor-currentpid-16536-readback-summary-20260514-134617.json` |
| RiftScan milestone review | `ready-for-read-only-proof` | `scripts/captures/riftscan-milestone-review-20260514-171113.json` |
| Review decision | `proceed-read-only-proof-first` | `scripts/captures/riftscan-milestone-review-20260514-171113.md` |

## Current-truth surfaces updated

| Surface | Status | Path |
|---|---|---|
| Human current truth | Updated to PID `16536` proof pointer | `docs/recovery/current-truth.md` |
| Machine current truth | Updated to PID `16536` proof pointer | `docs/recovery/current-truth.json` |
| Current proof pointer | Already promoted/current | `docs/recovery/current-proof-anchor-readback.json` |
| PID `2928` current-truth archive | Historical/stale | `docs/recovery/historical/current-truth-2026-05-14-pid2928-hwndC0994-historical.md` |
| PID `2928` current-truth JSON archive | Historical/stale | `docs/recovery/historical/current-truth-2026-05-14-pid2928-hwndC0994-historical.json` |
| PID `2928` proof-pointer archive | Historical/stale | `docs/recovery/historical/current-proof-anchor-readback-2026-05-14-pid2928-hwndC0994-historical.json` |

## Code/doc changes in this slice

| Area | Path |
|---|---|
| Current truth dashboard | `docs/recovery/current-truth.md` |
| Current truth machine payload | `docs/recovery/current-truth.json` |
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Historical stale PID `2928` current-truth archive | `docs/recovery/historical/current-truth-2026-05-14-pid2928-hwndC0994-historical.md` |
| Historical stale PID `2928` current-truth JSON archive | `docs/recovery/historical/current-truth-2026-05-14-pid2928-hwndC0994-historical.json` |
| Historical stale PID `2928` proof pointer archive | `docs/recovery/historical/current-proof-anchor-readback-2026-05-14-pid2928-hwndC0994-historical.json` |
| Current discovery tutorial | `docs/recovery/current-pid-coordinate-proof-anchor-discovery-2026-05-14.html` / `.md` |
| Historical discovery timelines | `docs/recovery/historical-coordinate-proof-anchor-discovery-timelines-2026-05.*` |

## Artifact anchors

| Artifact | Path |
|---|---|
| Clean coordinate proof route | `scripts/captures/coordinate-proof-route-20260514-163509-016518/coordinate-proof-route.json` |
| Promotion-ready batch | `scripts/captures/current-pid-coordinate-anchor-batch-16536-live-approved-route-20260514-163620/coordinate-anchor-batch-summary.json` |
| Prior live movement proof | `scripts/captures/live-test-Forward250-20260514-164220/run-summary.json` |
| Fresh ProofOnly | `scripts/captures/live-test-ProofOnly-20260514-174521/run-summary.json` |
| Proof readback summary | `scripts/captures/proof-anchor-currentpid-16536-readback-summary-20260514-134617.json` |
| RiftScan milestone review | `scripts/captures/riftscan-milestone-review-20260514-171113.json` |

## Validation commands for this recovery lane

- `python .\scripts\live_test.py --profile ProofOnly --pid 16536 --hwnd 0x1E0D66 --process-name rift_x64 --no-gui` -> latest `passed-proof-only` at `scripts/captures/live-test-ProofOnly-20260514-174521/run-summary.json`.
- `python .\scripts\riftscan_milestone_review.py ... --write-summary --write-markdown` -> `ready-for-read-only-proof`.
- `python -m unittest scripts.test_coordinate_candidate_compare scripts.test_manual_displacement_capture scripts.test_coordinate_proof_route scripts.test_current_proof_pointer scripts.test_promote_current_pid_proof_anchor_from_batch` -> `Ran 31 tests ... OK`.
- PowerShell parser check for `scripts\promote-current-pid-proof-anchor-from-batch.ps1` -> `parse-ok`.
- Current documentation update validation: `python -m json.tool docs/recovery/current-truth.json`, `python scripts/rift_live_test/current_truth_validator.py --truth-json docs/recovery/current-truth.json`, HTML parser checks for the discovery pages, and `git --no-pager diff --check`.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Start by reading this handoff, `docs/recovery/current-truth.md`, `docs/recovery/current-truth.json`, and `docs/recovery/current-proof-anchor-readback.json`. Treat PID `2928` / HWND `0xC0994` and older proof pointers as stale historical evidence only. Use current PID `16536` / HWND `0x1E0D66` only if the process epoch still matches; otherwise rerun current-PID family recovery. Before movement, rerun `ProofOnly` against the current target if target identity or proof age is not fresh. Do not use CE/x64dbg unless explicitly reauthorized.


<!-- PID23496_ACTIVE_BLOCKED_UPDATE -->

## Update — active post-close target found, proof still blocked

Updated: `2026-05-14T20:14:36Z`

Target discovery found active `rift_x64` PID `23496` / HWND `0x2C1024` after the close/restart sequence. Exact-HWND target-control passed, but `ProofOnly` blocked with target drift because the PID `16536` proof pointer had already been invalidated as stale. Movement remains blocked.

| Item | Status |
|---|---|
| Active target | PID `23496` / HWND `0x2C1024` |
| Target-control | `passed-target-control` |
| ProofOnly | `blocked-target-drift` |
| Movement allowed | `false` |
| ProofOnly artifact | `scripts/captures/post-close-proofonly-current-target-23496-20260514-2007/live-test-ProofOnly-20260514-200725/run-summary.json` |

Next recovery target is PID `23496` / HWND `0x2C1024` if it remains active. Reacquire/promote a same-target proof anchor, then rerun `ProofOnly` before movement.


---

## PID23496_FAST_PROOF_RESTORED_UPDATE — 2026-05-14T20:58:25Z

- Active target: PID `23496`, HWND `0x2C1024`.
- Fast proof lane restored coordinate proof without CE/x64dbg.
- Promoted candidate: `api-family-hit-000005` at `0x27236F46750`.
- Displacement support: 2 poses, max reference planar displacement `4.285970374371978`, max delta error `0.006023046874815918`.
- Readback assertion: `valid`, stable samples `3`, read failures `0`.
- ProofOnly: `passed-proof-only`, movement sent `false`.
- Current proof pointer: `docs/recovery/current-proof-anchor-readback.json`.
- ProofOnly run: `scripts/captures/fast-proof-lane-pid23496-proofonly-20260514-1654/live-test-ProofOnly-20260514-205441/run-summary.json`.
- Old PID `16536` pointer/address `0x21487DF8F64` remains historical/stale only.


---

## PID23496_DO_1_6_REFRESH_COMMIT_PUSH_UPDATE — 2026-05-14T21:03:41.227934Z

- Re-ran target-control before movement/proof use: `passed-target-control`, classification `exact-hwnd-foreground`.
- Re-ran same-target `ProofOnly`: `passed-proof-only`, movement sent `false`.
- Current anchor remains `api-family-hit-000005` at `0x27236F46750`, valid only for PID `23496` / HWND `0x2C1024`.
- PID `16536` address `0x21487DF8F64` remains historical/stale only.
- Latest ProofOnly run: `C:\RIFT MODDING\RiftReader\scripts\captures\do-1-6-pid23496-proofonly-20260514-170236\live-test-ProofOnly-20260514-210237\run-summary.json`.
- Latest readback summary: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-23496-readback-summary-20260514-170330.json`.
- This update is the commit/push readiness checkpoint for requested steps 1-6.
