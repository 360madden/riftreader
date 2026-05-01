# Candidate trajectory promotion gate

## Purpose

Use this workflow when a capture bundle contains a live coordinate truth stream
and one or more memory-coordinate candidates. The scorer ranks candidates, but
promotion is controlled only by `promotion-gate.json`.

Do not promote a coordinate candidate from score rank alone.

## Safety invariants

| Rule | Reason |
|---|---|
| `ReaderBridgeExport.lua` and other SavedVariables files are not live coordinate truth. | RIFT SavedVariables are post-save snapshots and can be stale during movement. |
| Static-cache, stale, wrong-origin, and stationary-tail-drift candidates are negative evidence only. | They can look plausible over short or stationary windows. |
| Use `promotion-gate.json` as the final promotion authority. | It enforces classification, score, RMSE, drift, missing-sample, and truth-surface checks. |
| Keep Cheat Engine out of this lane unless explicitly re-approved. | This workflow is the no-CE live telemetry plus memory-evidence path. |
| Do not send game-window input from this workflow. | The commands below are passive/offline unless a separate live capture plan is approved. |

## One-command offline validation

Run the repo-owned offline validation bundle before committing or pushing gate
workflow changes:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-offline-validation.ps1"
```

JSON output is available for automation:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-offline-validation.ps1" -Json
```

The validation bundle runs the focused metadata, ChromaLink export, trajectory
scorer, promotion-gate, and gate-runner regressions, then checks the relevant
PowerShell files with the parser and runs `git diff --check`.

## Manual bundle scoring command

The latest manual bundle remains negative/static-cache evidence. Re-run it with
explicit motion and stationary windows:

```powershell
$dir='C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451'
$truth=Join-Path $dir 'overlay-coords-manual-extract.csv'
$memory=Join-Path $dir 'memory'
$out=& pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-candidate-trajectory-gate.ps1" `
  -TruthCsv $truth `
  -MemoryDirectory $memory `
  -BundleDirectory $dir `
  -MovementSamples 1,2,3,4,5,6,7 `
  -StationarySamples 8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29 `
  -AllowPromotionFailure `
  -Json 2>&1
$out | ConvertFrom-Json -Depth 80 | Select-Object status,promotionAllowed,scoresFile,promotionGateFile,gateFailures | Format-List
```

Expected result: `promotion-blocked`, `promotionAllowed=false`.
The runner also writes `promotion-gate-summary.json` and
`promotion-gate-summary.md` into the bundle directory.

## Passive ChromaLink live-coordinate export

Only use this when ChromaLink is already producing fresh telemetry. This reads
the preferred ChromaLink RiftReader world-state HTTP endpoint, or the raw JSON
snapshot as a fallback, and writes `live-coords.ndjson`; it does not focus Rift
or send input.

Preferred live endpoint:

```powershell
$worldStateUrl = 'http://127.0.0.1:7337/api/v1/riftreader/world-state'
```

Bridge readiness check, with optional temporary start:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-chromalink-http-bridge.ps1" `
  -StartBridge `
  -Json
```

Use `-KeepRunning` if you want the helper-started bridge to stay up for the
following capture commands.

Contract/schema drift preflight:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-chromalink-world-state-contract.ps1" -Json
```

Preflight freshness first:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-chromalink-live-telemetry.ps1" `
  -WorldStateUrl $worldStateUrl `
  -Json
```

To wait passively for the source to become fresh:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-chromalink-live-telemetry.ps1" `
  -WorldStateUrl $worldStateUrl `
  -Watch `
  -DurationSeconds 30 `
  -IntervalMilliseconds 250 `
  -Json
```

The expected pass state is `status=pass` and `fresh=true`. `status=stale` or
`status=missing` means do not export/use the endpoint or snapshot as live truth
yet.

Preferred capture command:

```powershell
$bundle = Join-Path "C:\RIFT MODDING\RiftReader\scripts\captures" ("chromalink-live-coords-{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-chromalink-live-coords.ps1" `
  -WorldStateUrl $worldStateUrl `
  -BundleDirectory $bundle `
  -PreflightDurationSeconds 30 `
  -ExportDurationSeconds 30 `
  -ExportIntervalMilliseconds 250 `
  -Json
```

This wrapper writes:

| Artifact | Purpose |
|---|---|
| `chromalink-http-bridge-readiness.json` | HTTP bridge `/api/v1`, `/health`, `/ready`, and schema reachability proof for URL-based world-state captures |
| `chromalink-world-state-contract.json` | Contract/schema proof for world-state captures; omitted for raw snapshot fallback |
| `chromalink-freshness-preflight.json` | Freshness proof before export |
| `live-coords.ndjson` | Exported live coordinate truth stream |
| `chromalink-live-coords-export-result.json` | Lower-level export result |
| `chromalink-live-coords-capture-summary.json` | Wrapper summary |

The wrapper automatically runs bridge readiness and contract/schema preflights
for URL-based world-state captures and records them in the bundle. You can still
run either check separately after ChromaLink updates or before the first capture
in a session to confirm the HTTP bridge and schema still match RiftReader
expectations.

If the wrapper result is `preflight-failed`, it does not write
`live-coords.ndjson`; restart or repair the telemetry source first. The lower
level `export-chromalink-live-coords.ps1` remains available for diagnostics,
but the wrapper is safer for normal capture bundles.

Raw snapshot fallback:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-chromalink-live-coords.ps1" `
  -SnapshotPath "$env:LOCALAPPDATA\ChromaLink\DesktopDotNet\out\chromalink-live-telemetry.json" `
  -BundleDirectory $bundle `
  -PreflightDurationSeconds 30 `
  -ExportDurationSeconds 30 `
  -Json
```

## Future live bundle gate command

After a fresh live truth stream and a matching memory-candidate timeseries are
available, gate the bundle with explicit movement and stationary sample windows:

```powershell
$bundle='C:\path\to\future-bundle'
$liveCoords=Join-Path $bundle 'live-coords.ndjson'
$memory=Join-Path $bundle 'memory'
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-candidate-trajectory-gate.ps1" `
  -LiveCoordsFile $liveCoords `
  -MemoryDirectory $memory `
  -BundleDirectory $bundle `
  -MovementSamples 1,2,3,4,5 `
  -StationarySamples 6,7,8,9,10 `
  -Json
```

Adjust the sample windows to the actual capture. Avoid letting a long stationary
tail dominate the movement proof.

The runner automatically writes compact summaries for handoffs:

| Artifact | Purpose |
|---|---|
| `promotion-gate-summary.json` | Machine-readable compact promotion status |
| `promotion-gate-summary.md` | Markdown summary suitable for handoffs |

If summaries need to be regenerated from existing gate artifacts:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\summarize-promotion-gate.ps1" `
  -PromotionGateFile (Join-Path $bundle 'promotion-gate.json') `
  -OutputJsonFile (Join-Path $bundle 'promotion-gate-summary.json') `
  -OutputMarkdownFile (Join-Path $bundle 'promotion-gate-summary.md') `
  -Json
```

To emit one bundle-level handoff/status report that combines ChromaLink capture
readiness, scoring, promotion, truth-surface, and SavedVariables freshness:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\inspect-coordinate-bundle-status.ps1" `
  -BundleDirectory $bundle `
  -Json
```

This writes `coordinate-bundle-status.json` and `coordinate-bundle-status.md`.

## Promotion decision

| Gate field | Required state |
|---|---|
| `promotionAllowed` | `true` |
| `status` | `pass` |
| `selectedCandidate.classification` | `trajectory-match` |
| `selectedCandidate.score` | At least the configured minimum, default `80` |
| `selectedCandidate.missingSampleCount` | At most the configured maximum, default `0` |
| `selectedCandidate.absoluteRmse` | At most the configured maximum, default `0.75` |
| `selectedCandidate.deltaRmse` | At most the configured maximum, default `0.75` |
| `selectedCandidate.stationaryDriftMax` | At most the configured maximum, default `0.15` |
| Truth surface | Must not be `savedvariables-live` |
| SavedVariables freshness | Must not mark SavedVariables as usable live truth |

If any row fails, preserve the bundle as candidate or negative evidence only.

## Handoff summary template

Prefer linking `coordinate-bundle-status.md`, `promotion-gate-summary.md`, and
their JSON counterparts in future handoffs whenever gate artifacts exist. If
those artifacts are not present yet, include this table:

```markdown
| Field | Value |
|---|---|
| Bundle | `...` |
| Scores | `...\candidate-trajectory-scores.json` |
| Promotion gate | `...\promotion-gate.json` |
| Runner status | `...` |
| `promotionAllowed` | `true/false` |
| Best/selected candidate | `...` |
| Classification | `...` |
| Score | `...` |
| Gate failures | `...` |
```
