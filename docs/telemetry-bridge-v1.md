# RiftReader Telemetry Bridge v1

## Purpose

Telemetry Bridge v1 provides an always-on external JSON snapshot that merges:

- addon / ReaderBridgeExport truth for stable player context
- validated proof-grade memory coordinates for navigation
- validated behavior-backed memory facing for yaw, pitch, and forward vector

It is additive. It does **not** modify the fixed-width `ReaderBridge_v3` layout.

## Components

| Layer | Path | Role |
|---|---|---|
| Addon compatibility export | `C:\RIFT MODDING\RiftReader\addon\ReaderBridgeExport\main.lua` | Adds `current.telemetry` to the existing saved-variable export |
| Reader host CLI | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Program.cs` + `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\*` | Runs the always-on merge/publish loop |
| Thin launcher | `C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1` | Starts the host or reads/tails the latest JSON |

## Additive export block

`ReaderBridgeExport_State.current.telemetry` is optional and additive.

Fields:

- `version`
- `sequence`
- `generatedAtRealtime`
- `capabilities`
- `position`
- `movement`
- `context`

Important constraints:

- yaw / facing are **not** fabricated in the addon
- `apiYawAvailable` and `apiFacingAvailable` remain `false` until the API truly exposes them

## Reader host mode

CLI:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --process-name rift_x64 `
  --run-telemetry-host `
  --telemetry-poll-interval-ms 100 `
  --telemetry-diagnostics
```

PowerShell wrapper:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1" -Diagnostics
```

## Default output files

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.latest.json` | latest merged snapshot |
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.events.ndjson` | structured event log |
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.discovery.ndjson` | richer discovery log when diagnostics mode is enabled |

## Snapshot contract

Top-level JSON sections:

- `schemaVersion`
- `sequence`
- `generatedAtUtc`
- `process`
- `meta`
- `position`
- `facing`
- `movement`
- `state`
- `diagnostics`

### Position rules

- `position.memory` comes from the validated proof coord anchor
- `position.addon` comes from ReaderBridgeExport-compatible truth
- `position.effective` prefers memory when valid, otherwise addon

### Facing rules

- `facing` uses the live behavior-backed facing lead only
- if the lead is unavailable or invalid, facing remains `valid=false`

### Movement rules

Movement is derived from the **effective** position stream:

- `dx`
- `dy`
- `dz`
- `distance`
- `dt`
- `speed`
- `travelHeadingRadians`
- `travelHeadingDegrees`
- `yawRateDegreesPerSecond`
- `isMoving`
- `isTurning`

## Logging behavior

Always-on event log categories:

- `host.lifecycle`
- `source.coord`
- `source.facing`
- `source.context`
- `source.switch`
- `publish.snapshot`
- `publish.degraded`
- `validation.mismatch`

Logging is transition-based. A heartbeat summary is emitted every 5 seconds.

Discovery logs are only written when diagnostics mode is enabled.

## Current v1 limitations

| Limitation | Meaning |
|---|---|
| Addon fallback is compatibility-oriented | it is not a replacement for proof-grade memory coords |
| Facing still depends on a valid behavior-backed lead | the addon does not expose yaw directly |
| No localhost API in v1 | file-based JSON is the primary public contract |

## Reserved future sections

Not implemented in v1:

- `selection`
- `camera`
- `nearby`
- `route`
- `environment`
