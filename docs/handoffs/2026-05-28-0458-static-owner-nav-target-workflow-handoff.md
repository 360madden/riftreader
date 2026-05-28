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

---

# Continuation addendum — live static-owner movement smoke

Added after live movement was explicitly approved.

## Additional current state

| Need | Current state |
|---|---|
| Exact live target | Bound and focused `rift_x64` PID `34176`, HWND `0x3D1544`, title `RIFT`. |
| Pre-movement static-chain gate | Passed `static_owner_coordinate_chain_readback.py --use-current-truth --samples 3 --expect-stationary`: owner `0x278C3830010`, coordinate `X=7260.65380859375 Y=821.4304809570312 Z=2990.268798828125`, no owner changes, no blockers. |
| MCP visual/input smoke | Sent one approved `w` hold for `250ms`; frame-change check passed at `30.3819%` changed. Post-readback coordinate was `X=7260.64794921875 Y=821.3999633789062 Z=2992.156005859375`. |
| C# SendInput measured proof | `pwsh -File scripts\measure-csharp-sendinput-current.ps1 -Key w -HoldMilliseconds 250 -InputMode ScanCode -MinimumPlanarDistance 0.05 -Json` passed with API planar displacement `1.6499321501200075`. |
| Post-C# static-chain readback | Passed: owner still `0x278C3830010`, coordinate `X=7260.6416015625 Y=821.4066772460938 Z=2993.810302734375`, no owner changes, no blockers. |
| Convenience launcher | Added `scripts\measure-csharp-sendinput-current.cmd` so operators use the repo PowerShell 7 launcher instead of accidentally running the helper under Windows PowerShell 5.1. |

## Additional live artifacts

| Artifact | Path |
|---|---|
| Baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-055642-536.png` |
| MCP changed-frame screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-055720-686.png` |
| Final screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-060107-305.png` |
| Pre-movement static readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260528-095654-510477\summary.json` |
| Post-MCP static readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260528-095734-513511\summary.json` |
| C# SendInput measured proof | `C:\RIFT MODDING\RiftReader\scripts\captures\csharp-sendinput-current-measured-proof-20260528-055905\measured-result.json` |
| Post-C# static readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260528-100100-465296\summary.json` |

## Additional validation

| Validation | Result |
|---|---|
| `python scripts\static_owner_coordinate_chain_readback.py --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json` | Passed before movement |
| `mcp rift_game.send_key(w, 250ms, allowMovementKeys=true)` | Sent after explicit approval |
| `mcp rift_game.wait_for_frame_change(...)` | Passed: `30.3819%` frame change |
| `pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\measure-csharp-sendinput-current.ps1 -Key w -HoldMilliseconds 250 -InputMode ScanCode -MinimumPlanarDistance 0.05 -Json` | Passed: API planar displacement `1.6499321501200075` |
| `python scripts\static_owner_coordinate_chain_readback.py --use-current-truth --samples 3 --interval-seconds 0.20 --json` | Passed after C# movement |

## Updated resume note

Live movement is now smoke-validated against the promoted static owner-coordinate resolver for the current target. This still does **not** promote facing/yaw or a full actor/stat chain. The next useful development slice is a bounded route-step controller that uses the static-chain preflight, C# SendInput ScanCode movement, immediate post-readback, and the existing route contract validator; any ProofOnly/proof promotion still remains separately gated.

---

# Continuation addendum — bounded live route-step controller

Added after the live static-owner movement smoke.

## Additional local commit context

| Commit | Summary |
|---|---|
| `a7bac8f` | Add measured movement launcher guard |
| `83213a3` | Record live static owner movement smoke |

## Additional current state

| Need | Current state |
|---|---|
| One-step live controller | Added `scripts\static_owner_nav_route_step.py` and `scripts\static-owner-nav-route-step.cmd`. |
| Safety gate | The helper reads pre-state, refuses candidate-only turn actions, requires `--movement-approved` before input, sends at most one C# SendInput pulse, reads post-state, builds/validates a route summary, and blocks on no-progress/wrong-way/overshot. |
| Dry-run proof | `cmd /c scripts\static-owner-nav-route-step.cmd --destination-x 7260.64 --destination-z 3005 --destination-label forward-smoke --arrival-radius 1.5 --dry-run --json` passed with no input; initial bearing was aligned (`absoluteBearingDeltaDegrees=0.6981671652022783`). |
| Live route-step proof | Same destination with `--movement-approved` passed: `route-step-live-movement-progress-validated`, `routeStatus=progress`, `totalProgressDistance=1.677001320876208`, `initialPlanarDistance=11.189697380239469`, `finalPlanarDistance=9.512696059363261`. |
| Visual confirmation | MCP frame-change check after the live route-step saw `28.7847%` change. |
| Remaining boundary | This validates one bounded forward route step only. It still does not promote facing/yaw, turn control, actor/stat chain, ProofOnly, or provider truth. |

## Additional artifacts

| Artifact | Path |
|---|---|
| Route-step dry-run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-route-step-20260528-101059-549787\summary.json` |
| Live route-step summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-route-step-20260528-101131-369548\summary.json` |
| Live route summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-route-20260528-101135-090022\summary.json` |
| Live route contract validation | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-route-contract-20260528-101135-394002\summary.json` |
| Route-step baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-061121-492.png` |
| Route-step changed-frame screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-061139-912.png` |
| Route-step final screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260528-061146-649.png` |

## Additional validation

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_nav_route_step.py scripts\test_static_owner_nav_route_step.py` | Passed |
| `python -m unittest scripts.test_static_owner_nav_route_step scripts.test_static_owner_facing_discovery` | Passed: `27` tests |
| Route-step dry-run command | Passed; no input sent |
| Route-step live command with `--movement-approved` | Passed; one `w` / `250ms` C# SendInput pulse |
| MCP `wait_for_frame_change` after route step | Passed: `28.7847%` change |

## Updated resume note

The next practical slice is to harden route-step repeatability: add fixture coverage for full route-step summaries, then add a conservative multi-step route-runner that loops only while every step returns `route-step-live-movement-progress-validated`, target identity stays exact, and the destination remains aligned. Turn control should remain blocked until yaw/turn behavior is separately proven.

---

# Continuation addendum — route-step summary fixture and contract

Added after the bounded live route-step controller.

## Additional current state

| Need | Current state |
|---|---|
| Route-step fixture | Added `scripts\navigation\testdata\static-owner-nav-route-step-summary-progress.json` as a sanitized passing live-step summary fixture. |
| Contract function | Added `validate_route_step_summary_contract()` in `scripts\static_owner_nav_route_step.py`. |
| Fixture coverage | `scripts\test_static_owner_nav_route_step.py` now proves the checked-in fixture passes and a `wrong-way` route result blocks. |
| Documentation | `docs\workflow\static-owner-nav-route-contract.md` now names the route-step fixture and expected safety posture. |

## Additional validation

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_nav_route_step.py scripts\test_static_owner_nav_route_step.py` | Passed |
| `python -m unittest scripts.test_static_owner_nav_route_step scripts.test_static_owner_facing_discovery` | Passed: `29` tests |
| `git --no-pager diff --check` | Passed |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |

## Updated resume note

The next safe slice is a conservative multi-step route-runner design/implementation that imports the route-step contract and loops only on passing `progress` / `arrived` step summaries. Keep turn control blocked unless separately proven, and keep ProofOnly/proof promotion separately gated.

---

# Continuation addendum — conservative static-owner route-runner

Added after the route-step fixture and contract addendum.

## Additional current state

| Need | Current state |
|---|---|
| Multi-step route wrapper | Added `scripts\static_owner_nav_route_run.py` and `scripts\static-owner-nav-route-run.cmd`. |
| Movement primitive | The runner only calls the validated one-step helper; it does not send keys directly or implement turn control. |
| Dry-run gate | `--dry-run` runs exactly one route-step dry-run and sends no input. |
| Live gate | Live route runs require `--movement-approved`, loop only while every step passes the route-step contract with `routeStatus=progress`, and stop on arrival/block/failure/max-steps. |
| Max-step behavior | Progress without arrival at `--max-steps` returns blocked (`route-run-max-steps-reached-before-arrival`) so the runner cannot silently continue. |
| Safety posture | No CE, x64dbg, provider writes, proof promotion, actor-chain promotion, facing promotion, screenshot key, reload UI, push, or current-truth promotion. |

## Additional useful commands

Dry-run the conservative route-runner without input:

```powershell
cmd /c scripts\static-owner-nav-route-run.cmd --destination-x 7260.64 --destination-z 3005 --destination-label forward-smoke --arrival-radius 1.5 --max-steps 3 --dry-run --json
```

Live bounded run after the movement boundary is open:

```powershell
cmd /c scripts\static-owner-nav-route-run.cmd --destination-x 7260.64 --destination-z 3005 --destination-label forward-smoke --arrival-radius 1.5 --max-steps 3 --movement-approved --json
```

## Additional dry-run artifact

| Artifact | Path |
|---|---|
| Route-run dry-run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-route-run-20260528-102502-263674\summary.json` |

## Additional validation

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_nav_route_run.py scripts\test_static_owner_nav_route_run.py` | Passed |
| `cmd /c scripts\static-owner-nav-route-run.cmd --help` | Passed |
| `python -m unittest scripts.test_static_owner_nav_route_run scripts.test_static_owner_nav_route_step` | Passed: `13` tests |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status scripts.test_static_owner_nav_route_step scripts.test_static_owner_nav_route_run` | Passed: `55` tests |
| Route-run dry-run command | Passed: `route-run-dry-run-plan-built`, no input sent |
| `git --no-pager diff --check` | Passed; only line-ending warnings |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed |

## Updated resume note

The static-owner navigation lane now has a conservative multi-step wrapper, but live route-loop execution still should remain bounded and exact-target. Turn control remains blocked until yaw/turn behavior is separately proven, and ProofOnly/proof promotion remains separately gated.
