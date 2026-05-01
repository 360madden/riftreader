---
state: current
as_of: 2026-05-01
---

# ChromaLink RiftReader world-state integration study (2026-05-01)

## Scope

Re-study the updated ChromaLink repo for RiftReader integration after ChromaLink
added RiftReader-specific HTTP and typed-client support.

## Snapshot metadata

| Field | Value |
|---|---|
| State | current |
| As of | 2026-05-01 |
| Report date | 2026-05-01 |
| Branch | `main` |
| RiftReader worktree | `C:\RIFT MODDING\RiftReader` |
| ChromaLink worktree | `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink` |
| Input mode | read-only inspection; localhost probe only |
| Live game input | none |
| Validation status | ChromaLink offline tests passed; live HTTP bridge not running locally during this study |

## ChromaLink baseline checked

| Field | Value |
|---|---|
| ChromaLink branch | `main...origin/main` |
| Latest commit | `55a915d Add RiftReader schema and typed client support` |
| Relevant recent commits | `e5eab25 Add RiftReader world-state HTTP endpoint`; `eaed5a1 Add typed HTTP bridge client`; `55a915d Add RiftReader schema and typed client support` |
| ChromaLink handoff checked | `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\notes\handoff-2026-05-01-000743-chromalink-external-access.md` |

## Major finding

ChromaLink now has a first-class read-only app surface for RiftReader:

| Surface | Path / package | Role |
|---|---|---|
| HTTP world state | `GET http://127.0.0.1:7337/api/v1/riftreader/world-state` | Preferred live coordinate/status ingest path |
| JSON schema | `GET http://127.0.0.1:7337/api/v1/riftreader/world-state/schema` | Contract discovery and drift guard |
| Typed .NET client | `DesktopDotNet/ChromaLink.Client` | Typed consumer reference for future C# integration |
| Raw rolling snapshot | `%LOCALAPPDATA%\ChromaLink\DesktopDotNet\out\chromalink-live-telemetry.json` | Diagnostic/fallback surface |

## World-state contract summary

| Area | Fields / behavior |
|---|---|
| Contract | `contract.name = chromalink-riftreader-world-state`, `contract.schemaVersion = 1` |
| Source contract | `sourceContract.name = chromalink-live-telemetry`, current source target is schema v2 |
| Readiness | `ok`, `ready`, `healthy`, `fresh`, `stale`, `snapshotAgeSeconds`, `snapshotPath` |
| Player position | `player.position.x/y/z`, `observedAtUtc`, `ageMs`, `fresh`, `stale` |
| Other world state | player vitals/basic state, target position/vitals/status, follow-unit positions/status |
| Explicit limitations | no heading/facing/yaw, no route planning, no movement control |

## Integration decision

| Decision | Rationale |
|---|---|
| Prefer `/api/v1/riftreader/world-state` for live RiftReader capture | It is the ChromaLink-owned app-facing contract and avoids hand-parsing the full diagnostic snapshot. |
| Keep raw snapshot support | Useful when the HTTP bridge is not running or for low-level diagnostics. |
| Do not hard-reference `ChromaLink.Client` from RiftReader yet | It lives outside this repo and would introduce an external project dependency; PowerShell/JSON is enough for current capture tooling. |
| Treat ChromaLink coords as live API truth, not memory proof | It can score memory candidates but does not prove native pointer/source-chain provenance. |
| Keep ReaderBridge/native memory as proof surfaces | ChromaLink has no facing/control/route contract. |

## RiftReader changes made from this study

| File | Change |
|---|---|
| `scripts/test-chromalink-live-telemetry.ps1` | Added `-WorldStateUrl` and `-WorldStatePath` support. |
| `scripts/export-chromalink-live-coords.ps1` | Added world-state input support while preserving raw snapshot support. |
| `scripts/capture-chromalink-live-coords.ps1` | Added `-WorldStateUrl` pass-through for capture bundles. |
| `docs/candidate-trajectory-promotion-gate.md` | Updated live capture commands to prefer the HTTP world-state endpoint. |
| `docs/todos/2026-04-30-chromalink-targeted-live-telemetry-integration-plan.md` | Updated the integration plan to reflect ChromaLink's new endpoint/schema/client. |
| `docs/todos/2026-04-30-coord-discovery-workflow-todo.md` | Updated targeted ChromaLink TODOs to prefer the world-state endpoint. |

## Commands run

```powershell
git -C "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink" status --short --branch
git -C "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink" log --oneline --decorate -n 12
git -C "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink" diff --name-status dff3138..HEAD
Get-Content "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\notes\handoff-2026-05-01-000743-chromalink-external-access.md"
dotnet test .\DesktopDotNet\ChromaLink.sln -v minimal
dotnet run --project .\DesktopDotNet\ChromaLink.Cli\ChromaLink.Cli.csproj -- validate
Test-NetConnection -ComputerName 127.0.0.1 -Port 7337
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-offline-validation.ps1"
```

## Validation results

| Check | Result |
|---|---|
| ChromaLink tests | passed: 40/40 |
| ChromaLink CLI validate | passed |
| RiftReader offline validation | passed, including ChromaLink freshness/export/capture tests and parser checks |
| Live HTTP bridge probe | port `127.0.0.1:7337` was not listening during this study |
| Local raw snapshot | present but stale and still schema v1, so not usable as live truth |

## Immediate next step

Start the ChromaLink HTTP bridge and run:

```powershell
$worldStateUrl = 'http://127.0.0.1:7337/api/v1/riftreader/world-state'
$bundle = Join-Path "C:\RIFT MODDING\RiftReader\scripts\captures" ("chromalink-live-coords-{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-chromalink-live-coords.ps1" `
  -WorldStateUrl $worldStateUrl `
  -BundleDirectory $bundle `
  -PreflightDurationSeconds 30 `
  -ExportDurationSeconds 30 `
  -ExportIntervalMilliseconds 250 `
  -Json
```

This still does not move, focus, or send input to Rift. It only waits for fresh
ChromaLink world-state telemetry and exports coordinates to `live-coords.ndjson`.
