# Static owner navigation route contract

## Purpose

This document defines the offline contract for the static-owner navigation
route helpers. It is for saved route summaries only; it is not live movement
permission and does not promote facing, actor, or proof truth.

## Current helper chain

| Step | Command | Output kind | Safety |
|---|---|---|---|
| Capture no-input state | `cmd /c scripts\static-owner-nav-now.cmd ...` | `static-owner-nav-state-readback` | Reads current process memory only after exact target checks; no input. |
| Build one saved-state plan | `cmd /c scripts\static-owner-nav-plan.cmd --state-summary-json <state.json> ...` | `static-owner-nav-target-dry-run-plan` | Offline dry-run; no live read or input. |
| Compare saved plans | `cmd /c scripts\static-owner-nav-progress.cmd --plan-summary-json <before.json> <after.json>` | `static-owner-nav-progress-dry-run` | Offline dry-run; no movement permission. |
| Build route from saved states | `cmd /c scripts\static-owner-nav-route.cmd --state-summary-json <before.json> <after.json> ...` | `static-owner-nav-route-dry-run` | Offline dry-run; controller recommendation is candidate-only. |
| Validate route contract | `cmd /c scripts\static-owner-nav-validate-route.cmd --route-summary-json <route-summary.json>` | `static-owner-nav-route-contract-validation` | Fail-closed consumer gate; no live read or input. |
| Run one bounded route step | `cmd /c scripts\static-owner-nav-route-step.cmd --destination-x <x> --destination-z <z> --movement-approved --json` | `static-owner-nav-route-step` | Live workflow gate; performs pre-state readback, one C# SendInput pulse, post-state readback, route contract validation, and fail-closed progress classification. |
| Run a conservative bounded route | `cmd /c scripts\static-owner-nav-route-run.cmd --destination-x <x> --destination-z <z> --max-steps 3 --movement-approved --json` | `static-owner-nav-route-run` | Live workflow gate; loops only by calling the one-step helper, stops on arrival/block/failure/max-steps, and records aggregate safety. |
| Validate route-run contract | `cmd /c scripts\static-owner-nav-validate-route-run.cmd <route-run-summary.json> --json` | `static-owner-nav-route-run-contract-validation` | Saved-summary gate; no live read or input. |
| Report route-run summary | `cmd /c scripts\static-owner-nav-report-route-run.cmd <route-run-summary.json> --turn-summary-json <turn-summary.json> --json` | `static-owner-nav-route-run-report` | Saved-summary report; can show turn evidence beside forward progress; no live read or input. |
| Build turn-aware first-action plan | `cmd /c scripts\static-owner-turn-aware-route-plan.cmd --destination-x <x> --destination-z <z> --json` | `static-owner-turn-aware-route-plan` | Dry-run only; computes `stop`/`forward`/`turn-left`/`turn-right` while keeping candidate yaw blocked unless explicitly gated. |
| Run one turn-forward experiment | `cmd /c scripts\static-owner-turn-forward-experiment.cmd --destination-x <x> --destination-z <z> --allow-candidate-turn-control --turn-approved --movement-approved --json` | `static-owner-turn-forward-experiment` | Single bounded live experiment; not a route loop and still no proof/facing/actor promotion. |

## Route summary requirements

Consumers must reject a route summary unless all of these are true:

| Field | Required value | Why |
|---|---:|---|
| `kind` | `static-owner-nav-route-dry-run` | Confirms the artifact is from the offline route helper. |
| `status` | `passed` | Failed or blocked route summaries are not consumable. |
| `routePlanTargets` | At least two entries | Progress/stuck classification needs a before/after path. |
| `analysis.candidateOnly` | `true` | Prevents route analysis from being treated as promoted truth. |
| `analysis.actionableForMovement` | `false` | Keeps analysis advisory only. |
| `controllerRecommendation.candidateOnly` | `true` | Recommendation is not proven facing/navigation control. |
| `controllerRecommendation.dryRunOnly` | `true` | Recommendation came from saved artifacts. |
| `controllerRecommendation.movementPermission` | `false` | Downstream helpers must not infer movement approval. |
| `controllerRecommendation.actionableForMovement` | `false` | Downstream helpers must not send input from this artifact alone. |
| `controllerRecommendation.navigationControl` | `false` | No route loop control is authorized. |
| `controllerRecommendation.requiresFreshPreflightBeforeLiveUse` | `true` | Live consumers need a new exact-target preflight. |
| `safety.movementSent` | `false` | Route helper must not move the character. |
| `safety.inputSent` | `false` | Route helper must not send keys or mouse input. |
| `safety.noCheatEngine` | `true` | CE is not part of this lane. |
| `safety.x64dbgAttach` | `false` | Debugger attach is not part of this lane. |
| `safety.providerWrites` | `false` | RiftScan/ChromaLink stay read-only. |
| `safety.dryRunOnly` | `true` | The artifact remains offline-only. |
| `safety.facingPromotion` | `false` | Facing/yaw remains candidate-only. |

The repository fixture
`scripts/navigation/testdata/static-owner-nav-route-summary-safe.json` is the
canonical safe sample for this contract.

## Controller recommendation values

| Recommended action | Intended meaning | Live permission |
|---|---|---|
| `stop-arrived` | Saved route ended inside arrival radius. | No |
| `stop-overshot` | Saved route moved away after closest approach. | No |
| `stop-wrong-way` | Saved route distance increased beyond tolerance. | No |
| `sample-more-or-reassess` | Saved route did not meet minimum progress. | No |
| `turn-left-candidate` | Saved yaw/bearing suggests left. | No |
| `turn-right-candidate` | Saved yaw/bearing suggests right. | No |
| `continue-aligned-candidate` | Saved yaw/bearing is within alignment threshold. | No |

These values are labels for offline planning and review. A live route loop must
not send input from them unless a separate live workflow has already passed its
own exact-target, current-coordinate, and movement-approval gates.

## Bounded live route-step helper

`scripts\static-owner-nav-route-step.cmd` is the first live consumer of this
contract. It is intentionally one-step only:

| Gate | Behavior |
|---|---|
| Pre-state readback | Runs `static_owner_facing_discovery.py state` with exact current-truth target checks and a navigation destination. |
| Candidate turn block | Refuses to send input unless the pre-state bearing is already `aligned`; left/right turn labels remain candidate-only. |
| Movement approval | Requires `--movement-approved`; `--dry-run` builds the step plan and sends no input. |
| Input backend | Uses `scripts\send-rift-key-csharp.ps1` with C# SendInput `ScanCode` by default. |
| Post-state readback | Captures another exact-target static-owner state after the single pulse. |
| Progress gate | Builds and validates a saved route summary from pre/post states. `progress` or `arrived` passes; `no-progress`, `wrong-way`, and `overshot` block. |
| Promotions | Does not promote facing, actor chain, proof, or current truth. |

The repository fixture
`scripts/navigation/testdata/static-owner-nav-route-step-summary-progress.json`
is the canonical safe sample for a passing one-step live movement summary. It
captures the expected safety posture: movement/input were sent once, but CE,
x64dbg, provider writes, screenshot keys, reload UI, and all proof/facing/actor
promotions remained disabled.

## Conservative live route-runner

`scripts\static-owner-nav-route-run.cmd` is a bounded multi-step wrapper around
the one-step helper. It does not implement independent movement logic.

| Gate | Behavior |
|---|---|
| Primitive | Calls `static_owner_nav_route_step.py` for every step; no separate key sender or turn primitive is used. |
| Dry-run | `--dry-run` runs exactly one route-step dry-run and sends no input. |
| Movement approval | Live runs require `--movement-approved`; missing approval blocks before calling the step helper. |
| Step contract | Every live step must pass `validate_route_step_summary_contract()`. |
| Continue rule | Continues only when the prior step passed with `routeStatus=progress`. |
| Stop rule | Stops successfully on `routeStatus=arrived` or `route-step-no-movement-needed`. |
| Fail-closed rule | Blocks/fails immediately on step failure, contract failure, candidate turn block, wrong-way, no-progress, overshot, target drift, or JSON/summary load failure. |
| Max steps | Reaching `--max-steps` with progress but without arrival returns blocked (`route-run-max-steps-reached-before-arrival`) rather than silently continuing. |
| Arrival-radius guardrail | `--arrival-radius` must not exceed `--max-arrival-radius` (default `10.0`) unless the operator explicitly raises that ceiling. |
| Promotions | Does not promote facing, actor chain, proof, or current truth. |

The runner's `safety.navigationControl` is set only when a live run sends input
across more than one step. The one-step summaries remain the source of truth for
per-step exact-target, input, progress, and contract evidence.

The repository fixture
`scripts/navigation/testdata/static-owner-nav-route-run-summary-arrived.json`
is the canonical safe sample for a passing two-step live route-run summary. It
captures the expected route-run contract: every step passed the route-step
contract, the final step reached `routeStatus=arrived`, movement/input were
sent, multi-step `navigationControl=true` was recorded, and CE/x64dbg/provider
writes/proof/facing/actor promotions remained disabled.

Route-run reports can now include turn stimulus summaries through repeated
`--turn-summary-json` arguments. This is review-only evidence: valid turn
fixtures prove bounded yaw response and planar non-drift, but do not grant
route turn control or promote yaw/facing truth.

## Turn-aware planner and single experiment boundary

`scripts\static-owner-turn-aware-route-plan.cmd` is the dry-run bridge between
route targets and the candidate yaw lane. It can recommend a first action but
always records `movementPermission=false` and `navigationControl=false`.

`scripts\static-owner-turn-forward-experiment.cmd` may execute one bounded
turn-then-forward sequence only when all relevant flags are present:

| Required flag | When required | Purpose |
|---|---|---|
| `--allow-candidate-turn-control` | Plan first action is `turn-left` or `turn-right` | Explicitly opens the candidate-yaw turn-control experiment gate. |
| `--turn-approved` | A turn will be sent | Prevents accidental turn input. |
| `--movement-approved` | Any forward route step may be sent | Preserves the live movement approval gate. |

The experiment delegates the forward pulse to `static-owner-nav-route-step`, so
the forward movement still receives a fresh exact-target static-chain readback
after any turn stimulus. It is not a loop and defaults to one route step, bounded
turn degrees, and bounded total input duration.

## Live boundary

Before any live route loop or movement-polling consumer can use this offline
route contract, it must independently prove:

| Gate | Requirement |
|---|---|
| Target identity | Exact PID, HWND, process start, process name, and module base still match. |
| Coordinate source | Fresh static-chain readback is current for the target process. |
| Proof freshness | Any proof/watchset expansion has current PID/HWND proof, not stale artifacts. |
| Movement approval | The operator explicitly approved live input/movement in the current conversation. |
| Provider boundary | RiftScan/ChromaLink writes remain disabled unless separately approved. |

The current stale proof pointer targeting PID `12148` / HWND `0x640C0C` is
historical only and must not be used as current target proof for PID `34176` /
HWND `0x3D1544`.

## Validation commands

```powershell
cmd /c scripts\static-owner-nav-validate-route.cmd --route-summary-json scripts\navigation\testdata\static-owner-nav-route-summary-safe.json
cmd /c scripts\static-owner-nav-route-step.cmd --destination-x 7260.64 --destination-z 3005 --destination-label forward-smoke --arrival-radius 1.5 --dry-run --json
cmd /c scripts\static-owner-nav-route-run.cmd --destination-x 7260.64 --destination-z 3005 --destination-label forward-smoke --arrival-radius 1.5 --max-steps 3 --dry-run --json
cmd /c scripts\static-owner-nav-validate-route-run.cmd scripts\navigation\testdata\static-owner-nav-route-run-summary-arrived.json --json
cmd /c scripts\static-owner-nav-report-route-run.cmd scripts\navigation\testdata\static-owner-nav-route-run-summary-arrived.json --json
cmd /c scripts\static-owner-nav-report-route-run.cmd scripts\navigation\testdata\static-owner-nav-route-run-summary-arrived.json --turn-summary-json scripts\navigation\testdata\static-owner-turn-stimulus-summary-left.json --turn-summary-json scripts\navigation\testdata\static-owner-turn-stimulus-summary-right.json --json
cmd /c scripts\static-owner-validate-turn-aware-route-plan.cmd scripts\navigation\testdata\static-owner-turn-aware-route-plan-summary-turn-needed.json --json
cmd /c scripts\static-owner-turn-forward-experiment.cmd --destination-x 7260.64 --destination-z 3005 --destination-label forward-smoke --arrival-radius 1.5 --dry-run --json
python -m unittest scripts.test_static_owner_facing_discovery
python -m unittest scripts.test_static_owner_nav_route_step
python -m unittest scripts.test_static_owner_nav_route_run
python -m unittest scripts.test_static_owner_turn_aware_route_plan scripts.test_static_owner_turn_forward_experiment
```

The route-step dry-run command is read-only and sends no input. Remove
`--dry-run` and add `--movement-approved` only after the live movement boundary
has been explicitly opened for the current conversation.
