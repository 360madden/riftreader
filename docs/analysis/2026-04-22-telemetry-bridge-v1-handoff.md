---
state: active
as_of: 2026-04-22
---

# Telemetry Bridge v1 Handoff (2026-04-22)

## Scope

This handoff freezes the current state of the **Telemetry Bridge v1** work in:

- `C:\RIFT MODDING\RiftReader\addon\ReaderBridgeExport\main.lua`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\*`
- `C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1`

The pass covered four major areas:

1. additive ReaderBridge export telemetry support without changing `ReaderBridge_v3`
2. always-on merged telemetry host inside `RiftReader.Reader`
3. proof-anchor cache handoff so memory-backed coords can survive host startup
4. hardening for non-blocking coord refresh, one-shot preflight, and clearer operational docs

This report is intended as a session handoff for the next agent, not as a
replacement for the permanent bridge documentation.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `active` |
| As of | `2026-04-22` |
| Branch | `navigation` |
| HEAD | `ee829cd` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Input mode | repo edits + local PowerShell/.NET validation + live Rift process validation |
| Live process during validation | `rift_x64` PID `63012` |
| Validation status | code-level validation passed; live telemetry path operational |

## High-level result

| Area | Result |
|---|---|
| Additive export block | working |
| Reader-side telemetry host | working |
| JSON latest snapshot contract | working |
| Event/discovery NDJSON logging | working |
| Proof-anchor cache handoff | working |
| Wrapper priming path | working |
| Telemetry preflight mode | working |
| Non-blocking coord refresh | working |
| Full live output (`memory` coords + `memory-facing`) | working in current live session |

## Current live-good state

Latest validated wrapper-host snapshot:

- `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.wrapper-host.latest.json`

Current values observed from that snapshot:

| Field | Value |
|---|---|
| `meta.effectivePositionSource` | `memory` |
| `meta.effectiveFacingSource` | `memory-facing` |
| `meta.validity.memoryCoordValid` | `true` |
| `meta.validity.facingValid` | `true` |
| Memory coord address | `0x12C9B02B888` |
| Memory coords | `7377.8408203125, 867.5263671875, 3104.8515625` |
| Facing source address | `0x12CAF6F7080` |
| Basis forward offset | `0xD4` |
| Yaw | `50.1710279369488°` |
| Pitch | `18.6871433584535°` |

## Commands run

Representative commands used during this pass:

```powershell
git -C C:\RIFT MODDING\RiftReader branch --show-current
git -C C:\RIFT MODDING\RiftReader rev-parse --short HEAD
dotnet build C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj
dotnet test C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj
pwsh -NoProfile -ExecutionPolicy Bypass -File C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1 -ProcessName rift_x64 -Preflight -Diagnostics
pwsh -NoProfile -ExecutionPolicy Bypass -File C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1 -ProcessName rift_x64 -Diagnostics
dotnet C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\bin\Debug\net10.0-windows\RiftReader.Reader.dll --process-name rift_x64 --read-player-orientation --json
pwsh -NoProfile -ExecutionPolicy Bypass -File C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1 -ProcessName rift_x64 -Json
```

## Files touched this pass

| File | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptions.cs` | Added telemetry preflight option |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs` | Added `--telemetry-preflight`, parser validation, usage/help examples |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Program.cs` | Added one-shot telemetry preflight mode |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\TelemetryInfrastructure.cs` | Added `NullTelemetryLogger` for preflight |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\TelemetrySourceReadings.cs` | Added telemetry preflight option to host/runtime model |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\TelemetrySources.cs` | Added background coord refresh, stale-grace handling, cache load/persist, non-negative proof-anchor age output |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\Cli\ReaderOptionsParserTests.cs` | Added parser coverage for telemetry preflight |
| `C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1` | Added `-Preflight`, proof-anchor priming path, and mode gating |
| `C:\RIFT MODDING\RiftReader\docs\telemetry-bridge-v1.md` | Updated operator docs for preflight, wrapper priming, and async refresh behavior |

Files modified earlier in the same wider bridge pass and still important:

| File | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\addon\ReaderBridgeExport\main.lua` | Added additive `current.telemetry` export block |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\AddonSnapshots\ReaderBridgeSnapshotLoader.cs` | Added optional telemetry-block parsing |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\TelemetryContracts.cs` | Added public telemetry JSON contract |
| `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\TelemetryHost.cs` | Always-on host loop |

## Current working tree status

At handoff time:

| Status | File |
|---|---|
| modified | `C:\RIFT MODDING\RiftReader\docs\telemetry-bridge-v1.md` |
| modified | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\Cli\ReaderOptionsParserTests.cs` |
| modified | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptions.cs` |
| modified | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs` |
| modified | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Program.cs` |
| modified | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\TelemetryInfrastructure.cs` |
| modified | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\TelemetrySourceReadings.cs` |
| modified | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Telemetry\TelemetrySources.cs` |
| modified | `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json` |
| modified | `C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1` |

Important note:

- `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`
  was rebuilt against the current live session and is part of the current
  operational success state. Do not casually overwrite it without re-validating
  the facing path.

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| Wrapper priming + host startup | working | `run-telemetry-host.ps1` now primes `telemetry-proof-coord-anchor.json` before launch unless explicitly skipped |
| One-shot readiness check | working | `--telemetry-preflight` and `-Preflight` both work |
| Full merged telemetry | working | wrapper-host validation reached `memory` + `memory-facing` together |
| Async coord refresh | working | raw host startup no longer blocks while coord proof refresh is in flight |
| Proof-anchor freshness reporting | improved | non-negative `proofAnchorAgeSeconds` now observed |
| Live facing source | working | rebuilt lead at `0x12CAF6F7080` `+0xD4` remained valid in this session |

## Remaining caveats

| Area | Result | Notes |
|---|---|---|
| Raw unprimed host startup | degraded-first | may briefly publish addon coords while background refresh completes |
| Stale-grace semantics | not first-class in contract | currently implied through diagnostics notes, not a dedicated explicit field |
| Async coord-refresh regression coverage | missing | no focused automated test for timing/recovery behavior yet |
| Log rotation soak | unverified | structured logging exists, but long-duration runtime was not soak-tested in this pass |

## Key live artifacts

| Artifact | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json` | host-readable validated proof coord anchor cache |
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.wrapper-host.latest.json` | latest wrapper-host snapshot showing `memory` + `memory-facing` |
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.wrapper-host.events.ndjson` | wrapper-host event log |
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.wrapper-host.discovery.ndjson` | wrapper-host diagnostics log |
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.hardening.latest.json` | direct-host async refresh smoke snapshot |
| `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry.hardening.events.ndjson` | direct-host event log showing degraded-first then recovery |
| `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json` | current live facing lead used by telemetry |

## Validation completed

| Validation | Result |
|---|---|
| `dotnet build C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj` | passed |
| `dotnet test C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj` | passed (`27` tests) |
| PowerShell parse of `C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1` | passed |
| Wrapper preflight run | passed |
| Wrapper cold-start host run | passed |
| Direct host async-refresh smoke | passed |

## What the next agent should assume

| Question | Answer |
|---|---|
| Is Telemetry Bridge v1 implemented? | yes |
| Is the wrapper script the preferred operator path? | yes |
| Is a current live facing lead already available in the worktree? | yes |
| Is a current proof-anchor cache already available in `scripts\captures`? | yes, but validate freshness if the live session changed |
| Should raw direct host startup be considered fully clean? | no; prefer wrapper priming or preflight first |

## Immediate next step

If the next agent continues this thread, start with:

1. `C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1 -Preflight -Diagnostics`
2. if valid, use `C:\RIFT MODDING\RiftReader\scripts\run-telemetry-host.ps1 -Diagnostics`
3. only if needed, inspect the latest files under:
   - `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry*.json`
   - `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-telemetry*.ndjson`

Best likely follow-up improvements:

1. add a focused async `MemoryCoordSource` regression test
2. decide whether stale-grace should be a first-class contract flag
3. update discovery/debug scripts to consume `readerbridge-telemetry.latest.json`
