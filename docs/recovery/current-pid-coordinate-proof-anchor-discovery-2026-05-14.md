# Current-PID coordinate proof anchor discovery workflow — 2026-05-14

Generated: `2026-05-14T17:54:32Z`
Repo: `C:\RIFT MODDING\RiftReader`
Branch/commit at time of writing: `main` / `3c452a0 Restore current-pid coordinate proof promotion`

## Purpose

This document records the precise successful workflow that rediscovered and promoted the current player coordinate proof anchor after the local PC/RIFT client restart changed the live process epoch. It is intentionally detailed so a future recovery can repeat the proven path without falling back to stale pointers, weak single-pose heuristics, or broad debugger/watchpoint fishing.

## Final verdict

| Field | Value |
|---|---|
| Current proof pointer status | `current-target-proofonly-passed` |
| Current process | `rift_x64` PID `16536` |
| Current HWND | `0x1E0D66` |
| Candidate ID | `snapshot-delta-21487DF8F64-xyz` |
| Coord address | `0x21487DF8F64` |
| Coord layout | `X +0`, `Y +4`, `Z +8` |
| Source base / offset | `0x21487DF0000` + `0x8F64` |
| Candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022\delta-analysis\candidate-vec3.json` |
| Latest validation | `valid` |
| Movement gate | `True` |
| Latest ProofOnly | `passed-proof-only` |
| Proof support count | `5` |
| No Cheat Engine | `True` |
| SavedVariables used as live truth | `False` |

The discovered anchor is current-process truth for PID `16536` / HWND `0x1E0D66`. It is **not** a restart-safe static chain. If RIFT restarts or PID/HWND changes, archive this pointer as stale and rerun current-PID recovery.

## Safety and boundary conditions used

| Boundary | Applied behavior |
|---|---|
| Old pointer after restart | Treated as stale and archived under `docs/recovery/historical/current-proof-anchor-readback-2026-05-14-pid2928-hwndC0994-historical.json`. |
| Cheat Engine / x64dbg | Not used in this successful no-CE recovery path. |
| SavedVariables | Not accepted as live coordinate truth. |
| Live movement | Only sent after exact PID/HWND targeting and proof gates; movement was bounded. |
| RiftScan | Used as evidence/readback provider only; RiftReader remained the proof/movement gate. |
| Promotion rule | Candidate evidence stayed candidate-only until multi-pose same-PID proof and `ProofOnly` passed. |

## Discovery chain at a glance

| Stage | Evidence | Verdict |
|---|---|---|
| Target preflight | PID `16536`, HWND `0x1E0D66` | Exact live target selected. |
| Fresh API truth | `RRAPICOORD1`/RIFT API reference captures | Fresh live coordinate surface available. |
| Full family snapshots | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/summary.json` | `status=passed`, 3 explicit scan ranges. |
| Delta analysis | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/delta-summary.json` | `candidateCount=32`, `familyCount=2`, `cleanCandidateCount=32`. |
| Best candidate | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/candidate-vec3.json` | `snapshot-delta-21487DF8F64-xyz` at `0x21487DF8F64`. |
| API/memory proof route | `scripts/captures/coordinate-proof-route-20260514-163509-016518/coordinate-proof-route.json` | `status=api-memory-match`, selected candidate `snapshot-delta-21487DF8F64-xyz` at `0x21487DF8F64`. |
| Promotion batch | `scripts/captures/current-pid-coordinate-anchor-batch-16536-live-approved-route-20260514-163620/coordinate-anchor-batch-summary.json` | `status=promotion-candidate-found`, captured poses `3`, movement pulses `2`. |
| Proof pointer | `docs/recovery/current-proof-anchor-readback.json` | `status=current-target-proofonly-passed`. |
| Latest ProofOnly | `scripts/captures/live-test-ProofOnly-20260514-174521/run-summary.json` | `status=passed-proof-only`, movement sent `False`. |
| Live movement smoke | `scripts/captures/live-test-Forward250-20260514-164220/run-summary.json` | `status=passed`, planar delta `0.3315185178299767`. |

## Step-by-step successful workflow

### 1. Block the stale pointer first

After the local PC/game restart, the previously promoted proof pointer was no longer current. The recovery started by treating the older pointer as `blocked-target-drift` / historical-only and preserving it at:

```text
docs/recovery/historical/current-proof-anchor-readback-2026-05-14-pid2928-hwndC0994-historical.json
```

Do **not** reuse stale fields such as old `candidateId`, `matchFile`, absolute address, or `movementAllowed=true` from a different PID/HWND except as broad historical hints.

### 2. Resolve the current exact target

The current target used for the successful recovery was:

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `16536` |
| HWND | `0x1E0D66` |
| Window title | `RIFT` |
| Client size during recovery | `640x360` |

The family snapshot preflight used exact target checks and verified no debugger process was attached before scanning.

### 3. Use fresh API/runtime coordinate truth

The successful workflow used the live `RRAPICOORD1` / RIFT API coordinate surface, not SavedVariables. In the family snapshot run, the reference source was:

```text
referenceSource: rrapicoord
```

Example baseline reference from the winning candidate:

| Axis | API/reference | Memory candidate |
|---|---:|---:|
| X | `7408.02` | `7408.01953125` |
| Y | `871.78` | `871.7153930664062` |
| Z | `3029.01` | `3029.012939453125` |

Example displaced reference:

| Axis | API/reference | Memory candidate |
|---|---:|---:|
| X | `7413.8696` | `7413.86669921875` |
| Y | `871.78` | `871.7219848632812` |
| Z | `3027.03` | `3027.03369140625` |

### 4. Scan/decode entire targeted family groups

The successful family-snapshot sequence used full grouped family ranges instead of narrow offset probing. The selected ranges were:

| Segment | Label | Source | Size bytes | Displaced changed bytes | Passive changed bytes |
|---|---|---|---:|---:|---:|
| `0X21487DE0000-0X21487DF0000` | `primary-transform-family-21487DF-nearby` | `explicit-current-lead` | `65536` | `37` | `0` |
| `0X21487DF0000-0X21487E00000` | `primary-transform-family-21487DF-nearby` | `explicit-current-lead` | `65536` | `56` | `0` |
| `0X21487E00000-0X21487E10000` | `primary-transform-family-21487DF-nearby` | `explicit-current-lead` | `65536` | `253` | `0` |
| `0XB655958000-0XB655970000` | `secondary-dense-family-B655958-nearby` | `explicit-current-lead` | `98304` | `14845` | `0` |
| `0X214808C0000-0X214808D0000` | `negative-control-demoted-214808D-nearby` | `explicit-control` | `65536` | `175` | `0` |
| `0X214808D0000-0X214808E0000` | `negative-control-demoted-214808D-nearby` | `explicit-control` | `65536` | `2763` | `0` |
| `0X214808E0000-0X214808F0000` | `negative-control-demoted-214808D-nearby` | `explicit-control` | `65536` | `0` | `0` |

Key points:

- Primary transform-like family: `0x21487D00000` / page `0x21487DF8000`.
- Secondary dense family was scanned as a secondary lead, but the primary family won by displacement tracking.
- The negative control family was included to avoid overpromoting general memory churn.
- The scan used multi-pose deltas and candidate ranking, not a single coordinate snapshot.

### 5. Rank by displacement tracking, not one-pose closeness

The winning candidate:

| Field | Value |
|---|---|
| Candidate | `snapshot-delta-21487DF8F64-xyz` |
| Absolute address | `0x21487DF8F64` |
| Family base | `0x21487D00000` |
| Page | `0x21487DF8000` |
| Segment base | `0x21487DF0000` |
| Segment offset | `0x8F64` |
| Axis order | `xyz` |
| Classification at this stage | `current-pid-family-snapshot-delta-triplet` |
| Truth readiness at this stage | `candidate_only_not_movement_proof` |

Delta tracking metrics:

| Metric | Value |
|---|---:|
| API delta dx | `5.849599999999555` |
| API delta dy | `0.0` |
| API delta dz | `-1.9800000000000182` |
| API planar delta | `6.175614962090404` |
| Memory delta dx | `5.84716796875` |
| Memory delta dy | `0.006591796875` |
| Memory delta dz | `-1.979248046875` |
| Memory planar delta | `6.173070231727038` |
| Tracking max abs error | `0.006591796875` |
| Baseline max abs delta | `0.06460693359372272` |
| Displaced max abs delta | `0.058015136718722715` |
| Passive noise byte overlap | `0` |
| Clean displacement window | `True` |
| Score | `0.007818` |

Why this mattered: dense coordinate-copy/cache families can look plausible in a single pose. This candidate won because the memory displacement vector matched the API displacement vector with very low tracking error.

### 6. Fix the candidate comparison path so snapshot-delta records could prove correctly

A key implementation fix was required before promotion. Snapshot-delta candidates contain separate `baselineValue` and `displacedValue` fields. The comparison route had been too weak because it effectively used a single preview/best value for both references. That could falsely classify a good displacement-tracking candidate as `candidate-only-no-two-reference-match`.

The fix in commit `3c452a0` changed:

| File | Change |
|---|---|
| `scripts/rift_live_test/coordinate_candidate_compare.py` | Added mapping-aware comparison so baseline API is compared against `baselineValue` and displaced API is compared against `displacedValue`. |
| `scripts/test_coordinate_candidate_compare.py` | Added regression for snapshot-delta two-reference candidates. |
| `scripts/current_pid_candidate_readback.py` | Added proof-route compatible fields such as `ProcessId`, `TargetWindowHandle`, `NoCheatEngine`, `ReferenceMatchCount`, and `BestReferenceMatches`. |
| `scripts/promote-current-pid-proof-anchor-from-batch.ps1` | Replaced fragile encoded-command line continuations with hashtable splatting. |
| `scripts/test_promote_current_pid_proof_anchor_from_batch.py` | Added regression to ensure encoded child commands use splatted parameters and no trailing line continuations. |

### 7. Route candidate through API-now vs memory-now proof

After the comparison/readback fixes, the proof route reported:

| Field | Value |
|---|---|
| Route status | `api-memory-match` |
| Displaced readiness | `passed` |
| Both-reference match count | `16` |
| Memory readback status | `api-memory-match` |
| Reference match count | `32` |
| Decoded candidate count | `32` |
| Stable decoded candidate count | `32` |
| Selected candidate | `snapshot-delta-21487DF8F64-xyz` |
| Selected address | `0x21487DF8F64` |
| Reference max abs delta | `0.058015136718722715` |
| Promotion allowed by route | `True` |
| Movement allowed by route | `False` |

The route intentionally did **not** grant movement. It only established API/memory agreement and promotion readiness.

### 8. Run the promotion-ready multi-pose batch

The promotion batch used controlled same-target poses and readbacks:

| Field | Value |
|---|---|
| Status | `promotion-candidate-found` |
| OK | `True` |
| Captured pose count | `3` |
| Movement sent count | `2` |
| Movement evidence satisfied | `True` |
| Top candidate | `snapshot-delta-21487DF8F64-xyz` |
| Support pose count | `3` |
| Max reference max abs delta | `0.06362792968752728` |

This is the point where the candidate became strong enough to promote into the proof-anchor path.

### 9. Promote into the canonical proof anchor/watchset

Promotion produced the current proof pointer at:

```text
docs/recovery/current-proof-anchor-readback.json
```

The anchor/readback layout is:

| Field | Value |
|---|---|
| Candidate address | `0x21487DF8F64` |
| Region/address base used by proof readback | `0x21487DF8F24` |
| Candidate offset inside region | `64` |
| X/Y/Z relative offsets | `0 / 4 / 8` |
| Canonical proof source kind | `riftscan-reference-validated-candidate` |
| Proof method | `no-ce-riftscan-reference-multisample` |

### 10. Confirm freshness with ProofOnly

Latest `ProofOnly` rerun:

| Field | Value |
|---|---|
| Run | `scripts/captures/live-test-ProofOnly-20260514-174521/run-summary.json` |
| Status | `passed-proof-only` |
| OK | `True` |
| Target control | `passed-target-control` / `exact-hwnd-foreground` |
| Movement sent | `False` |
| Movement attempted | `False` |
| Current X | `7404.44091796875` |
| Current Y | `871.7135009765625` |
| Current Z | `3028.63232421875` |
| Recorded at UTC | `2026-05-14T17:46:22.1910144Z` |
| Readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-16536-readback-summary-20260514-134617.json` |
| No CE | `True` |
| SavedVariables live truth | `False` |

The proof readback was stable and sent no movement. `MovementAllowed=true` means the gate is satisfied; always check `MovementSent` separately.

### 11. Validate actual proof-gated movement separately

A short live movement smoke test later confirmed the proof-gated path moved the player:

| Field | Value |
|---|---|
| Run | `scripts/captures/live-test-Forward250-20260514-164220/run-summary.json` |
| Status | `passed` |
| Live flag | `True` |
| Movement sent | `True` |
| Input backend | `window-message` |
| Delta X | `0.31396484375` |
| Delta Y | `-0.02423095703125` |
| Delta Z | `-0.1064453125` |
| Planar distance | `0.3315185178299767` |
| Minimum required planar distance | `0.05` |

## Important artifact map

| Artifact | Path |
|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Historical stale pointer archive | `docs/recovery/historical/current-proof-anchor-readback-2026-05-14-pid2928-hwndC0994-historical.json` |
| Detailed handoff | `docs/handoffs/2026-05-14-1711-current-pid-coordinate-proof-restored.md` |
| Family snapshot sequence summary | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/summary.json` |
| Delta analysis summary | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/delta-summary.json` |
| Winning candidate file | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/candidate-vec3.json` |
| Coordinate proof route | `scripts/captures/coordinate-proof-route-20260514-163509-016518/coordinate-proof-route.json` |
| Promotion batch summary | `scripts/captures/current-pid-coordinate-anchor-batch-16536-live-approved-route-20260514-163620/coordinate-anchor-batch-summary.json` |
| Latest ProofOnly run | `scripts/captures/live-test-ProofOnly-20260514-174521/run-summary.json` |
| Latest ProofOnly readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-16536-readback-summary-20260514-134617.json` |
| Proof-gated movement run | `scripts/captures/live-test-Forward250-20260514-164220/run-summary.json` |
| RiftScan milestone review | `scripts/captures/riftscan-milestone-review-20260514-171113.json` |

## Commands / helpers involved

The exact command envelopes are preserved in the run artifacts. The important helpers were:

| Helper | Role |
|---|---|
| `scripts/x64dbg_preflight.py --require-exact-target --require-no-debugger-process` | Verified exact PID/HWND target and no debugger process. |
| `scripts/capture-rift-api-reference-coordinate.ps1` | Captured fresh `RRAPICOORD1` API/runtime coordinate references. |
| `scripts/post-rift-key.ps1 -UseWindowMessage` | Sent bounded W pulses during the family snapshot sequence. |
| `scripts/scan_current_pid_coordinate_family.py` / family snapshot wrappers | Captured grouped family memory snapshots for the current PID. |
| `scripts/rift_live_test/coordinate_candidate_compare.py` | Compared candidates against baseline and displaced API references. |
| `scripts/current_pid_candidate_readback.py` | Produced current-PID readback summaries compatible with proof routing/promotion. |
| `scripts/promote-current-pid-proof-anchor-from-batch.ps1` | Promoted the top batch candidate into proof-anchor/readback. |
| `scripts/live_test.py --profile ProofOnly` | Confirmed current proof anchor freshness without movement. |
| `scripts/live_test.py --profile Forward250 --live` | Confirmed proof-gated live movement after `ProofOnly`. |
| `scripts/riftscan_milestone_review.py` | Ran the coordinated RiftScan/RiftReader strategy gate. |

## Documented commits in this recovery lane

| Commit | Subject | Why it matters |
|---|---|---|
| `3c452a0` | Restore current-pid coordinate proof promotion | Promoted the current-PID proof pointer, archived the stale pointer, fixed snapshot-delta comparison/readback compatibility/promotion wrapper, added regressions, and added the compact handoff. |
| `2fb7483` | Add manual displacement proof runner | Added the manual displaced-pose runner and compact truth helper used just before the final recovery push. |
| `d940893` | Gate same-pose coordinate comparisons | Prevented same-pose or weak-displacement comparisons from becoming promotion evidence. |
| `c34f262` | Document fresh no-displacement gate | Documented why fresh but non-displaced evidence must not promote movement truth. |
| `b8e1646` | Prefer route-selected coordinate candidates | Made the route-selected candidate preferred over older family/import snapshots. |
| `50a6032` | Gate coordinate promotion readiness | Added promotion-readiness checks before proof-anchor promotion. |
| `3160f88` | Route displaced readiness evidence | Wired displaced-readiness evidence into the proof route. |
| `e386c2a` | Add displaced readiness gate and route current hits | Added the explicit displaced-reference gate and current-hit routing. |
| `6a4f05f` | Route coordinate center evidence safely | Kept center/visual evidence sidecar-only and prevented overclaiming. |
| `ba1eb9d` | Harden coordinate displaced-pose tooling | Hardened displaced-pose tooling before this recovery run. |
| `a346e30` | Harden coordinate scan profile workflows | Hardened scan-profile workflow behavior. |
| `5697968` | Add coordinate scan profile tooling | Added the scan-profile tooling this recovery lane built on. |

Commit `3c452a0` is the main durable milestone for this discovery. It is pushed to `origin/main` and includes the code fixes, tests, handoff, stale-pointer archive, and promoted proof pointer from the successful recovery slice.

## Validation performed

| Validation | Result |
|---|---|
| Unit tests after code changes | `Ran 31 tests ... OK` |
| PowerShell parser check for promotion wrapper | `parse-ok` |
| `git diff --check --cached` before commit `3c452a0` | Passed |
| Fresh `ProofOnly` after commit | `passed-proof-only` |
| RiftScan milestone review | `ready-for-read-only-proof` / `proceed-read-only-proof-first` |
| Live movement smoke | `passed`, planar distance `0.3315185178299767` |

## Future recovery recipe

Use this order after any future restart/PID/HWND drift:

1. Read the newest handoff and this document.
2. Resolve current `rift_x64` PID/HWND and exact target-control status.
3. Immediately mark any old proof pointer as stale if PID/HWND/process epoch does not match.
4. Archive the stale pointer under `docs/recovery/historical/`.
5. Capture fresh API/runtime coordinates from `RRAPICOORD1`/live runtime surface.
6. Run grouped current-PID family snapshots over prior winning/nearby families, not single-offset probes.
7. Decode full family groups and rank candidates by displacement tracking.
8. Require baseline and displaced API references to match `baselineValue` and `displacedValue` independently.
9. Run current-PID candidate readback and coordinate proof route.
10. Promote only same-PID multi-pose candidates with sufficient displacement and stable readback.
11. Run `ProofOnly`; only then consider proof-gated movement.
12. Run a short bounded movement smoke before longer navigation.
13. Commit a coherent recovery slice only after validation passes.

## Do not repeat these mistakes

| Mistake | Why it is wrong |
|---|---|
| Reusing old absolute addresses after restart | Heap/process addresses are tied to a process epoch. |
| Treating single-pose closeness as truth | Dense/cache copies can look correct without tracking movement. |
| Treating SavedVariables as live IPC | SavedVariables are post-save snapshots, not live truth. |
| Letting visual evidence promote coordinates | Screenshots/crops are sidecar evidence only. |
| Letting route readiness grant movement | Movement still requires `ProofOnly` and live approval/profile gates. |
| Broad debugger/watchpoint fishing before ranking | The faster path was family snapshot + displacement tracking first. |

## Open gap

The current anchor is strong current-PID proof, but source/owner/static-chain provenance remains unresolved. Pointer/source scans during the recovery did not identify a static owner. The next upgrade should focus on owner/module/RVA provenance from the proven family/address after a fresh `ProofOnly`, not on replacing the working proof gate.

## Current repo note at document time

This documentation was written after commit `3c452a0`. A later `ProofOnly` freshness rerun updated `docs/recovery/current-proof-anchor-readback.json` again, and this document itself is new. `desktop.ini` is unrelated repo noise.
