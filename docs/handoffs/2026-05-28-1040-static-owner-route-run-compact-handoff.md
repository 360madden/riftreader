# RiftReader compact handoff — static-owner route-run navigation lane

Created UTC: `2026-05-28T10:40:00Z`

# **✅ CURRENT RESULT**

Static-owner navigation development is now at a coherent pushed-ready checkpoint:

| Area | Current state |
|---|---|
| Promoted coordinate resolver | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Facing/yaw source | Candidate-only: `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` |
| One-step movement | Implemented and live-smoke validated. |
| Multi-step route-runner | Implemented, live-validated, and fixture-backed. |
| Saved-summary validation | Implemented for route and route-run artifacts. |
| Current live target during validation | PID `34176`, HWND `0x3D1544`, process `rift_x64`, title `RIFT` |
| Stale historical proof pointer | PID `12148`, HWND `0x640C0C`; do not reuse as current proof. |

## Latest local commit stack before this handoff

| Commit | Summary |
|---|---|
| `4d776f1` | Add static owner route run validator |
| `350421e` | Add static owner route run fixture |
| `889393b` | Add conservative static owner route runner |
| `1b3aba8` | Add static owner route step fixture |
| `5c72c24` | Add bounded static owner route step |
| `83213a3` | Record live static owner movement smoke |
| `a7bac8f` | Add measured movement launcher guard |

## Implemented helpers

| Helper | Purpose | Live input? |
|---|---|---:|
| `scripts\static-owner-nav-route-step.cmd` | One bounded forward route step: pre-state, one C# SendInput pulse, post-state, route-contract check. | Only with `--movement-approved` |
| `scripts\static-owner-nav-route-run.cmd` | Conservative multi-step wrapper around route-step only; stops on arrival/block/failure/max-steps. | Only with `--movement-approved` |
| `scripts\static-owner-nav-validate-route-run.cmd` | Validates saved route-run summaries. | No |
| `scripts\static-owner-nav-validate-route.cmd` | Validates saved route summaries. | No |

## Live proof summary

| Proof | Result |
|---|---|
| C# SendInput measured movement | Passed; API planar displacement `1.6499321501200075`. |
| One route step | Passed: `route-step-live-movement-progress-validated`, progress `1.677001320876208`. |
| Two-step route run | Passed: `route-run-arrived`, total progress `3.2040832966875277`, final distance `6.308612762675733`. |
| MCP visual confirmation after route-run | Passed: `27.5%` frame change. |

## Key artifacts

| Artifact | Path |
|---|---|
| Live route-run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-route-run-20260528-102940-990292\summary.json` |
| Route-run fixture | `C:\RIFT MODDING\RiftReader\scripts\navigation\testdata\static-owner-nav-route-run-summary-arrived.json` |
| Route-run validator output | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-route-run-contract-20260528-103600-088442\summary.json` |
| Final route-run screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-063002-080.png` |
| Full running handoff | `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-28-0458-static-owner-nav-target-workflow-handoff.md` |
| Route contract doc | `C:\RIFT MODDING\RiftReader\docs\workflow\static-owner-nav-route-contract.md` |

## Validation snapshot

| Validation | Latest result |
|---|---|
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status scripts.test_static_owner_nav_route_step scripts.test_static_owner_nav_route_run` | Passed: `58` tests |
| `cmd /c scripts\static-owner-nav-validate-route-run.cmd scripts\navigation\testdata\static-owner-nav-route-run-summary-arrived.json --json` | Passed: `contractStatus=passed` |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |

---

# Continuation addendum — turn-aware planner and single turn-forward proof

Created UTC: `2026-05-28T18:15:00Z`

## Additional result

| Area | Current state |
|---|---|
| Turn-aware planner | Added dry-run `scripts\static_owner_turn_aware_route_plan.py` and wrappers. |
| Turn-control blocker | Plan summaries explicitly block candidate-yaw turn control unless `--allow-candidate-turn-control` is supplied by a separate live experiment. |
| Planner fixtures | Added aligned, small-angle, turn-needed, and opposite-facing checked-in summaries. |
| Turn-forward experiment | Added gated one-step helper `scripts\static_owner_turn_forward_experiment.py`; defaults to one route step and bounded turn/input limits. |
| Route-run report | `scripts\static-owner-nav-report-route-run.cmd` can include `--turn-summary-json` evidence beside forward route progress. |
| Actor/stat separation | No-input actor-chain status was run separately; promotion remains blocked by `current-proof-anchor-not-passed`. |

## Live turn-forward proof

Current exact target:

| Field | Value |
|---|---|
| PID | `34176` |
| HWND | `0x3D1544` |
| Process | `rift_x64` |
| Title | `RIFT` |

Command:

```powershell
cmd /c scripts\static-owner-turn-forward-experiment.cmd --destination-x 7256.371343 --destination-z 3005.467139 --destination-label turn-forward-live-smoke --arrival-radius 2.0 --alignment-threshold-degrees 15 --turn-hold-milliseconds 175 --forward-hold-milliseconds 250 --max-total-input-milliseconds 600 --max-initial-turn-degrees 90 --max-cumulative-turn-degrees 90 --max-observed-turn-degrees 90 --allow-candidate-turn-control --turn-approved --movement-approved --json
```

Result:

| Field | Value |
|---|---:|
| Verdict | `turn-forward-live-progress-validated` |
| Initial signed bearing delta | `30.000003355339118` |
| Observed turn yaw delta | `31.0602385700289` |
| Turn planar drift | `0.0` |
| Forward route status | `progress` |
| Total progress distance | `1.6784812442367274` |
| Initial planar distance | `7.9999999030984945` |
| Final planar distance | `6.321518658861767` |
| MCP visual frame change | `53.4375%` |

Artifacts:

| Artifact | Path |
|---|---|
| Live turn-forward summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-turn-forward-experiment-20260528-181318-655031\summary.json` |
| Turn-aware plan child summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-turn-forward-experiment-20260528-181318-655031\child-runs\static-owner-turn-aware-route-plan-20260528-181318-896791\summary.json` |
| Turn stimulus child summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-turn-forward-experiment-20260528-181318-655031\child-runs\static-owner-turn-stimulus-20260528-181319-685501\summary.json` |
| Forward route-step child summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-turn-forward-experiment-20260528-181318-655031\child-runs\static-owner-nav-route-step-20260528-181323-420245\summary.json` |
| Experiment contract validation | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-turn-forward-experiment-contract-20260528-181339-107616\summary.json` |
| MCP baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-141309-063.png` |
| MCP changed-frame screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-141335-342.png` |
| MCP final screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-141344-131.png` |

## Safety ledger update

| Boundary | Status |
|---|---|
| Live input/movement | Sent once under explicit approval via bounded turn-forward experiment. |
| Cheat Engine / x64dbg / debugger attach | Not used. |
| ProofOnly / proof promotion | Not run. |
| Full actor/stat-chain promotion | Not done. |
| Facing/yaw promotion | Not done; candidate-only. |
| Route turn control | Proven only for one bounded experiment, not enabled as an open route loop. |
| Provider writes | Not done. |
| SavedVariables as live truth | Not used. |

## Validation added

| Validation | Result |
|---|---|
| `python -m unittest scripts.test_static_owner_turn_aware_route_plan scripts.test_static_owner_turn_forward_experiment scripts.test_static_owner_nav_route_run scripts.test_static_owner_turn_stimulus_capture scripts.test_static_owner_nav_route_step` | Passed: `45` tests |
| Broader nav/recovery suite through turn-forward + actor-chain status | Passed: `92` tests |
| Turn-aware plan validators | Passed for turn-needed and opposite-facing fixtures |
| Route-run report with left/right turn evidence | Passed |
| Turn-forward dry-run | Passed with no input |
| Turn-forward live contract validation | Passed |

## Resume guidance

1. Keep route-loop turn control closed until the single experiment is promoted
   into a separately bounded route-loop design.
2. Use the turn-forward helper for one-step experiments only.
3. Keep actor/stat-chain and ProofOnly lanes separate; the no-debug actor-chain
   status still reports `current-proof-anchor-not-passed`.
4. If expanding to multiple turn-forward steps, add fixtures and max cumulative
   route-level input/turn guards first.
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |

## Safety ledger

| Boundary | Status |
|---|---|
| Cheat Engine / x64dbg / debugger attach | Not used |
| ProofOnly / proof promotion | Not run |
| Full actor/stat-chain promotion | Not done |
| Facing/yaw promotion | Not done; candidate-only |
| Turn control | Not implemented or enabled |
| Provider writes | Not done |
| SavedVariables as live truth | Not used |

## Resume guidance

1. Treat `+0x30C/+0x310/+0x314` yaw/facing as candidate-only.
2. Route-runner is forward-only and must remain bounded until turn/facing behavior is separately proven.
3. Use `scripts\static-owner-nav-validate-route-run.cmd` before consuming saved route-run summaries.
4. Do not promote proof/facing/actor truth without explicit approval and proof gates.
5. If continuing live, exact-target PID/HWND/process-start/module-base and take a fresh static-chain readback before movement.
6. If pushing was not already completed after this handoff, push `main` once validation stays clean.

## Recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Add a bounded turn/yaw stimulus capture helper | Route-run is forward-only; turn control needs separate evidence. |
| 2 | Capture left/right turn deltas with exact-target preflight | Proves whether candidate yaw responds reliably to turn input. |
| 3 | Add turn-capture fixtures and contract validation | Keeps future turn work regression-safe. |
| 4 | Add max-radius/arrival-radius guardrails to route-runner | Prevents overly generous arrival radii from hiding weak navigation. |
| 5 | Add route-run replay/report command | Makes saved route evidence easier to review without live reruns. |
| 6 | Keep ProofOnly separate and gated | Historical proof pointer is stale for the current PID/HWND. |
| 7 | Keep provider repos read-only | RiftReader remains the consumer in this lane. |
| 8 | Avoid route-loop expansion until turn evidence exists | Prevents candidate-only yaw from becoming implicit control truth. |
| 9 | Push after handoff commit if remote is still behind | Shares validated route-runner work. |
| 10 | After push, verify `origin/main` head matches local head | Confirms remote has the full checkpoint. |

---

# Continuation addendum — turn/yaw stimulus and route-run guardrails

Created UTC: `2026-05-28T17:05:00Z`

## Additional result

| Area | Current state |
|---|---|
| Turn/yaw stimulus helper | Added `scripts\static_owner_turn_stimulus_capture.py` and `scripts\static-owner-turn-stimulus-capture.cmd`. |
| Turn validator | Added `scripts\static-owner-validate-turn-stimulus.cmd`. |
| Turn fixtures | Added left/right checked-in summaries under `scripts\navigation\testdata\`. |
| Route-run guardrail | Added `--max-arrival-radius` (default `10.0`) and blocks overlarge `--arrival-radius`. |
| Route-run report | Added `scripts\static-owner-nav-report-route-run.cmd` for saved-summary review without live input. |
| Turn contract doc | Added `docs\workflow\static-owner-turn-stimulus-contract.md`. |

## Live turn/yaw evidence

| Direction | Key | Signed yaw delta | Planar drift | MCP frame change |
|---|---|---:|---:|---:|
| left | `left` | `-63.528090239335185` | `0.0` | `61.7222%` |
| right | `right` | `63.5280902393352` | `0.0` | `64.0833%` |

## New artifacts

| Artifact | Path |
|---|---|
| Left turn live summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-turn-stimulus-20260528-170126-146711\summary.json` |
| Right turn live summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-turn-stimulus-20260528-170200-971334\summary.json` |
| Left turn fixture | `C:\RIFT MODDING\RiftReader\scripts\navigation\testdata\static-owner-turn-stimulus-summary-left.json` |
| Right turn fixture | `C:\RIFT MODDING\RiftReader\scripts\navigation\testdata\static-owner-turn-stimulus-summary-right.json` |
| Left changed-frame screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-130136-180.png` |
| Right changed-frame screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-130209-103.png` |

## Validation added

| Validation | Result |
|---|---|
| `python -m unittest scripts.test_static_owner_turn_stimulus_capture scripts.test_static_owner_nav_route_run` | Passed: `19` tests |
| `cmd /c scripts\static-owner-validate-turn-stimulus.cmd scripts\navigation\testdata\static-owner-turn-stimulus-summary-left.json --json` | Passed |
| `cmd /c scripts\static-owner-validate-turn-stimulus.cmd scripts\navigation\testdata\static-owner-turn-stimulus-summary-right.json --json` | Passed |
| `cmd /c scripts\static-owner-nav-report-route-run.cmd scripts\navigation\testdata\static-owner-nav-route-run-summary-arrived.json --json` | Passed |
| Route-run overlarge arrival-radius guardrail | Blocked as expected with `arrival-radius-exceeds-max-arrival-radius`. |

## Updated boundary

Turn/yaw stimulus evidence proves the candidate yaw lane responds to bounded left/right turn input. It still does **not** promote facing/yaw, full actor/stat-chain truth, ProofOnly, or route turn control. Next controller work should consume these fixtures only through explicit fail-closed gates.

Final validation before commit:

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_turn_stimulus_capture.py scripts\test_static_owner_turn_stimulus_capture.py scripts\static_owner_nav_route_run.py scripts\test_static_owner_nav_route_run.py` | Passed |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status scripts.test_static_owner_nav_route_step scripts.test_static_owner_nav_route_run scripts.test_static_owner_turn_stimulus_capture` | Passed: `69` tests |
| `git --no-pager diff --check` | Passed; only line-ending warnings |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
