# Final push handoff - navigation summary live pass

Created: 2026-05-08 23:20 EDT / 2026-05-09 03:20 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

This is the push-bound resume handoff for the current validated no-turn navigation milestone.

Live no-turn observed-forward waypoint movement is green. The latest run used exact-HWND window-message input, wrote the durable `--navigation-run-summary-file`, arrived inside the `0.75m` radius, and was followed by a fresh no-input `ProofOnly`. Auto-turn remains blocked because actor-facing truth is stale for the current PID.

`rift-window-control` is not the final movement engine; it should remain the Codex-side safety/visual harness. The longer-term movement direction is a local runner/native input backend so movement timing is owned locally rather than by Codex/cloud turns.

## Current live truth

| Item | Value |
|---|---|
| Exact target | `rift_x64` PID `49504`, HWND `0x5121A` |
| Visual gate | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-231046\visual-gate-status.json`; `passed-visual-baseline`, `readyForLiveInput=true` |
| MCP baseline | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-231130-399.png` |
| Pre-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-031137\run-summary.json`; `movementSent=false` |
| Live waypoint summary | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\navigate-waypoints-run-summary.json` |
| Live waypoint result | `Status=success`, `PulseCount=5`, `StopReason=arrived`, final planar `0.3942869934100385m`, arrival radius `0.75m` |
| Visual change after input | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-231323-029.png`; `changePercent=34.2978`; final capture `capture-20260508-231327-998.png` |
| Post-movement proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-031334\run-summary.json`; `movementSent=false` |
| Latest coordinate snapshot | `X=7392.33203125`, `Y=874.7553100585938`, `Z=3050.837646484375` at `2026-05-09T03:14:25.9468120Z`; do not treat as current-now without a fresh proof/API-now vs memory-now check |
| Current proof pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` updated by latest `ProofOnly` |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-031702.json`; `ready-for-read-only-proof` |

## Current implementation status

| Area | Status |
|---|---|
| Exact-HWND waypoint input | Live-proven green for no-turn forward movement. |
| Durable navigation summaries | Live-proven green with `--navigation-run-summary-file`. |
| Default ReaderBridge SavedVariables trust | Removed from default navigation read/move paths; explicit snapshot only. |
| Visual preflight | New reusable `scripts\check_live_visual_gate.py`; caught and documented a transient capture blocker, then passed after recovery. |
| Observed-forward route builder | Live-used to avoid stale actor-facing truth. |
| Auto-turn | Blocked. Actor-facing truth is stale/fallback-only for PID `49504`. |
| Final movement architecture | Not done. Next architectural step is a local/native movement backend so Codex is supervisor, not high-frequency controller. |

## Code/docs included in this push

| Path | Change |
|---|---|
| `configs/live-test-profiles.json` | `ForwardSeries3x250.maxAutoRefreshAttempts=3` for proof-refresh budget. |
| `reader/RiftReader.Reader/Processes/ProcessTarget.cs` | Captures `MainWindowHandleHex` for exact-HWND movement. |
| `reader/RiftReader.Reader/Navigation/MovementBackend.cs` | Uses `-UseWindowMessage` with exact HWND; foreground SendInput fallback only when no HWND exists. |
| `reader/RiftReader.Reader/Program.cs` | Passes target HWND into waypoint movement; avoids default SavedVariables live truth; emits navigation run summary files. |
| `reader/RiftReader.Reader/Cli/ReaderOptions*.cs` | Adds and validates `--navigation-run-summary-file`. |
| `reader/RiftReader.Reader.Tests/*` | Adds parser and movement-backend coverage. |
| `scripts/rift_live_test/observed_forward_route.py` | New observed-forward no-turn route builder. |
| `scripts/build_observed_forward_smoke_route.py` | Dumb entrypoint for route builder. |
| `scripts/rift_live_test/visual_gate_status.py` | New no-input visual gate. |
| `scripts/check_live_visual_gate.py` | Dumb entrypoint for visual gate. |
| `scripts/test_observed_forward_route.py` | Route builder tests. |
| `scripts/test_visual_gate_status.py` | Visual gate tests. |
| `docs/recovery/current-truth.md` / `docs/recovery/README.md` | Updated current truth and resume pointers. |
| `docs/handoffs/*.md` | Session handoffs for refresh-budget pass, waypoint smoke, visual blocker, navigation summary pass, and this push handoff. |

## Validation

| Command / check | Result |
|---|---|
| `python .\scripts\test_visual_gate_status.py` | Passed `4/4` |
| `python .\scripts\test_observed_forward_route.py` | Passed `2/2` |
| `python .\scripts\test_live_test_orchestrator.py` | Passed `75/75` |
| `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore` | Passed `97/97` |
| `git diff --check` | Passed; only CRLF warnings |
| `python .\scripts\riftscan_milestone_review.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --write-summary --write-markdown --compact-json` | Passed; latest `ready-for-read-only-proof` |

## Resume rules

| Rule | Detail |
|---|---|
| Visual gate first | Run `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full` before live input. |
| Proof second | Run `python .\scripts\live_test.py --profile ProofOnly --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui` immediately before movement. |
| Rebuild route after movement | Generate a fresh observed-forward route from the newest `ProofOnly` summary before any additional no-turn waypoint run. |
| No CE | Do not use Cheat Engine unless explicitly reauthorized in a later conversation. |
| No SavedVariables live truth | Do not treat `ReaderBridgeExport.lua` or any SavedVariables file as live currentness. |
| No auto-turn yet | Do not use actor-facing or auto-turn until current-PID actor-facing truth is behavior-backed and promoted. |

## Suggested next branch/milestone

After this push, the best next implementation branch is a focused local/native movement backend milestone:

1. keep `rift-window-control` as visual/safety gate only;
2. keep `RiftReader.Reader` as local navigation owner;
3. replace per-pulse PowerShell input with native C# exact-HWND input;
4. later consider a resident helper/service for low-latency control loops.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs\recovery\current-truth.md`, `docs\recovery\README.md`, and `docs\handoffs\2026-05-08-232000-final-push-handoff.md` first. Latest validated live movement is a no-turn observed-forward `--navigate-waypoints` run on PID `49504` / HWND `0x5121A` with durable summary `scripts\captures\navigation-summary-currentpid-49504-20260508-2312\navigate-waypoints-run-summary.json`, `PulseCount=5`, `StopReason=arrived`, final planar `0.3942869934100385m`. Before any new input, rerun the visual gate and then `ProofOnly`. Do not use CE, do not use SavedVariables as live truth, and do not use auto-turn until actor-facing truth is current-session behavior-backed.
