# Native window-message movement backend handoff

Created: 2026-05-08 23:35 EDT / 2026-05-09 03:35 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Target carried forward from last live pass: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

The next post-handoff milestone is implemented: C# waypoint navigation now owns
exact-HWND window-message input locally instead of spawning `pwsh` for every
exact-HWND movement pulse.

This was a code/test milestone only. No live movement was sent after the native
backend patch. The last live movement truth remains the previous durable-summary
observed-forward no-turn waypoint pass, and auto-turn remains blocked by stale
actor-facing truth.

## What changed

| Area | Result |
|---|---|
| Backend selection | Added `MovementBackendFactory` in `reader/RiftReader.Reader/Navigation/MovementBackend.cs`. |
| Native exact-HWND input | Added `WindowMessageMovementBackend` using C# P/Invoke for `PostMessageW`, `GetWindowThreadProcessId`, `GetGUIThreadInfo`, `VkKeyScanW`, and `MapVirtualKeyW`. |
| Safety checks | Native path validates HWND ownership against requested PID and process name before posting any key messages. |
| Fallback | `PowerShellMovementBackend` is preserved for no-HWND cases only. |
| Waypoint wiring | `reader/RiftReader.Reader/Program.cs` now uses the factory for `--navigate-waypoints` and `--navigate-waypoint-route`. |
| Tests | `reader/RiftReader.Reader.Tests/Navigation/PowerShellMovementBackendTests.cs` now covers factory routing, native key down/up message construction, effective target handle usage, PID mismatch fail-closed behavior, and the old PowerShell fallback argument contract. |
| Docs | Updated `docs/recovery/current-truth.md`, `docs/recovery/README.md`, and `docs/navigation-waypoint-v1.md`. |

## Current live truth carried forward

| Fact | Value |
|---|---|
| Last validated live target | `rift_x64` PID `49504`, HWND `0x5121A` |
| Last live movement truth | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\navigate-waypoints-run-summary.json`; `Status=success`, `PulseCount=5`, `StopReason=arrived`, final planar `0.3942869934100385m` |
| Latest no-input proof pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`; last updated `2026-05-09T03:14:26Z` |
| Milestone review | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-034200-native-window-message-backend-final.json`; status `ready-for-read-only-proof`; movement allowed by review `false` |
| Live validation after native patch | Not run; rerun visual gate and fresh `ProofOnly` before any live input. |
| Auto-turn | Still blocked; no actor-facing or turn-backend promotion happened in this slice. |

## Validation

| Command / check | Result |
|---|---|
| `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore --filter "FullyQualifiedName~PowerShellMovementBackendTests"` | Passed `7/7` |
| `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore` | Passed `102/102` |
| `dotnet format .\RiftReader.slnx --verify-no-changes --no-restore` | Passed |
| `git diff --check` | Passed; only CRLF warnings |
| `python .\scripts\riftscan_milestone_review.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --write-summary --write-markdown --summary-file scripts\captures\riftscan-milestone-review-20260509-034200-native-window-message-backend-final.json --compact-json` | Passed; `ready-for-read-only-proof` |

## Resume rules

| Rule | Detail |
|---|---|
| No CE | Do not use Cheat Engine unless explicitly reauthorized in the current conversation. |
| No SavedVariables live truth | Do not treat `ReaderBridgeExport.lua` or any SavedVariables file as live currentness. |
| Visual gate first | Before live input, rerun `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full`. |
| Proof second | Run `python .\scripts\live_test.py --profile ProofOnly --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui` immediately before movement. |
| Native backend expectation | Exact-HWND waypoint navigation should now use `WindowMessageMovementBackend`; no-HWND fallback should still use `PowerShellMovementBackend`. |
| No auto-turn yet | Do not use actor-facing or auto-turn until current-PID actor-facing truth is behavior-backed and promoted. |

## Suggested next milestone

Live-validate the native exact-HWND backend with the smallest safe no-turn
observed-forward waypoint run after the visual gate and fresh `ProofOnly` pass.
Keep `rift-window-control` as visual/safety harness and treat Codex/cloud as the
supervisor, not the high-frequency movement loop.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read
`docs\recovery\current-truth.md`, `docs\recovery\README.md`, and
`docs\handoffs\2026-05-08-233500-native-window-message-backend-handoff.md`
first. C# waypoint navigation now uses native exact-HWND
`WindowMessageMovementBackend` through `MovementBackendFactory`; no live input
was sent after that code patch. Last live movement truth remains the 23:12 EDT
durable-summary observed-forward waypoint pass on PID `49504` / HWND `0x5121A`.
Before any new input, rerun the visual gate and then `ProofOnly`. Do not use CE,
do not use SavedVariables as live truth, and do not use auto-turn until
actor-facing truth is current-session behavior-backed.
