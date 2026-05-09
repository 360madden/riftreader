# Navigation backend metadata handoff

Created: 2026-05-09 00:21 EDT / 2026-05-09 04:21 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Target context: `rift_x64` PID `49504`, HWND `0x5121A` from the prior live smoke; no live input was sent in this metadata slice.

## TL;DR

Navigation artifacts now identify the movement backend explicitly. `NavigationRunResult` and `NavigationRouteRunResult` include `MovementBackend`, text output prints it, and JSON summaries persist it. This turns the prior native exact-HWND live-smoke evidence from a stderr-only backend claim into a first-class artifact contract for future runs.

Last live movement truth remains the native exact-HWND no-turn smoke:
`C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\navigate-waypoints-run-summary.json`.

Auto-turn remains blocked. No CE was used. SavedVariables were not used as live truth.

## What changed

| Area | Result |
|---|---|
| Backend contract | `IMovementBackend` now exposes `BackendKind`. |
| Backend labels | Added `native-window-message`, `powershell-window-message`, `powershell-sendinput-foreground`, `not-created`, and `unknown`. |
| Single-segment results | `NavigationRunResult` records `MovementBackend`; `WaypointNavigator` propagates the active backend into success and failure summaries. |
| Route results | `NavigationRouteRunResult` records `MovementBackend`; route summaries use the first segment backend or `not-created` when movement never reached backend creation. |
| CLI failure paths | Anchor-unavailable and auto-turn-failure results now retain backend metadata where a backend exists. |
| Text output | Navigation run and route text formatters print `Movement backend:`. |
| JSON output | Existing JSON serialization now includes `MovementBackend` automatically via the result records. |
| Tests | Movement backend factory/backend tests and navigation text/JSON tests cover the new contract. |
| Docs | `README.md`, `docs\navigation-waypoint-v1.md`, and `docs\recovery\current-truth.md` document the artifact metadata. |

## Validation performed

| Check | Result |
|---|---|
| Targeted C# tests | Passed `26/26`: backend tests, navigation JSON/text formatter tests, and waypoint navigator tests. |
| Full reader test project | Passed `102/102`: `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore`. |
| Format verification | Passed: `dotnet format .\RiftReader.slnx --verify-no-changes --no-restore`. |
| Milestone strategy review | Passed: `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0018-backend-metadata.json` returned `ready-for-read-only-proof`; movement allowed by review remains `false`. |

## Current truth boundaries

| Boundary | Detail |
|---|---|
| No live input in this slice | This milestone only changed code/tests/docs metadata. |
| Last live movement truth | Native exact-HWND no-turn smoke summary: `C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\navigate-waypoints-run-summary.json`. |
| Freshness before next input | Rerun visual gate and fresh `ProofOnly` immediately before any new movement. |
| No CE | Do not use Cheat Engine unless explicitly reauthorized in the current conversation. |
| No SavedVariables live truth | Do not treat `ReaderBridgeExport.lua` or any SavedVariables file as live currentness. |
| Auto-turn | Still blocked pending current-session behavior-backed actor-facing / turn-backend proof. |

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs\recovery\current-truth.md`, `docs\recovery\README.md`, and `docs\handoffs\2026-05-09-002100-navigation-backend-metadata-handoff.md` first. Navigation result artifacts now include `MovementBackend` metadata. The prior native exact-HWND C# no-turn waypoint smoke remains the latest live movement truth at `C:\RIFT MODDING\RiftReader\scripts\captures\native-backend-smoke-currentpid-49504-20260509-0006\navigate-waypoints-run-summary.json` with `PulseCount=5`, `StopReason=arrived`, final planar `0.45741853055044995m`. Before any further input, rerun visual gate and fresh `ProofOnly`. Do not use CE, do not use SavedVariables as live truth, and do not use auto-turn until actor-facing/turn-backend truth is promoted.
