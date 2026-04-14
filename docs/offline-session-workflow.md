# Offline Session Workflow

## Why this exists

Cheat Engine, x64dbg, and similar tools remain the **live acquisition workbench**
for RiftReader. They are still the fastest path for:

- scans
- access/write tracing
- structure inspection
- manual probe validation

But the project now also needs a **repo-owned evidence format** so discoveries can
be replayed and decoded after the game session ends.

The goal is not to replace CE today. The goal is to make CE-discovered evidence
portable enough that the reader can eventually stand on its own.

## Workflow split

- **Cheat Engine / third-party tools**
  - live discovery
  - trace generation
  - confirmation of candidate paths
- **RiftReader-owned session package**
  - freezes the artifact set used for a run
  - exports a named watchset
  - samples named memory regions into one session folder
  - preserves a ReaderBridge truth snapshot when available
  - enables offline decode/diff work later

## MVP package layout

The first owned session workflow writes a folder under:

- `C:\RIFT MODDING\RiftReader\scripts\sessions\<session-id>\`

Current package contents:

- `package-manifest.json`
  - top-level package summary, status, integrity result, and missing-file report
- `recording-manifest.json`
  - schema-versioned process/module/sample metadata from the reader recorder,
    including timing drift, capture duration, marker summaries, region summaries,
    interruption state, and byte/read-failure totals
- `watchset.json`
  - schema-versioned named memory regions derived from the current artifact chain
- `samples.ndjson`
  - one sampled timeline row per interval
- `markers.ndjson`
  - built-in lifecycle markers plus manual/scripted external markers
- `modules.json`
  - current module list for the attached process
- `capture-consistency.json`
  - schema-versioned provenance / freshness warnings from the live capture set
- `readerbridge-snapshot.json`
  - frozen ReaderBridge truth when available
- `artifacts\`
  - copied capture artifacts used to build the watchset

This is intentionally a folder, not one binary blob, so it stays diffable and
easy to inspect by hand.

Integrity rule:

- a session folder is only a valid package when `package-manifest.json` is present
  and its `Status` / `IntegrityStatus` do not report failure
- incomplete or failed runs should be treated as invalid evidence, even if some
  component files were written

## Watchset design

The watchset is the bridge between the current discovery scripts and offline
recording.

Current watchset sources:

- `player-owner-components.json`
- `player-selector-owner-trace.json`
- `player-source-accessor-family.json`
- `player-stat-hub-graph.json`
- `player-current-anchor.json`

Current region priorities:

1. selected source object and its proven field offsets
2. owner object / owner container / owner state record
3. identity-bearing components
4. top ranked shared hubs
5. legacy cache/blob window as bootstrap only

Important rule:

- if the current artifacts disagree on selected source lineage, the watchset still
  exports, but stale paths are marked via warnings and only the owner-component
  lineage is treated as preferred
- exported regions are now sorted deterministically and guarded so one bad artifact
  cannot silently explode the watchset surface area
- overlap warnings are aimed at suspicious required-region collisions while still
  allowing expected parent/child coverage within the current discovery model

## Commands

Export the current watchset only:

```powershell
C:\RIFT MODDING\RiftReader\scripts\export-discovery-watchset.cmd
```

Direct reader-side recording from an existing watchset:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --record-session --session-watchset-file C:\RIFT MODDING\RiftReader\scripts\captures\session-watchset.json --session-output-directory C:\RIFT MODDING\RiftReader\scripts\sessions\20260409-baseline --session-marker-input-file C:\RIFT MODDING\RiftReader\scripts\sessions\20260409-baseline\marker-input.ndjson --session-sample-count 20 --session-interval-ms 500 --session-label baseline --json
```

Full owned package flow:

```powershell
C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.cmd -Label baseline -SampleCount 20 -IntervalMilliseconds 500
```

Optional live-truth refresh before packaging:

```powershell
C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.cmd -Label moved -SampleCount 20 -IntervalMilliseconds 250 -RefreshReaderBridge
```

Offline package summary:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --session-summary --session-directory C:\RIFT MODDING\RiftReader\scripts\sessions\20260409-baseline --json
```

Append a manual/scripted stimulus marker during a recording window:

```powershell
powershell -ExecutionPolicy Bypass -File C:\RIFT MODDING\RiftReader\scripts\append-session-marker.ps1 -File C:\RIFT MODDING\RiftReader\scripts\sessions\20260409-baseline\marker-input.ndjson -Kind combat-start -Label baseline -Message "entered combat" -Source manual
```

## What is implemented now

This change implements the current owned session foundation:

- reader CLI support for `--record-session`
- reader CLI support for `--session-summary`
- artifact-driven watchset export
- package orchestration script that freezes artifacts + truth + sampled bytes
- schema-versioned `watchset.json`, `recording-manifest.json`, `package-manifest.json`, and `capture-consistency.json`
- explicit package integrity checks and missing-file reporting before success is reported
- explicit failed-package manifests when the owned package flow aborts after the session folder is created
- per-sample timing drift and capture duration metrics
- per-region read-failure and byte-count summaries
- graceful cancellation with explicit interrupted-session markers and manifest state
- burst/high-frequency sampling support without changing the package file contract
- manual/scripted marker ingestion through `--session-marker-input-file`
- `append-session-marker.ps1` helper for one-off external marker writes
- offline package inspection that loads package + recording manifest + samples + markers
- offline JSON output that exposes raw sample bytes, region summaries, marker timeline data, and frozen ReaderBridge truth when available

It does **not** yet implement:

- package-vs-package diff reports
- targeted offline decoder passes over recorded sessions
- a GUI capture tool

## Near-term next phases

1. add package-vs-package diff reports
2. add targeted stat-diff and coord/orientation decode helpers
3. add curated capture scenarios and regression corpus packages
4. drop CE only after session-driven decoding and reader parity are proven

## Operator notes

- use `C:\RIFT MODDING\RiftReader\docs\offline-session-troubleshooting.md`
  when a session folder exists but the package is failed or incomplete
- use `C:\RIFT MODDING\RiftReader\docs\offline-session-implementation-checklist.md`
  for the current foundation-slice backlog
- `--session-summary --json` is now the package-first inspect entry point when
  you need raw sample bytes, marker timelines, region summaries, or frozen truth
  without attaching to a live Rift process
