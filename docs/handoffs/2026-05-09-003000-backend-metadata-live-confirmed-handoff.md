# Backend metadata live confirmation handoff

Created: 2026-05-09 00:30 EDT / 2026-05-09 04:30 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

The new navigation `MovementBackend` metadata is now live-confirmed in a real no-turn waypoint run summary. The persisted JSON at
`C:\RIFT MODDING\RiftReader\scripts\captures\navigation-backend-metadata-live-currentpid-49504-20260509-0028\navigate-waypoints-run-summary.json`
reports `MovementBackend=native-window-message`, `Status=success`, `PulseCount=4`, `StopReason=arrived`, and final planar distance `0.6847331308384343m` inside the `0.75m` arrival radius.

A fresh post-run `ProofOnly` passed and updated the tracked current proof pointer. Auto-turn remains blocked. No CE was used. SavedVariables were not used as live truth.

## Live result

| Fact | Value |
|---|---|
| Visual gate | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-002611\visual-gate-status.json`; `passed-visual-baseline`, `readyForLiveInput=true` |
| Pre-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-042651\run-summary.json`; `passed-proof-only`, `movementSent=false` |
| Route | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-backend-metadata-live-currentpid-49504-20260509-0028\smoke-test-waypoints-2m-observed-forward.json` |
| Pre-navigation read | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-backend-metadata-live-currentpid-49504-20260509-0028\pre-navigation-read-current.json`; `AnchorSource=coord-trace-anchor`, initial planar `1.9999999999996247m` |
| Native waypoint run | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-backend-metadata-live-currentpid-49504-20260509-0028\navigate-waypoints-run-summary.json` |
| Status | `success` |
| Movement backend | `native-window-message` |
| Pulse count | `4` |
| Stop reason | `arrived` |
| Final planar distance | `0.6847331308384343m` inside `0.75m` radius |
| Visual change | Baseline `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-002832-404.png`; changed capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-002904-063.png`; `changePercent=62.0927`; final capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260509-002909-506.png` |
| Post-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-042916\run-summary.json`; `passed-proof-only`, `movementSent=false`, coordinate `7395.18603515625,876.5137939453125,3050.689453125` |
| Milestone review | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0030-backend-metadata-live-confirmation.json`; `ready-for-read-only-proof`; movement allowed by review `false` |

## Validation performed

| Check | Result |
|---|---|
| `find_game_window` / `focus_game_window` / `capture_game_window` | Passed for exact PID/HWND before input |
| Visual gate | Passed; `readyForLiveInput=true` |
| Fresh pre-movement `ProofOnly` | Passed at `2026-05-09T04:27:32Z` |
| Pre-navigation read | Passed; coord-trace anchor, initial planar `2.0m` |
| Native exact-HWND `--navigate-waypoints` smoke | Passed; `success`, `arrived`, `PulseCount=4`, `MovementBackend=native-window-message` |
| `wait_for_frame_change` | Passed; `changePercent=62.0927` |
| Post-movement `ProofOnly` | Passed at `2026-05-09T04:29:51Z`; pointer updated |
| RiftScan milestone review | Passed; `ready-for-read-only-proof` |

## Resume rules

| Rule | Detail |
|---|---|
| No CE | Do not use Cheat Engine unless explicitly reauthorized. |
| No SavedVariables live truth | Do not treat `ReaderBridgeExport.lua` or any SavedVariables file as live currentness. |
| Visual gate first | Rerun `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full` before live input. |
| Proof second | Rerun `python .\scripts\live_test.py --profile ProofOnly --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui` immediately before movement. |
| Native backend metadata | Real live waypoint JSON now proves `MovementBackend=native-window-message`. |
| No auto-turn yet | Actor-facing and turn-backend truth are still not promoted for this target. |

## Suggested next milestone

Start the actor-facing / turn-backend proof lane in isolation. Do not combine it with route execution until current-session actor-facing truth is behavior-backed and promoted.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs\recovery\current-truth.md`, `docs\recovery\README.md`, and `docs\handoffs\2026-05-09-003000-backend-metadata-live-confirmed-handoff.md` first. Native exact-HWND no-turn waypoint movement passed again on PID `49504` / HWND `0x5121A`, and the persisted run summary now includes `MovementBackend=native-window-message`: `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-backend-metadata-live-currentpid-49504-20260509-0028\navigate-waypoints-run-summary.json`, `PulseCount=4`, `StopReason=arrived`, final planar `0.6847331308384343m`. Post-movement `ProofOnly` passed at `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-042916\run-summary.json`. Before any further input, rerun visual gate and fresh `ProofOnly`. Do not use CE, do not use SavedVariables as live truth, and do not use auto-turn until actor-facing/turn-backend truth is promoted.
