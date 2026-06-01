# RiftReader compact handoff — facing-target gates and live proof refresh

Generated UTC: `2026-06-01T05:51:16Z`

# **✅ RESULT — TOP-10 FOLLOW-UP PACKAGED; NO PROMOTION PERFORMED**

This handoff supersedes
`docs/handoffs/2026-06-01-0521-camera-yaw-proof-pack-handoff.md` for the latest
implementation, route-proof, and promotion-gate packet state. The prior handoff
remains the source for the original two-pose camera/yaw proof pack.

The promoted coordinate resolver remains:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

The facing-target chain remains candidate-only for promotion review:

`[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`

No ProofOnly run, actor-chain promotion, facing/turn-rate truth promotion,
provider write, x64dbg/CE attach, or target memory write was performed.

## Current target

| Item | Current value |
|---|---|
| Target PID/HWND | PID `41808`, HWND `0x2B0A26`, process `rift_x64` |
| Process start UTC | `2026-06-01T01:50:50.903773Z` |
| Module base | `0x7FF6EE5D0000` |
| Owner root | `[rift_x64+0x32EBC80]` / owner `0x1E16E8706A0` |
| Promoted coordinate chain | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Latest coordinate readback | `scripts\captures\static-owner-coordinate-chain-readback-20260601-054735-005823\summary.json` |
| Latest nav-state readback | `scripts\captures\static-owner-nav-state-20260601-054735-766761\summary.json` |
| Latest API-now reference | `scripts\captures\rift-api-reference-currentpid-41808-20260601-054745.json` |

Latest post-proof coordinate/API agreement:

| Field | Value |
|---|---|
| Chain coordinate | `x=7259.82568359375`, `y=821.4274291992188`, `z=2994.700439453125` |
| API coordinate | `x=7259.8301`, `y=821.43`, `z=2994.7` |
| Max abs delta | `0.004416406250129512` |
| Tolerance | `0.25` |
| Status | `passed-current-pid-41808-api-now-vs-chain-now` |

## Implemented top-10 items

| # | Result |
|---:|---|
| 1 | Added visual foreground/capture pre-input gate to `scripts/static_owner_camera_yaw_classification.py`; it checks capture PID/HWND/process/title evidence and foreground exact HWND before mouse-look input. |
| 2 | Updated `tools/riftreader_workflow/navigation_pointer_discovery.py` to prefer and summarize the aggregate `static-owner-camera-yaw-multipose-report-*` packet. |
| 3 | Added `scripts/facing_target_three_pose_gate.py` and tests; existing route-forward passes now package into a formal three-pose gate artifact. |
| 4 | Refreshed exact-target coordinate/nav/API readbacks before and after the live route proof. |
| 5 | Ran one bounded exact-target turn-forward experiment; first action was `forward`, route status `progress`, progress distance `1.5254744940722471`. |
| 6 | Added `scripts/facing_target_restart_survival_packet.py` and tests; latest packet reports distinct process-start epochs and stable offsets. |
| 7 | Added `docs/recovery/ghidra-facing-coordinate-source-site-review-2026-06-01.md` summarizing owner-layout writer-site evidence. |
| 8 | Kept `owner+0x304` support-only in the new gate/review artifacts. |
| 9 | Preserved proof/gate paths in the new packet outputs and this handoff for later promotion-readiness review. |
| 10 | No promotion was performed; all facing/turn-rate/actor proof remains gated behind separate review. |

## New durable artifacts

| Artifact | Status | Path |
|---|---|---|
| Three-pose route-progress gate | `passed`, `formal-three-pose-route-progress-gate-passed` | `scripts\captures\facing-target-three-pose-gate-20260601-054258-066521\summary.json` |
| Bounded turn-forward proof | `passed`, `turn-forward-live-progress-validated` | `scripts\captures\static-owner-turn-forward-experiment-20260601-054700-011212\summary.json` |
| Restart/relog survival packet | `passed`, `candidate-facing-target-restart-relog-survival-passed` | `scripts\captures\facing-target-restart-survival-packet-20260601-054826-920485\summary.json` |
| Ghidra source-site review | tracked doc | `docs\recovery\ghidra-facing-coordinate-source-site-review-2026-06-01.md` |
| Current-truth refresh plan | `passed`, dry-run only, not applied | `.riftreader-local\current-truth-refresh-plan\latest\summary.json` |

## Live visual proof

| Check | Result |
|---|---|
| Exact bind | Passed: PID `41808`, HWND `0x2B0A26`, title `RIFT` |
| Foreground state | Passed before live route proof: `isForeground=true` |
| Baseline screenshot | `tools\rift-game-mcp\.runtime\screenshots\capture-20260601-014648-514.png` |
| Post-proof frame change | `25.9861%` changed, `tools\rift-game-mcp\.runtime\screenshots\capture-20260601-014715-904.png` |
| Final screenshot | `tools\rift-game-mcp\.runtime\screenshots\capture-20260601-014721-015.png` |

## Gate details

| Gate | Current result | Promotion implication |
|---|---|---|
| Camera/yaw aggregate | `route-actionable-candidate-present-needs-proof`, route-actionable pose count `2` | Candidate-only route-control evidence. |
| Three-pose route-progress gate | Passed from three prior aligned forward route steps | Promotion input only; not promotion. |
| Live turn-forward proof | Passed current PID/HWND after fresh readbacks | Confirms current route-progress behavior; still candidate-only. |
| Restart/relog survival packet | Passed comparing pre PID `25668` process-start `2026-05-30T02:46:41.581536+00:00` to post PID `41808` process-start `2026-06-01T01:50:50.9037737+00:00` | Promotion input only; still requires separate review. |
| Ghidra source-site review | Supports same owner writer cluster around `0x304/0x30C/0x314/0x320/0x324/0x328` | Supporting evidence only; not static-root proof alone. |

## Safety boundary

| Boundary | State |
|---|---|
| Live input sent | Yes — one bounded exact-target forward route proof after visual/freshness gates |
| Route movement sent | Yes — `movementSent=true`, `inputSent=true` in `static-owner-turn-forward-experiment-20260601-054700-011212` |
| Target memory writes | None |
| x64dbg / Cheat Engine | Not used |
| Provider writes | None |
| Tracked current-truth write | Not performed; only dry-run proposal written under `.riftreader-local` |
| Proof/facing/actor promotion | Not performed |

## Current blockers / boundaries

| Blocker | Meaning |
|---|---|
| Separate promotion review still required | The new packets are inputs, not a promotion artifact. |
| Current truth refresh not applied | Dry-run plan is ready, but tracked truth remains a separate gate. |
| Static-root/source-site proof still needs formal packaging | Ghidra note supports layout but is not a full proof gate by itself. |
| `0x304` remains support-only | It correlates with turn state but is not promoted or route-control truth. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\facing_target_three_pose_gate.py scripts\facing_target_restart_survival_packet.py scripts\static_owner_camera_yaw_classification.py tools\riftreader_workflow\navigation_pointer_discovery.py scripts\test_facing_target_three_pose_gate.py scripts\test_facing_target_restart_survival_packet.py scripts\test_navigation_pointer_discovery.py` | Passed |
| `python -m unittest scripts.test_facing_target_three_pose_gate scripts.test_facing_target_restart_survival_packet scripts.test_navigation_pointer_discovery` | Passed, `16` tests |
| `python scripts\facing_target_three_pose_gate.py ... --json` | Passed, three eligible poses |
| `python scripts\facing_target_restart_survival_packet.py ... --json` | Passed, stable offsets across distinct process epochs |
| `cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write` | Passed; only stale source is tracked `currentTruth` |
| `python tools\riftreader_workflow\validation_ledger.py --tier targeted --command "python -m unittest scripts.test_facing_target_three_pose_gate scripts.test_facing_target_restart_survival_packet scripts.test_navigation_pointer_discovery scripts.test_static_owner_camera_yaw_classification"` | Passed; ledger `C:\RIFT MODDING\RiftReader\.riftreader-local\validation-runs\20260601-055313-722576\summary.md` |

## Resume checklist

1. Refresh local status:
   ```powershell
   cd "C:\RIFT MODDING\RiftReader"
   git --no-pager status --short --branch
   cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write
   ```
2. Review `.riftreader-local\current-truth-refresh-plan\latest\proposed-current-truth.diff` before any tracked truth apply.
3. If pursuing promotion, build a separate proof/promotion review artifact that consumes:
   - `scripts\captures\facing-target-three-pose-gate-20260601-054258-066521\summary.json`
   - `scripts\captures\static-owner-turn-forward-experiment-20260601-054700-011212\summary.json`
   - `scripts\captures\facing-target-restart-survival-packet-20260601-054826-920485\summary.json`
   - `docs\recovery\ghidra-facing-coordinate-source-site-review-2026-06-01.md`
4. Do not promote facing/turn-rate/actor chains from this handoff alone.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Review and, if desired, apply the dry-run current-truth refresh proposal. | The latest readback/API evidence is fresh, but tracked truth was intentionally not updated in this slice. |
| 2 | Build a formal facing-target promotion-readiness review packet from the new gate artifacts. | Turns the new inputs into one auditable pass/fail review without silently promoting. |
| 3 | Extend the promotion review to require the Ghidra source-site doc plus route/restart gates. | Keeps static evidence and live evidence tied together. |
| 4 | Add the two new gate helpers to the tool catalog/status surfaces. | Makes them discoverable from normal resume entrypoints. |
| 5 | Add visual foreground/capture gating to other live-input helpers, starting with route-step/turn-forward. | The camera/yaw helper is hardened first; route helpers still rely on their existing foreground guards. |
| 6 | Add a regression fixture that consumes real-shaped route labels such as `current-facing-target-0x30C-pose2`. | Prevents the label-suffix issue found during first three-pose packaging. |
| 7 | Re-run the Ghidra static evidence extractor only if source-site proof needs deeper xref/decompiler context. | Current doc is enough for layout support, not final root proof. |
| 8 | Keep `owner+0x304` support-only until a dedicated turn-rate proof packet exists. | Avoids over-promoting a correlated scalar. |
| 9 | Refresh exact-target readbacks/API before any future live input or promotion claim. | Currentness ages quickly and target drift is high risk. |
| 10 | Push only after reviewing this committed slice and confirming no unrelated tracked changes. | Keeps remote history clean and reviewable. |
