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
