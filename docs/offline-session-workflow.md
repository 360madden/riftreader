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
  - schema-versioned process/module/sample metadata from the reader recorder
- `watchset.json`
  - schema-versioned named memory regions derived from the current artifact chain
- `samples.ndjson`
  - one sampled timeline row per interval
- `markers.ndjson`
  - start/end markers plus the initial label marker
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

## Commands

Export the current watchset only:

```powershell
C:\RIFT MODDING\RiftReader\scripts\export-discovery-watchset.cmd
```

Direct reader-side recording from an existing watchset:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --record-session --session-watchset-file C:\RIFT MODDING\RiftReader\scripts\captures\session-watchset.json --session-output-directory C:\RIFT MODDING\RiftReader\scripts\sessions\20260409-baseline --session-sample-count 20 --session-interval-ms 500 --session-label baseline --json
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

## What is implemented now

This change implements the first owned session slice:

- reader CLI support for `--record-session`
- reader CLI support for `--session-summary`
- artifact-driven watchset export
- package orchestration script that freezes artifacts + truth + sampled bytes
- schema-versioned `watchset.json`, `recording-manifest.json`, `package-manifest.json`, and `capture-consistency.json`
- explicit package integrity checks and missing-file reporting before success is reported
- explicit failed-package manifests when the owned package flow aborts after the session folder is created

It does **not** yet implement:

- automatic stimulus markers beyond start/end/label
- burst/high-frequency sampling
- offline decoder passes over recorded sessions
- a GUI capture tool

## Near-term next phases

1. add richer markers from manual/scripted stimuli
2. add offline reader modes that inspect/diff saved sessions
3. add targeted stat-diff helpers for hub decoding
4. drop CE only after session-driven decoding and reader parity are proven

## Operator notes

- use `C:\RIFT MODDING\RiftReader\docs\offline-session-troubleshooting.md`
  when a session folder exists but the package is failed or incomplete
- use `C:\RIFT MODDING\RiftReader\docs\offline-session-implementation-checklist.md`
  for the current foundation-slice backlog
