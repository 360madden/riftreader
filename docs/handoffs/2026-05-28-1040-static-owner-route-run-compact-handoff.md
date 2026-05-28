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
