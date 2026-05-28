# RiftReader handoff — static owner nav-target workflow helpers

Created UTC: `2026-05-28T04:58:00Z`

# **✅ DIRECT RESULT**

Static-owner pointer-chain navigation state development continued safely after the latest handoff. The work added **read-only** navigation-target analysis and a thin operator launcher. No live input, debugger, CE, provider writes, push, proof promotion, facing/yaw promotion, or route control occurred.

## Current truth snapshot

| Need | Current state |
|---|---|
| Current position resolver | Promoted coordinates only: `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Facing / yaw | Candidate-only relative target: `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` |
| New state metrics | Signed yaw transitions, max yaw delta, yaw speed/s, optional destination bearing/delta |
| Waypoint bridge | `state` can resolve a destination from a waypoint JSON + waypoint id |
| Operator launcher | `scripts/static-owner-nav-now.cmd` wraps the Python state command with compact JSON defaults |
| Movement/route control | Not promoted and not used |
| Proof pointer/RiftScan gate | Blocked for current PID because historical proof pointer still targets PID `12148` / HWND `0x640C0C` |

## Local commits from this continuation

| Commit | Summary |
|---|---|
| `c6fd6bd` | Add static owner nav target analysis |
| `88ca92c` | Load nav targets from waypoint files |
| `4555b93` | Add static owner nav state launcher |

Branch state after commits:

```text
## main...origin/main [ahead 3]
```

No push was performed.

## What changed

| Area | Change |
|---|---|
| `scripts/static_owner_facing_discovery.py` | Added `build_yaw_transition_analysis`, candidate-only `navigation_target_from_state`, waypoint destination loading, and state output fields for navigation-target requests/results. |
| `scripts/test_static_owner_facing_discovery.py` | Added tests for wrap-safe yaw deltas, candidate-only turn analysis, destination validation, waypoint loading, and waypoint request resolution. |
| `scripts/static-owner-nav-now.cmd` | New dumb `.cmd` wrapper: changes to repo root and calls `python scripts\static_owner_facing_discovery.py state --samples 3 --interval-seconds 0.1 --json %*`. |

## Useful commands

Read current static-owner nav state with compact JSON defaults:

```powershell
cmd /c scripts\static-owner-nav-now.cmd
```

Read current nav state against a waypoint destination without sending movement:

```powershell
cmd /c scripts\static-owner-nav-now.cmd --destination-waypoint-json scripts\navigation\waypoints.json --destination-waypoint-id destination
```

Use direct destination coordinates without sending movement:

```powershell
cmd /c scripts\static-owner-nav-now.cmd --destination-x 7265 --destination-z 2990 --destination-label test-destination
```

## Validation run

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_facing_discovery.py scripts\test_static_owner_facing_discovery.py` | Passed |
| `python -m unittest scripts.test_static_owner_facing_discovery` | Passed: `11` tests |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status` | Passed: `32` tests |
| `git --no-pager diff --check` | Passed; only LF/CRLF warnings before commit |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |
| `cmd /c scripts\static-owner-nav-now.cmd --help` | Passed |
| `python scripts\riftscan_milestone_review.py --pid 34176 --hwnd 0x3D1544 --process-name rift_x64 --compact-json` | Blocked as expected: pointer PID/HWND mismatch and no supported RiftScan candidate for requested target |

## RiftScan strategy gate blocker

| Field | Value |
|---|---|
| Requested target | PID `34176`, HWND `0x3D1544`, process `rift_x64` |
| Historical proof pointer target | PID `12148`, HWND `0x640C0C` |
| Gate status | `blocked` |
| Main issues | `pointer_pid_mismatch`, `pointer_hwnd_mismatch`, selected candidate source `none` |
| Safe interpretation | Do not consume old RiftScan/proof-pointer evidence for the current target. |
| Gated next command from review | `python C:\RIFT MODDING\RiftReader\scripts\live_test.py --profile ProofOnly --pid 34176 --hwnd 0x3D1544 --process-name rift_x64` |

That `ProofOnly` command is a hard approval boundary.

## Safety ledger

| Operation | Status |
|---|---|
| Live input / movement | Not sent |
| Route control | Not used |
| ProofOnly | Not run |
| Cheat Engine | Not used |
| x64dbg/debugger attach | Not used |
| Breakpoints/watchpoints | Not used |
| Provider writes | Not used |
| Facing/yaw promotion | Not done |
| Full actor/stat-chain promotion | Not done |
| Git push | Not done |

## Resume guidance

1. Treat these commits as local-only until push is explicitly approved.
2. Use `scripts/static-owner-nav-now.cmd` for no-input static-owner state reads.
3. Continue treating the `+0x30C/+0x310/+0x314` yaw source as candidate-only.
4. Do not run route movement from the candidate yaw output.
5. Before further live proof/discovery expansion, explicitly approve the fresh `ProofOnly` command from the RiftScan milestone review.
6. If `ProofOnly` succeeds for PID `34176` / HWND `0x3D1544`, rerun the milestone review before consuming RiftScan/proof evidence.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Approve or decline pushing the 4 local commits | Main is ahead locally and remote does not have the workflow helpers/handoff yet. |
| 2 | If continuing live, explicitly approve fresh `ProofOnly` for PID `34176` / HWND `0x3D1544` | RiftScan strategy gate blocks on stale proof pointer target mismatch. |
| 3 | After ProofOnly, rerun `riftscan_milestone_review.py` | Confirms whether provider/consumer evidence can be safely consumed. |
| 4 | Run a no-input `static-owner-nav-now.cmd` waypoint read | Verifies the new wrapper and waypoint bridge without movement. |
| 5 | Keep yaw/facing candidate-only until multi-stimulus proof is approved and captured | Prevents accidental route control from unpromoted facing evidence. |
| 6 | Add dry-run route-controller tests from saved state summaries | Builds route logic without touching live RIFT. |
| 7 | Add stuck/overshoot predicates around state-summary deltas | Prepares safety gates before any future movement loop. |
| 8 | Create a tiny fixture from a redacted state summary | Gives regression tests a realistic state payload. |
| 9 | Keep old PID `12148` proof artifacts marked historical | Avoids stale absolute address reuse. |
| 10 | Update current-truth only after approved proof/facing promotion gates | Keeps docs aligned with actual evidence. |

---

# Continuation addendum — offline dry-run planner

Added after the initial handoff block.

## Additional local commits

| Commit | Summary |
|---|---|
| `5401d54` | Add static owner nav dry-run planner |
| `f042f4c` | Add static owner nav plan launcher |

## Additional current state

| Need | Current state |
|---|---|
| Offline route planning | `static_owner_facing_discovery.py plan` consumes a saved `state` summary JSON and builds candidate-only destination bearing / signed turn analysis without live reads. |
| Plan launcher | `scripts/static-owner-nav-plan.cmd` wraps the dry-run `plan` command and forwards args. |
| Live safety | Still no live input, no movement, no ProofOnly, no CE/x64dbg, no promotion. |

## Additional useful commands

Build a dry-run plan from a saved state summary and direct target coordinates:

```powershell
cmd /c scripts\static-owner-nav-plan.cmd --state-summary-json <state-summary.json> --destination-x 7265 --destination-z 2990 --destination-label test-destination
```

Build a dry-run plan from a saved state summary and waypoint file:

```powershell
cmd /c scripts\static-owner-nav-plan.cmd --state-summary-json <state-summary.json> --destination-waypoint-json scripts\navigation\waypoints.json --destination-waypoint-id destination
```

## Additional validation

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_facing_discovery.py scripts\test_static_owner_facing_discovery.py` | Passed |
| `python -m unittest scripts.test_static_owner_facing_discovery` | Passed: `13` tests |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status` | Passed: `34` tests |
| `python scripts\static_owner_facing_discovery.py plan --help` | Passed |
| `cmd /c scripts\static-owner-nav-plan.cmd --help` | Passed |
| `git --no-pager diff --check` | Passed |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |

## Updated resume note

The next safe offline lane is to add recorded-state fixtures or a route-controller dry-run that consumes the new `plan` output. The next live/proof lane remains gated on explicit approval for fresh `ProofOnly` against PID `34176` / HWND `0x3D1544`, followed by rerunning the RiftScan milestone review.

---

# Continuation addendum — offline progress/stuck analysis

Added after the dry-run planner addendum.

## Additional local commits

| Commit | Summary |
|---|---|
| `54e3de7` | Add static owner nav progress dry-run |
| `d9e4a57` | Add static owner nav progress launcher |

## Additional current state

| Need | Current state |
|---|---|
| Offline progress analysis | `static_owner_facing_discovery.py progress` consumes saved dry-run plan summaries and classifies `arrived`, `progress`, `no-progress`, `wrong-way`, or `overshot`. |
| Progress launcher | `scripts/static-owner-nav-progress.cmd` wraps the dry-run `progress` command and forwards args. |
| Route safety | The progress output is explicitly dry-run, candidate-only, and not movement permission. |

## Additional useful command

Compare two or more saved plan summaries without reading live memory or sending input:

```powershell
cmd /c scripts\static-owner-nav-progress.cmd --plan-summary-json <plan-before.json> <plan-after.json>
```

Override thresholds offline:

```powershell
cmd /c scripts\static-owner-nav-progress.cmd --plan-summary-json <plan-before.json> <plan-after.json> --minimum-progress-distance 0.35 --wrong-way-tolerance-distance 0.75 --arrival-radius 2.0
```

## Additional validation

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_facing_discovery.py scripts\test_static_owner_facing_discovery.py` | Passed |
| `python -m unittest scripts.test_static_owner_facing_discovery` | Passed: `15` tests |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status` | Passed: `36` tests |
| `python scripts\static_owner_facing_discovery.py progress --help` | Passed |
| `cmd /c scripts\static-owner-nav-progress.cmd --help` | Passed |
| `git --no-pager diff --check` | Passed |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |

## Updated resume note

The offline lane now has a three-step artifact chain: `state` summary -> `plan` summary -> `progress` summary. The next safe code slice is a route-controller dry-run that consumes this chain and emits stop reasons without issuing movement. The next live/proof lane remains gated on explicit approval for fresh `ProofOnly` against PID `34176` / HWND `0x3D1544`, followed by rerunning the RiftScan milestone review.

---

# Continuation addendum — offline route dry-run

Added after the progress/stuck analysis addendum.

## Additional local commits

| Commit | Summary |
|---|---|
| `a4fed13` | Add static owner nav route dry-run |
| `c0f02a3` | Add static owner nav route launcher |

## Additional current state

| Need | Current state |
|---|---|
| Offline route dry-run | `static_owner_facing_discovery.py route` consumes two or more saved `state` summaries and one destination request, builds per-state candidate-only navigation targets, then reuses the progress/stuck classifier. |
| Route launcher | `scripts/static-owner-nav-route.cmd` wraps the dry-run `route` command and forwards args. |
| Route safety | The output is dry-run only, candidate-only, and explicitly not movement permission. It does not read live memory, send input, run ProofOnly, use CE/x64dbg, or promote facing/actor truth. |
| Live/proof boundary | Fresh ProofOnly for PID `34176` / HWND `0x3D1544` remains a hard approval boundary before any proof/watchset expansion. |

## Additional useful commands

Build a route dry-run from saved state summaries and direct target coordinates:

```powershell
cmd /c scripts\static-owner-nav-route.cmd --state-summary-json <state-before.json> <state-after.json> --destination-x 7265 --destination-z 2990 --destination-label test-destination
```

Build a route dry-run from saved state summaries and a waypoint file:

```powershell
cmd /c scripts\static-owner-nav-route.cmd --state-summary-json <state-before.json> <state-after.json> --destination-waypoint-json scripts\navigation\waypoints.json --destination-waypoint-id destination
```

Override route-progress thresholds offline:

```powershell
cmd /c scripts\static-owner-nav-route.cmd --state-summary-json <state-before.json> <state-after.json> --destination-x 7265 --destination-z 2990 --minimum-progress-distance 0.35 --wrong-way-tolerance-distance 0.75 --arrival-radius 2.0
```

## Additional validation

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_facing_discovery.py scripts\test_static_owner_facing_discovery.py` | Passed |
| `python -m unittest scripts.test_static_owner_facing_discovery` | Passed: `17` tests |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status` | Passed: `38` tests |
| `python scripts\static_owner_facing_discovery.py route --help` | Passed |
| `cmd /c scripts\static-owner-nav-route.cmd --help` | Passed |
| `git --no-pager diff --check` | Passed |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |

## Updated resume note

The offline lane now has both artifact-chain and direct-route dry runs:

1. `state` summary -> `plan` summary -> `progress` summary.
2. multiple `state` summaries + one destination request -> `route` summary.

Neither path authorizes live movement. The next useful safe local slice is to add small recorded fixture coverage for route summaries or to harden route output into a non-mutating controller contract. The next live/proof lane remains gated on explicit approval for fresh `ProofOnly` against PID `34176` / HWND `0x3D1544`, followed by rerunning the RiftScan milestone review.

---

# Continuation addendum — offline route controller recommendation

Added after the route dry-run addendum.

## Additional local commit

| Commit | Summary |
|---|---|
| `d0dfb75` | Add static owner nav route controller recommendation |

## Additional current state

| Need | Current state |
|---|---|
| Non-mutating route controller contract | Route dry-run summaries now include `controllerRecommendation` with `recommendedAction`, `controlIntent`, source sample, latest distance, bearing deltas, and explicit safety booleans. |
| Movement permission | Always `movementPermission=false`, `actionableForMovement=false`, `navigationControl=false`, `candidateOnly=true`, and `dryRunOnly=true`. |
| Stop/turn classifications | The recommendation maps offline route analysis to `stop-arrived`, `stop-overshot`, `stop-wrong-way`, `sample-more-or-reassess`, `turn-left-candidate`, `turn-right-candidate`, or `continue-aligned-candidate`. |
| Live/proof boundary | No live input, ProofOnly, CE/x64dbg, provider writes, or promotion was performed. Fresh ProofOnly remains gated. |

## Additional validation

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_facing_discovery.py scripts\test_static_owner_facing_discovery.py` | Passed |
| `python -m unittest scripts.test_static_owner_facing_discovery` | Passed: `18` tests |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status` | Passed: `39` tests |
| `git --no-pager diff --check` | Passed |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |

## Updated resume note

The route dry-run can now be used as a saved-state controller contract, but only offline. It intentionally separates recommendation text from permission: downstream live route loops must still exact-target PID/HWND/process-start/module-base and perform fresh static-chain readback/preflight before any movement, and any ProofOnly/proof expansion still requires explicit approval.

---

# Continuation addendum — offline route contract validator

Added after the route controller recommendation addendum.

## Additional local commits

| Commit | Summary |
|---|---|
| `3aa0a77` | Add static owner nav route contract validator |
| `0a09564` | Add static owner nav route contract launcher |

## Additional current state

| Need | Current state |
|---|---|
| Route summary contract validation | `static_owner_facing_discovery.py validate-route` reads a saved route summary and fails closed unless the route/controller/safety contract remains non-mutating. |
| Contract launcher | `scripts/static-owner-nav-validate-route.cmd` wraps the validator and forwards args. |
| Fail-closed checks | The validator blocks if route kind/status is wrong, fewer than two route targets exist, analysis/controller fields are missing, route targets are actionable, movement/input/provider/debug flags are unsafe, or `movementPermission` is not `false`. |
| Live/proof boundary | This is offline-only validation. It does not read live memory, send input, run ProofOnly, use CE/x64dbg, write providers, or promote truth. |

## Additional useful command

Validate a saved route summary contract before any downstream consumer reads it:

```powershell
cmd /c scripts\static-owner-nav-validate-route.cmd --route-summary-json <route-summary.json>
```

## Additional validation

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_facing_discovery.py scripts\test_static_owner_facing_discovery.py` | Passed |
| `python -m unittest scripts.test_static_owner_facing_discovery` | Passed: `20` tests |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status` | Passed: `41` tests |
| `python scripts\static_owner_facing_discovery.py validate-route --help` | Passed |
| `cmd /c scripts\static-owner-nav-validate-route.cmd --help` | Passed |
| `git --no-pager diff --check` | Passed |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |

## Updated resume note

The offline navigation chain now includes a fail-closed consumer gate: generate route summaries with `static-owner-nav-route.cmd`, then validate them with `static-owner-nav-validate-route.cmd` before any downstream helper consumes the recommendation. This still does not permit movement; live route loops need a separate exact-target static-chain readback/preflight and any proof expansion still requires explicit approval.

---

# Continuation addendum — checked-in route contract fixture

Added after the route contract validator addendum.

## Additional local commit

| Commit | Summary |
|---|---|
| `ac48988` | Add static owner nav route contract fixture |

## Additional current state

| Need | Current state |
|---|---|
| Stable route-summary fixture | Added `scripts/navigation/testdata/static-owner-nav-route-summary-safe.json` as a safe, non-live, movement-denied route summary sample. |
| Fixture coverage | `scripts/test_static_owner_facing_discovery.py` now validates the checked-in fixture through `validate_route_summary_contract`. |
| Safety posture | Fixture asserts `movementPermission=false`, `actionableForMovement=false`, `navigationControl=false`, `candidateOnly=true`, and `dryRunOnly=true`. |

## Additional validation

| Validation | Result |
|---|---|
| `python -m py_compile scripts\test_static_owner_facing_discovery.py` | Passed |
| `python -m unittest scripts.test_static_owner_facing_discovery` | Passed: `21` tests |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status` | Passed: `42` tests |
| `git --no-pager diff --check` | Passed |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |

## Updated resume note

Downstream code now has a checked-in fixture that documents and tests the safe route-summary contract. Use it as the canonical offline sample for future route consumers, not as live truth or movement permission.

---

# Continuation addendum — route contract workflow doc

Added after the checked-in route contract fixture addendum.

## Additional local commit

| Commit | Summary |
|---|---|
| `244546e` | Document static owner nav route contract |

## Additional current state

| Need | Current state |
|---|---|
| Durable route contract docs | Added `docs/workflow/static-owner-nav-route-contract.md`. |
| Consumer safety contract | The doc lists required route, analysis, controller, and safety fields that downstream helpers must enforce before consuming a saved route summary. |
| Validation command | The doc records `cmd /c scripts\static-owner-nav-validate-route.cmd --route-summary-json scripts\navigation\testdata\static-owner-nav-route-summary-safe.json`. |
| Live boundary | The doc explicitly states that route summaries and controller recommendations do not grant movement permission. |

## Additional validation

| Validation | Result |
|---|---|
| `cmd /c scripts\static-owner-nav-validate-route.cmd --route-summary-json scripts\navigation\testdata\static-owner-nav-route-summary-safe.json` | Passed |
| `git --no-pager diff --check` | Passed |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |

## Updated resume note

The route contract is now both executable and documented: use the checked-in fixture plus the workflow doc as the baseline when adding future route consumers. Remaining obvious next actions are gated: push the local commits, or approve fresh ProofOnly/live proof recovery for PID `34176` / HWND `0x3D1544`.
