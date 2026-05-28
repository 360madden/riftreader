# Static owner turn stimulus contract

## Purpose

This document defines the bounded turn/yaw stimulus lane for the static-owner
candidate facing fields. It is evidence collection only: `+0x30C/+0x310/+0x314`
remains candidate-only and is not promoted to navigation truth.

## Helper chain

| Step | Command | Output kind | Safety |
|---|---|---|---|
| Capture turn stimulus | `cmd /c scripts\static-owner-turn-stimulus-capture.cmd --direction left --turn-approved --json` | `static-owner-turn-stimulus-capture` | Exact-target pre/post static-owner reads around one C# SendInput turn key. |
| Validate turn summary | `cmd /c scripts\static-owner-validate-turn-stimulus.cmd <turn-summary.json> --json` | `static-owner-turn-stimulus-contract-validation` | Saved-summary contract validation; no live read or input. |
| Review with route-run report | `cmd /c scripts\static-owner-nav-report-route-run.cmd <route-run-summary.json> --turn-summary-json <turn-summary.json> --json` | `static-owner-nav-route-run-report` | Shows turn evidence beside forward route progress without granting control permission. |

## Contract requirements

Consumers must reject a turn capture summary unless all of these are true:

| Field | Required value |
|---|---|
| `kind` | `static-owner-turn-stimulus-capture` |
| `status` | `passed` |
| `verdict` | `turn-yaw-delta-validated` |
| `analysis.status` | `passed` |
| `analysis.candidateOnly` | `true` |
| `analysis.actionableForNavigation` | `false` |
| `analysis.movementPermission` | `false` |
| `analysis.facingPromotion` | `false` |
| `safety.movementSent` | `true` |
| `safety.inputSent` | `true` |
| `safety.noCheatEngine` | `true` |
| `safety.x64dbgAttach` | `false` |
| `safety.providerWrites` | `false` |
| `safety.proofPromotion` | `false` |
| `safety.actorChainPromotion` | `false` |
| `safety.facingPromotion` | `false` |
| `safety.navigationControl` | `false` |

Checked-in fixtures:

| Fixture | Direction | Result |
|---|---|---|
| `scripts\navigation\testdata\static-owner-turn-stimulus-summary-left.json` | left | Passed; signed yaw delta is negative. |
| `scripts\navigation\testdata\static-owner-turn-stimulus-summary-right.json` | right | Passed; signed yaw delta is positive. |

## Live validation results

Against PID `34176` / HWND `0x3D1544`:

| Direction | Signed yaw delta | Planar drift | Visual frame change |
|---|---:|---:|---:|
| left | `-63.528090239335185` | `0.0` | `61.7222%` |
| right | `63.5280902393352` | `0.0` | `64.0833%` |

## Validation commands

```powershell
cmd /c scripts\static-owner-validate-turn-stimulus.cmd scripts\navigation\testdata\static-owner-turn-stimulus-summary-left.json --json
cmd /c scripts\static-owner-validate-turn-stimulus.cmd scripts\navigation\testdata\static-owner-turn-stimulus-summary-right.json --json
python -m unittest scripts.test_static_owner_turn_stimulus_capture
```

## Boundary

Turn stimulus captures prove that the candidate yaw lane responds to bounded
turn input. They do **not** prove route turn control, full actor/stat-chain
truth, or ProofOnly/proof freshness. Any route controller that consumes turn
evidence must still exact-target the current process and keep proof/facing
promotion as separate explicit gates. The next-stage turn-aware planner and
single turn-forward experiment are documented separately in
`docs\workflow\static-owner-turn-aware-route-contract.md`.
