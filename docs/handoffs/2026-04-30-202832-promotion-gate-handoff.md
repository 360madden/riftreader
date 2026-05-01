# RiftReader handoff - candidate trajectory promotion gate

Created: 2026-04-30 20:28:32 -04:00 local / 2026-05-01 00:28:32Z UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Latest local commit: `83f0ec5 Add candidate trajectory promotion gate`
Remote baseline at handoff: `origin/main` = `effe053 Add ChromaLink live telemetry integration TODOs`
Status at handoff: `main...origin/main [ahead 2]`; this handoff file itself is newly created and not committed unless a later commit records it.

## TL;DR

- Offline gate work is implemented and committed.
- No live Rift/game-window input was used in this slice.
- SavedVariables remain explicitly non-live truth and must not be used as live coordinate truth.
- The manual bundle still fails promotion correctly: best candidate is `static-cache`, score `20`, not `trajectory-match`.
- Next useful step is either push the two local commits or run a fresh approved live telemetry capture and score it with the new wrapper.

## Current branch/commit truth

| Ref | State |
|---|---|
| `HEAD` | `83f0ec5 Add candidate trajectory promotion gate` |
| Previous local commit | `b1db3a1 Add capture metadata and truth-surface validation` |
| `origin/main` | `effe053 Add ChromaLink live telemetry integration TODOs` |
| Ahead count | Local `main` is ahead of `origin/main` by 2 commits before this handoff file |
| Worktree note | This handoff file is expected to make the worktree dirty until committed |

## Completed work

| Area | Result |
|---|---|
| Capture metadata/freshness tooling | Implemented in `scripts/write-capture-metadata.ps1` and wired into `scripts/record-discovery-session.ps1` by prior local commit `b1db3a1`. |
| ChromaLink live coord export | Implemented in `scripts/export-chromalink-live-coords.ps1`; stale source snapshot detection works. |
| Candidate trajectory scoring | Implemented in `scripts/score-candidate-trajectories.ps1`; supports truth CSV/live coords plus memory CSV/directory flattening. |
| Promotion gate | Implemented in `scripts/write-promotion-gate.ps1`. Fails closed unless selected candidate is a strong `trajectory-match`. |
| Gate runner | Implemented in `scripts/run-candidate-trajectory-gate.ps1`. Runs scoring, then promotion gate, and emits a single JSON result. |
| Explicit sample windows | Fixed parsing so `-MovementSamples 1,2,3` and `-StationarySamples 4,5` remain separate sample indices instead of collapsing to `123` / `45`. |
| Regression tests | Added/updated tests for metadata, ChromaLink export, scoring, promotion gate, and gate runner. |

## Key files touched by latest commit

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\write-promotion-gate.ps1` | Writes `promotion-gate.json`; permits promotion only if score, classification, sample coverage, RMSE, drift, and truth-surface checks pass. |
| `C:\RIFT MODDING\RiftReader\scripts\test-write-promotion-gate.ps1` | Regression test for passing and failing gate scenarios. |
| `C:\RIFT MODDING\RiftReader\scripts\run-candidate-trajectory-gate.ps1` | Wrapper that runs scoring and gate generation in one command. |
| `C:\RIFT MODDING\RiftReader\scripts\test-run-candidate-trajectory-gate.ps1` | Regression test for wrapper pass/fail behavior and explicit sample forwarding. |
| `C:\RIFT MODDING\RiftReader\scripts\score-candidate-trajectories.ps1` | Candidate scorer; now safely parses comma/space/semicolon-delimited sample index arguments. |
| `C:\RIFT MODDING\RiftReader\scripts\test-score-candidate-trajectories.ps1` | Added explicit sample-window regression coverage. |

## Validation already run

| Command / check | Result |
|---|---|
| `pwsh -File scripts/test-write-capture-metadata.ps1` | Passed |
| `pwsh -File scripts/test-export-chromalink-live-coords.ps1` | Passed |
| `pwsh -File scripts/test-score-candidate-trajectories.ps1` | Passed |
| `pwsh -File scripts/test-write-promotion-gate.ps1` | Passed |
| `pwsh -File scripts/test-run-candidate-trajectory-gate.ps1` | Passed |
| PowerShell parser check on touched scripts | Passed |
| `git diff --check` / `git diff --cached --check` | Passed after removing one EOF blank line in `write-promotion-gate.ps1` |
| Commit | `83f0ec5 Add candidate trajectory promotion gate` |

## Manual bundle result

Bundle directory:

`C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451`

Truth CSV:

`C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\overlay-coords-manual-extract.csv`

Memory directory:

`C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\memory`

Generated outputs:

| Artifact | Path |
|---|---|
| Scores | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\candidate-trajectory-scores.json` |
| Promotion gate | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\promotion-gate.json` |
| Flattened memory CSV | `C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451\memory-timeseries.csv` |

Observed manual-bundle gate result:

| Field | Value |
|---|---|
| Runner status | `promotion-blocked` |
| `promotionAllowed` | `false` |
| Best candidate | `0x2C98262C1F0` |
| Classification | `static-cache` |
| Score | `20` |
| Main failures | `promotionReady=false`; classification is not `trajectory-match`; score below `80`; absolute RMSE above `0.75` |

This is expected negative evidence. Do not promote any coordinate candidate from this manual bundle.

## Resume commands

### Check state

```powershell
cd 'C:\RIFT MODDING\RiftReader'
git status --short --branch
git log --oneline --decorate -5
```

### Re-run targeted validation

```powershell
$tests=@(
 'scripts/test-write-capture-metadata.ps1',
 'scripts/test-export-chromalink-live-coords.ps1',
 'scripts/test-score-candidate-trajectories.ps1',
 'scripts/test-write-promotion-gate.ps1',
 'scripts/test-run-candidate-trajectory-gate.ps1'
)
foreach($test in $tests){
  pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File $test
}
```

### Re-run the manual bundle gate

```powershell
$dir='C:\RIFT MODDING\RiftReader\scripts\captures\manual-bundle-001-sloped-10point-coord-calibration-20260430-180012\stream-1hz-20260430-182451'
$truth=Join-Path $dir 'overlay-coords-manual-extract.csv'
$memory=Join-Path $dir 'memory'
$out=& pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts/run-candidate-trajectory-gate.ps1 `
  -TruthCsv $truth `
  -MemoryDirectory $memory `
  -BundleDirectory $dir `
  -AllowPromotionFailure `
  -Json 2>&1
$out | ConvertFrom-Json -Depth 80 | Select-Object status,promotionAllowed,scoresFile,promotionGateFile,gateFailures | Format-List
```

Expected result: `promotion-blocked`, `promotionAllowed=false`.

## Safety / policy constraints to preserve

| Constraint | Why |
|---|---|
| Do not treat `ReaderBridgeExport.lua` or any SavedVariables file as live coordinate truth. | SavedVariables are post-save snapshots, not live IPC. |
| Do not promote static-cache, stale, wrong-origin, or stationary-tail-drift candidates. | These are negative/candidate evidence only. |
| Use `promotion-gate.json` as the final promotion authority. | Prevents accidental candidate promotion from scorer rank alone. |
| No live Rift input unless the user explicitly approves it. | Current work was offline only. |
| If live capture resumes, use overlay/live telemetry/native memory truth surfaces, not stale SavedVariables. | Keeps captures current-session valid. |

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit this handoff if you want it preserved in repo history. | The handoff file is newly created after `83f0ec5`. |
| 2 | Push local `main` when ready. | Local `main` is ahead of `origin/main` by 2 commits before this handoff. |
| 3 | Add a short README/runbook section for `run-candidate-trajectory-gate.ps1`. | Makes future scoring/gating repeatable without reading code. |
| 4 | Add a one-command offline validation script. | Reduces manual test friction and missed checks. |
| 5 | Use the gate wrapper for every future coord candidate bundle. | Keeps promotion fail-closed and comparable. |
| 6 | Capture a fresh approved live ChromaLink telemetry bundle. | Current manual bundle only proves static-cache negative evidence. |
| 7 | Score future live bundles with explicit movement/stationary sample windows. | Avoids stationary-tail bias. |
| 8 | Add `promotion-gate.json` summaries to future handoffs. | Makes promotion status obvious at resume. |
| 9 | Keep CE out unless explicitly re-approved. | Current lane is no-CE/live telemetry + memory evidence. |
| 10 | Promote a coordinate candidate only when `promotionAllowed=true`. | Preserves the evidence threshold and prevents stale candidate promotion. |

## Ready-to-paste resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read the newest handoff first: docs\handoffs\2026-04-30-202832-promotion-gate-handoff.md. Then check git status/log. Continue from the candidate trajectory promotion gate work: local main has commits b1db3a1 and 83f0ec5 ahead of origin/main, the manual bundle correctly fails promotion as static-cache, and SavedVariables must not be used as live truth. Do not use live Rift input unless I explicitly approve it.
```
