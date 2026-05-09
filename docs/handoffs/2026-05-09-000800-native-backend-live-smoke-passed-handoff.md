# Native exact-HWND backend live smoke passed handoff

Created: 2026-05-09 00:08 EDT / 2026-05-09 04:08 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

Native exact-HWND C# waypoint movement is live-validated for the no-turn observed-forward path. The run used the new `MovementBackendFactory`/`WindowMessageMovementBackend` path, arrived inside the `0.75m` radius, and was followed by a fresh no-input `ProofOnly`.

Auto-turn remains blocked. No CE was used. SavedVariables were not used as live truth.

## Live result

| Fact | Value |
|---|---|
| Visual gate | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-235535\visual-gate-status.json`; `passed-visual-baseline`, `readyForLiveInput=true` |
| Pre-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-040515\run-summary.json`; `passed-proof-only`, `movementSent=false` |
| Route | `C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\smoke-test-waypoints-2m-observed-forward.json` |
| Native waypoint run | `C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\navigate-waypoints-run-summary.json` |
| Status | `success` |
| Pulse count | `5` |
| Stop reason | `arrived` |
| Final planar distance | `0.45741853055044995m` inside `0.75m` radius |
| Visual change | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-000704-904.png`; `changePercent=43.7149`; final capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-000711-522.png` |
| Post-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-040722\run-summary.json`; `passed-proof-only`, `movementSent=false`, coordinate `7393.87255859375,875.7035522460938,3050.758056640625` |
| Milestone review | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0008-native-live-smoke.json`; `ready-for-read-only-proof`; movement allowed by review `false` |

## Validation performed

| Check | Result |
|---|---|
| `find_game_window` / `focus_game_window` / `capture_game_window` | Passed for exact PID/HWND |
| Fresh pre-movement `ProofOnly` | Passed at `2026-05-09T04:05:52Z` |
| Native exact-HWND `--navigate-waypoints` smoke | Passed; `success`, `arrived`, `PulseCount=5` |
| `wait_for_frame_change` | Passed; `changePercent=43.7149` |
| Post-movement `ProofOnly` | Passed at `2026-05-09T04:07:59Z`; pointer updated |
| RiftScan milestone review | Passed; `ready-for-read-only-proof` |

## Resume rules

| Rule | Detail |
|---|---|
| No CE | Do not use Cheat Engine unless explicitly reauthorized. |
| No SavedVariables live truth | Do not treat `ReaderBridgeExport.lua` or any SavedVariables file as live currentness. |
| Visual gate first | Rerun `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full` before live input. |
| Proof second | Rerun `python .\scripts\live_test.py --profile ProofOnly --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui` immediately before movement. |
| Native backend | Exact-HWND waypoint movement is now live-validated for no-turn forward movement. |
| No auto-turn yet | Actor-facing and turn-backend truth are still not promoted for this target. |

## Suggested next milestone

Promote the backend evidence in docs/code metadata by recording backend type in navigation run summaries, then prepare the next isolated actor-facing/turn-backend proof lane. Do not combine auto-turn with the backend validation slice.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs\recovery\current-truth.md`, `docs\recovery\README.md`, and `docs\handoffs\2026-05-09-000800-native-backend-live-smoke-passed-handoff.md` first. Native exact-HWND C# waypoint movement passed a no-turn observed-forward live smoke on PID `49504` / HWND `0x5121A`: summary `C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\navigate-waypoints-run-summary.json`, `PulseCount=5`, `StopReason=arrived`, final planar `0.45741853055044995m`. Post-movement `ProofOnly` passed at `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-040722\run-summary.json`. Before any further input, rerun visual gate and fresh `ProofOnly`. Do not use CE, do not use SavedVariables as live truth, and do not use auto-turn until actor-facing/turn-backend truth is promoted.
