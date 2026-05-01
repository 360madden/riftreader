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

## Passive ChromaLink live-coordinate export

Only use this when ChromaLink is already producing a fresh snapshot. This reads
the ChromaLink JSON snapshot and writes `live-coords.ndjson`; it does not focus
Rift or send input.

Preflight freshness first:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-chromalink-live-telemetry.ps1" -Json
```

To wait passively for the source to become fresh:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\test-chromalink-live-telemetry.ps1" `
  -Watch `
  -DurationSeconds 30 `
  -IntervalMilliseconds 250 `
  -Json
```

The expected pass state is `status=pass` and `fresh=true`. `status=stale` or
`status=missing` means do not export/use the snapshot as live truth yet.

Preferred capture command:

```powershell
$bundle = Join-Path "C:\RIFT MODDING\RiftReader\scripts\captures" ("chromalink-live-coords-{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-chromalink-live-coords.ps1" `
  -BundleDirectory $bundle `
  -PreflightDurationSeconds 30 `
  -ExportDurationSeconds 30 `
  -ExportIntervalMilliseconds 250 `
  -Json
```

This wrapper writes:

| Artifact | Purpose |
|---|---|
| `chromalink-freshness-preflight.json` | Freshness proof before export |
| `live-coords.ndjson` | Exported live coordinate truth stream |
| `chromalink-live-coords-export-result.json` | Lower-level export result |
| `chromalink-live-coords-capture-summary.json` | Wrapper summary |

If the wrapper result is `preflight-failed`, it does not write
`live-coords.ndjson`; restart or repair the telemetry source first. The lower
level `export-chromalink-live-coords.ps1` remains available for diagnostics,
but the wrapper is safer for normal capture bundles.

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

After the gate runs, write compact summaries for handoffs:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\summarize-promotion-gate.ps1" `
  -PromotionGateFile (Join-Path $bundle 'promotion-gate.json') `
  -OutputJsonFile (Join-Path $bundle 'promotion-gate-summary.json') `
  -OutputMarkdownFile (Join-Path $bundle 'promotion-gate-summary.md') `
  -Json
```

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

Prefer linking `promotion-gate-summary.md` / `promotion-gate-summary.json` in
future handoffs whenever `promotion-gate.json` exists. If those artifacts are
not present yet, include this table:

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
