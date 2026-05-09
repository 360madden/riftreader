# Navigation summary-file live pass handoff

Created: 2026-05-08 23:16 EDT / 2026-05-09 03:16 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

Live testing is green again for the no-turn observed-forward lane. A transient desktop-capture blocker was recorded, then the visual gate recovered. I then reran a fresh `ProofOnly`, rebuilt a 2m observed-forward route, and completed a live `--navigate-waypoints` run with `--navigation-run-summary-file`. The run arrived after `5` W pulses and wrote the durable summary file successfully.

Auto-turn is still blocked by stale actor-facing truth for this PID.

## Current truth

| Item | Value |
|---|---|
| Exact target | `rift_x64` PID `49504`, HWND `0x5121A` |
| Latest visual gate | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-231046\visual-gate-status.json`; `passed-visual-baseline`, `readyForLiveInput=true` |
| MCP baseline | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-231130-399.png` |
| Latest live waypoint summary | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\navigate-waypoints-run-summary.json` |
| Latest post-run ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-031334\run-summary.json` |
| Latest coordinate snapshot | `X=7392.33203125`, `Y=874.7553100585938`, `Z=3050.837646484375` at `2026-05-09T03:14:25.9468120Z` |
| Current proof pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` updated by the latest `ProofOnly` |
| No-CE / SavedVariables | No CE used. SavedVariables were not used as live truth. |

## What passed in this slice

| Test | Evidence |
|---|---|
| Visual gate recovery | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-231046\visual-gate-status.json`; `passed-visual-baseline` |
| Rift MCP baseline | `find_game_window` + `focus_game_window` + `capture_game_window` succeeded for exact PID/HWND; baseline `capture-20260508-231130-399.png` |
| Pre-movement ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-031137\run-summary.json`; no movement |
| Observed-forward route build | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\smoke-test-waypoints-2m-observed-forward.json`; 2m target from latest proof coordinate plus observed ForwardSeries displacement |
| Route plan/read precheck | `plan-navigation-route.json` and `pre-navigation-read-current.json`; start distance `1.9999999999996247m`, `WithinArrivalRadius=false` |
| Live waypoint run | `navigate-waypoints-run-summary.json`; `Status=success`, `PulseCount=5`, `StopReason=arrived`, final planar `0.3942869934100385m`, arrival radius `0.75m` |
| Visual change after input | `wait_for_frame_change` saved `capture-20260508-231323-029.png`; `changePercent=34.2978`; final capture `capture-20260508-231327-998.png` |
| Post-movement ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-031334\run-summary.json`; no movement |
| Post-run navigation read | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\post-navigation-read-current.json`; `WithinArrivalRadius=true` |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-031702.json`; status `ready-for-read-only-proof` |

## Code/docs in this overall working set

| Area | Change |
|---|---|
| Navigation input plumbing | Exact-HWND waypoint navigation uses window-message input when HWND is available. |
| Navigation live-truth safety | Navigation read/move modes no longer silently trust default ReaderBridge SavedVariables snapshots. |
| Durable navigation summary | `--navigation-run-summary-file` writes movement-mode result JSON; now live-validated on a successful run. |
| Observed-forward route builder | Python route builder creates no-turn smoke routes from current-session proof + ForwardSeries displacement. |
| Visual gate | Python no-input visual gate added: `scripts\check_live_visual_gate.py`. |
| Docs | `docs\recovery\current-truth.md` and `docs\recovery\README.md` updated to the latest green summary-file run. |

## Validation run

| Command | Result |
|---|---|
| `python .\scripts\test_visual_gate_status.py` | Passed `4/4` |
| `python .\scripts\test_observed_forward_route.py` | Passed `2/2` |
| `python .\scripts\test_live_test_orchestrator.py` | Passed `75/75` |
| `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore` | Passed `97/97` |
| `git diff --check` | Passed; only CRLF warnings were reported |

## Blockers / cautions

| Blocker | Detail |
|---|---|
| Auto-turn blocked | `scripts\actor-facing-behavior-backed-lead.json` is stale for PID `49504`; read-only facing remains `fallback-candidate`, not canonical/actionable. |
| Proof age is short-lived | Rerun visual gate and `ProofOnly` immediately before any later movement. |
| Observed-forward only | The green waypoint smoke is no-turn movement along the observed W-key vector. It does not prove actor-facing or turn behavior. |
| No CE / no SavedVariables | Continue the current boundary: no Cheat Engine and no SavedVariables as live truth. |

## Fast resume commands

```powershell
# 1) Visual gate first.
python .\scripts\check_live_visual_gate.py `
  --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full

# 2) Fresh proof before any movement.
python .\scripts\live_test.py --profile ProofOnly `
  --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui

# 3) Rebuild no-turn observed-forward route from the newest ProofOnly.
python .\scripts\build_observed_forward_smoke_route.py `
  --proof-summary .\scripts\captures\live-test-ProofOnly-<latest>\run-summary.json `
  --forward-series-summary .\scripts\captures\live-test-ForwardSeries3x250-20260509-020624\run-summary.json `
  --output-file .\scripts\captures\navigation-summary-currentpid-49504-<new>\smoke-test-waypoints-2m-observed-forward.json `
  --distance-forward 2.0 --arrival-radius 0.75 --start-radius 0.75 --max-travel-seconds 20

# 4) Only after fresh visual + proof gates: live no-turn waypoint run with durable result summary.
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --pid 49504 --navigate-waypoints `
  --start-waypoint smoke_start --destination-waypoint smoke_destination `
  --navigation-waypoint-file <route> `
  --navigation-run-summary-file <run-summary-output> `
  --arrival-radius 0.75 --max-travel-seconds 20 `
  --verbose-navigation-events --json
```

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs\recovery\current-truth.md`, `docs\recovery\README.md`, and `docs\handoffs\2026-05-08-231600-navigation-summary-live-pass-handoff.md` first. Current target was `rift_x64` PID `49504` / HWND `0x5121A`. The visual gate recovered and a durable-summary `--navigate-waypoints` live run passed with `5` pulses and final planar distance `0.3942869934100385m`. Before any new live input, rerun `check_live_visual_gate.py` and then `ProofOnly`. Do not use CE. Do not treat SavedVariables as live truth. Do not use auto-turn until actor-facing truth is re-proven for the current PID.
