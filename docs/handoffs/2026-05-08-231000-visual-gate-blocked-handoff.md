# Visual-baseline gate blocked handoff

Created: 2026-05-08 23:10 EDT / 2026-05-09 03:10 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

Do **not** continue live input yet. The current target still resolves, but the visual-baseline gate is blocked: `CopyFromScreen` fails globally with `The handle is invalid`, PrintWindow/WGC return black or flat content, and DXGI Desktop Duplication returns `E_ACCESSDENIED`. No game input was sent in this slice.

## Current truth

| Item | Value |
|---|---|
| Exact target | `rift_x64` PID `49504`, HWND `0x5121A` |
| Window state | Visible, not minimized, client rect `639x354`; focus preflight exits successfully but `isForeground=false` remains reported |
| Latest visual gate | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-230651\visual-gate-status.json` |
| Gate verdict | `blocked-visual-baseline`; `readyForLiveInput=false`; blocker `desktop-capture-access-denied` |
| Input/movement in this slice | None: `inputSent=false`, `movementSent=false` |
| Last green movement evidence | 2m observed-forward `--navigate-waypoints` smoke passed earlier with `PulseCount=4`, `StopReason=arrived`, final planar distance `0.6606430399933529m` |
| Last green proof-only | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-023644\run-summary.json` |

## What changed

| File | Change |
|---|---|
| `scripts\rift_live_test\visual_gate_status.py` | New Python no-input visual-baseline gate that resolves/focuses the target and runs CopyFromScreen, Rift MCP capture, PrintWindow, WGC window/monitor, and DXGI diagnostics. |
| `scripts\check_live_visual_gate.py` | Dumb Python entrypoint for the visual gate. |
| `scripts\test_visual_gate_status.py` | Unit tests for pass/blocker classification. |
| `docs\recovery\current-truth.md` | Updated current truth to show live input is blocked until visual baseline capture recovers. |
| `docs\recovery\README.md` | Updated newest handoff pointer and resume notes. |

## Evidence

| Check | Result |
|---|---|
| Target inspect | Passed: PID `49504`, HWND `0x5121A`, process `rift_x64`, title `RIFT`, visible, not minimized |
| Focus preflight | Exited successfully, but window still reports `isForeground=false` |
| CopyFromScreen sanity | Failed for desktop 1x1 and client 64x64 with `Exception calling "CopyFromScreen" ... "The handle is invalid."` |
| Rift MCP capture | Failed with the same `CopyFromScreen` invalid-handle error |
| PrintWindow | Failed usable quality gate; diagnostic sidecar under the visual-gate output dir |
| WGC window | Captured mechanically, but `Usable=false`; content black/flat |
| WGC monitor | Captured mechanically, but all-black/flat |
| DXGI Desktop Duplication | Failed with `E_ACCESSDENIED / Access is denied` |

## Validation run

| Command | Result |
|---|---|
| `python .\scripts\test_visual_gate_status.py` | Passed `4/4` |
| `python -m py_compile .\scripts\rift_live_test\visual_gate_status.py .\scripts\check_live_visual_gate.py` | Passed |
| `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full` | Completed no-input gate; exited blocked with summary path above |

## Blockers / cautions

| Blocker | Detail |
|---|---|
| Visual baseline blocked | Live testing policy requires a usable visual baseline before input; all current capture paths fail or return unusable content. |
| Proof age expired | The last `ProofOnly` was green earlier, but it is no longer a fresh movement gate. Rerun after visual capture is restored. |
| Auto-turn blocked | Actor-facing truth is stale for PID `49504`; do not use auto-turn or actor-facing route generation. |
| No CE / no SavedVariables | Continue the current boundary: no Cheat Engine and no SavedVariables as live truth. |

## Fast resume commands

```powershell
# 1) After waking/unlocking/reconnecting the visible desktop, rerun the visual gate first.
python .\scripts\check_live_visual_gate.py `
  --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full

# 2) Only if the visual gate reports readyForLiveInput=true, refresh proof.
python .\scripts\live_test.py --profile ProofOnly `
  --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui

# 3) Only after fresh visual + proof gates, rebuild a current observed-forward route if doing no-turn waypoint smoke.
python .\scripts\build_observed_forward_smoke_route.py `
  --proof-summary .\scripts\captures\live-test-ProofOnly-<latest>\run-summary.json `
  --forward-series-summary .\scripts\captures\live-test-ForwardSeries3x250-20260509-020624\run-summary.json `
  --output-file .\scripts\captures\navigation-smoke-currentpid-49504-<new>\smoke-test-waypoints-2m-fixed-bearing.json `
  --distance-forward 2.0 --arrival-radius 0.75 --start-radius 0.75 --max-travel-seconds 20
```

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs\recovery\current-truth.md`, `docs\recovery\README.md`, and `docs\handoffs\2026-05-08-231000-visual-gate-blocked-handoff.md` first. Current target was `rift_x64` PID `49504` / HWND `0x5121A`, but live input is blocked until `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full` returns `readyForLiveInput=true`. After that, rerun `ProofOnly` before movement. Do not use CE. Do not treat SavedVariables as live truth. Do not use auto-turn until actor-facing truth is re-proven for the current PID.
