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
| Thin launcher | `C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1` | Primes the proof-anchor cache, starts the host, or reads/tails/preflights the latest JSON |

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

### Continuous host

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

### One-shot preflight

Use preflight when you want a single readiness snapshot without entering the continuous loop.

CLI:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --process-name rift_x64 `
  --telemetry-preflight `
  --telemetry-diagnostics `
  --json
```

PowerShell wrapper:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1" -Preflight -Diagnostics
```

### Wrapper behaviors

`C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1` supports:

- `-Diagnostics`
- `-Preflight`
- `-ReadLatest`
- `-TailLatest`
- `-ProofCoordAnchorFile`
- `-SkipProofCoordPrime`

By default the wrapper tries to pre-resolve a fresh proof coord anchor into:

- `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`

before starting the reader host.

## Default output files

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.latest.json` | latest merged snapshot |
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.events.ndjson` | structured event log |
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.discovery.ndjson` | richer discovery log when diagnostics mode is enabled |
| `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json` | host-readable cached validated proof coord anchor |

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
- host coord refresh is background/non-blocking; if a fresh validation is still in flight, the host may publish addon fallback temporarily instead of stalling

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

## Startup and freshness behavior

| Behavior | Meaning |
|---|---|
| Primed wrapper start | best path; usually allows immediate memory-backed coords when the cached anchor is fresh and still valid |
| Raw host start with stale cache | may begin with addon fallback while coord refresh runs in the background |
| `proofAnchorAgeSeconds` | reported as a non-negative freshness value |
| stale-grace note in diagnostics | indicates the host is still using the last validated anchor while a background refresh is in flight |

## Current v1 limitations

| Limitation | Meaning |
|---|---|
| Addon fallback is compatibility-oriented | it is not a replacement for proof-grade memory coords |
| Facing still depends on a valid behavior-backed lead | the addon does not expose yaw directly |
| Raw unprimed startup can still publish temporary addon fallback | memory coord refresh is asynchronous, not magic |
| No localhost API in v1 | file-based JSON is the primary public contract |

## Reserved future sections

Not implemented in v1:

- `selection`
- `camera`
- `nearby`
- `route`
- `environment`
