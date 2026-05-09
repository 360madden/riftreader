# Observed-forward waypoint smoke handoff - 2m passed

Created: 2026-05-08 22:42 EDT / 2026-05-09 02:42 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

The current PID/HWND lane is live-test green for bounded forward movement and for a 2m observed-forward waypoint smoke. Auto-turn is still blocked because actor-facing truth is stale for this PID.

## Current truth

| Item | Value |
|---|---|
| Exact target | `rift_x64` PID `49504`, HWND `0x5121A` |
| Latest proof-only | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-023644\run-summary.json` |
| Latest current coordinate | `X=7390.728515625`, `Y=873.7625732421875`, `Z=3050.921630859375` at `2026-05-09T02:37:31.8477050Z` |
| Current proof pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| Proof anchor candidate | `api-coord-hit-000005` at `0x24A01358880` from `C:\RIFT MODDING\RiftReader\scripts\captures\reacquire-currentpid-49504-20260508-211304\api-bootstrap-vec3-candidates.json` |
| No-CE / SavedVariables | No CE used. SavedVariables were not used as live truth. |

## What passed in this slice

| Test | Evidence |
|---|---|
| C# exact-HWND waypoint input plumbing | `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore` passed `96/96` |
| Observed-forward route builder | `python .\scripts\test_observed_forward_route.py` passed `2/2` |
| Pre-waypoint ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-023425\run-summary.json` |
| 2m observed-forward route plan | Route `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\smoke-test-waypoints-2m-fixed-bearing.json` planned as `2.0m`, `0.75m` arrival radius |
| Live waypoint smoke | `--navigate-waypoints` succeeded, `PulseCount=4`, `StopReason=arrived`, `FinalPlanarDistance=0.6606430399933529`, `ArrivalRadius=0.75` |
| Waypoint result artifact | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\navigate-waypoints-result-transcript.json` |
| Post-waypoint ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-023644\run-summary.json` |
| Post-waypoint navigation read | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\post-waypoint-read-navigation-current.json`; `AnchorSource=coord-trace-anchor`, `WithinArrivalRadius=true` |
| Visual change | Baseline `capture-20260508-223415-608.png`; frame change `capture-20260508-223628-326.png`; final `capture-20260508-223634-616.png` |
| Strategy checkpoint | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-024109.json`; status `ready-for-read-only-proof` |

## Code changes made

| File | Change |
|---|---|
| `reader/RiftReader.Reader/Processes/ProcessTarget.cs` | Stores resolved `MainWindowHandleHex` from the target process, JSON-ignored. |
| `reader/RiftReader.Reader/Navigation/MovementBackend.cs` | Uses exact-HWND `-UseWindowMessage` when a window handle is available; only uses foreground-required SendInput fallback when no HWND exists. |
| `reader/RiftReader.Reader/Program.cs` | Passes target HWND into waypoint movement backends; navigation read/move modes no longer silently load default ReaderBridge SavedVariables snapshots unless an explicit snapshot file is provided; `--navigation-run-summary-file` writes durable result JSON for navigation movement modes. |
| `scripts/rift_live_test/observed_forward_route.py` | New Python route builder for observed-forward smoke routes. |
| `scripts/build_observed_forward_smoke_route.py` | Dumb Python entrypoint wrapper. |
| `scripts/test_observed_forward_route.py` | Unit tests for route generation and low-signal rejection. |
| `configs/live-test-profiles.json` | Earlier fix: `ForwardSeries3x250.maxAutoRefreshAttempts=3`. |

## Blockers / cautions

| Blocker | Detail |
|---|---|
| Auto-turn blocked | `scripts\actor-facing-behavior-backed-lead.json` is stale for PID `49504`; read-only facing is only `fallback-candidate`, not canonical/actionable. |
| Actor-facing route generation blocked | `scripts\navigation\new-forward-smoke-route.ps1` still depends on current actor-facing truth; use observed-forward route builder for no-turn smoke only. |
| Proof age is short-lived | Rerun `ProofOnly` immediately before any new live movement. |
| Do not trust SavedVariables as live currentness | `ReaderBridgeExport.lua` is post-save only; currentness must come from proof anchor/API-now vs memory-now or an explicitly freshness-proven live source. |

## Fast resume commands

```powershell
# 1) Re-bind and proof current target before movement
python .\scripts\live_test.py --profile ProofOnly --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui

# 2) Rebuild a current observed-forward smoke route after any movement/proof coordinate change
python .\scripts\build_observed_forward_smoke_route.py `
  --proof-summary .\scripts\captures\live-test-ProofOnly-<latest>\run-summary.json `
  --forward-series-summary .\scripts\captures\live-test-ForwardSeries3x250-20260509-020624\run-summary.json `
  --output-file .\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\smoke-test-waypoints-2m-fixed-bearing.json `
  --distance-forward 2.0 --arrival-radius 0.75 --start-radius 0.75 --max-travel-seconds 20

# 3) Read-only plan/current checks
$route = 'C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\smoke-test-waypoints-2m-fixed-bearing.json'
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 49504 --plan-navigation-route --start-waypoint smoke_start --destination-waypoint smoke_destination --navigation-waypoint-file $route --json
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 49504 --read-navigation-current --destination-waypoint smoke_destination --navigation-waypoint-file $route --arrival-radius 0.75 --scan-context 192 --max-hits 12 --json

# 4) Only after fresh ProofOnly and read-only checks: bounded no-turn waypoint smoke
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --pid 49504 --navigate-waypoints --start-waypoint smoke_start --destination-waypoint smoke_destination --navigation-waypoint-file $route --navigation-run-summary-file .\scripts\captures\navigation-smoke-currentpid-49504-<new>\navigate-waypoints-run-summary.json --arrival-radius 0.75 --max-travel-seconds 20 --verbose-navigation-events --json
```

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs\recovery\current-truth.md`, `docs\recovery\README.md`, and this handoff first. Current target was `rift_x64` PID `49504` / HWND `0x5121A`. Bounded forward movement and a 2m observed-forward waypoint smoke passed; auto-turn remains blocked by stale actor-facing truth. Before any live movement, re-run ProofOnly for the exact PID/HWND and regenerate the observed-forward route from the newest ProofOnly coordinate. Do not use CE. Do not treat SavedVariables as live truth.
