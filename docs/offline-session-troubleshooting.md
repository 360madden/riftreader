# Offline Session Troubleshooting

Use this guide when an offline session package is **missing files**, **ends early**, **fails to load offline**, or looks **partial/incomplete**.

## Expected package location

Session packages are written under:

- `C:\RIFT MODDING\RiftReader\scripts\sessions\<session-id>\`

A healthy package normally includes:

- `package-manifest.json`
- `recording-manifest.json`
- `watchset.json`
- `samples.ndjson`
- `markers.ndjson`
- `modules.json`
- `capture-consistency.json`
- `readerbridge-snapshot.json` when truth is available
- `artifacts\`

## First checks

1. Confirm the command completed without interruption.
2. Open the session folder and verify the expected files exist.
3. Check whether `package-manifest.json` is present and whether `Status` /
   `IntegrityStatus` report `complete` / `ok`, `warning`, or `failed`.
4. Check `capture-consistency.json` for stale or cross-run warnings.
5. Confirm the selected process was actually `rift_x64`.
6. Run `--session-summary --json` and inspect:
   - `Warnings`
   - `RecordingManifest.Interrupted`
   - `RecordingManifest.TotalRegionReadFailures`
   - `MarkerKinds`
   - `Regions`

Quick summary command:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --session-summary --session-directory C:\RIFT MODDING\RiftReader\scripts\sessions\<session-id>
```

## Common failure modes

### 1) Session folder exists, but files are missing

Likely cause:

- the run was interrupted
- the recorder or package-integrity check failed before final success
- the source watchset was incomplete

What to do:

- treat the package as failed/incomplete if `package-manifest.json` reports
  `Status = failed` or `IntegrityStatus = failed`
- re-run the full capture with a fresh session ID
- regenerate the watchset first if the source chain changed

If the session folder exists but `package-manifest.json` is missing entirely,
assume the run predates the hardened package flow or died before the manifest
could be written. Do not trust it as a valid offline package.

### 2) `capture-consistency.json` reports stale or mismatched artifacts

Likely cause:

- the artifact chain belongs to an older Rift process
- the selected source lineage changed
- the watchset was exported from stale discovery data

What to do:

- refresh the discovery chain before recording
- re-run:

```powershell
C:\RIFT MODDING\RiftReader\scripts\refresh-discovery-chain.ps1
```

- then re-export the watchset:

```powershell
C:\RIFT MODDING\RiftReader\scripts\export-discovery-watchset.cmd
```

### 3) `readerbridge-snapshot.json` is missing

Likely cause:

- ReaderBridge truth was unavailable at capture time
- the optional live-truth refresh was skipped or failed

What to do:

- verify the addon export is running if truth is required
- rerun the package with live truth refresh if needed

```powershell
C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.cmd -Label baseline -SampleCount 20 -IntervalMilliseconds 500 -RefreshReaderBridge
```

### 4) Samples exist, but the capture looks too short

Likely cause:

- `-SampleCount` was too small
- `-IntervalMilliseconds` was too large
- the session ended early
- the operator cancelled the recording intentionally

What to do:

- increase sample count for the scenario
- reduce interval only if the reader and target process can keep up
- verify the recorder stayed attached for the full run
- inspect `recording-manifest.json` for:
  - `Interrupted`
  - `RecordedSampleCount`
  - `MarkerCount`
  - `TotalRegionReadFailures`

### 5) The package loads, but `--session-summary` reports timing drift or burst warnings

Likely cause:

- sampling interval was intentionally very small
- the requested byte budget was too large for the sample cadence
- the target process or reader could not keep up cleanly

What to do:

- review `MaxTimingDriftMilliseconds` and `MaxCaptureDurationMilliseconds`
- reduce watchset scope if too many bytes are being sampled every interval
- increase `-IntervalMilliseconds` when the run is meant to be stable instead of bursty
- keep burst-mode packages for short stimulus windows only

### 6) External markers did not appear in `markers.ndjson`

Likely cause:

- `--session-marker-input-file` was not supplied to `--record-session`
- the marker file path did not match the one being watched
- the marker input line was malformed JSON
- PowerShell execution policy blocked `append-session-marker.ps1`

What to do:

- confirm the recording manifest reports `SessionMarkerInputFile`
- append a marker with:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File C:\RIFT MODDING\RiftReader\scripts\append-session-marker.ps1 -File <marker-input.ndjson> -Kind note -Message "smoke"
```

- inspect `Warnings` from `--session-summary --json` for marker-input parse errors
- verify the marker file is outside the recorder-managed output files (`markers.ndjson`, `samples.ndjson`, etc.)

### 7) Watchset exports but the region set looks wrong

Likely cause:

- selected-source lineage is stale
- owner-component lineage was not the preferred path
- legacy cache/blob regions were promoted too early

What to do:

- regenerate the discovery chain
- confirm the current artifact chain before exporting the watchset
- prefer owner-component lineage over stale fallback paths

## Recovery workflow

When a package looks bad, use this sequence:

1. Refresh the discovery chain.
2. Export the watchset again.
3. Re-run the owned package flow.
4. Verify the new session folder contains all expected files.

Recommended commands:

```powershell
C:\RIFT MODDING\RiftReader\scripts\refresh-discovery-chain.ps1
C:\RIFT MODDING\RiftReader\scripts\export-discovery-watchset.cmd
C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.cmd -Label baseline -SampleCount 20 -IntervalMilliseconds 500
```

## When to discard a capture

Discard the session and start over if:

- the package is missing core files
- the process target was wrong
- the session was interrupted mid-run
- timing drift or capture duration warnings show the package could not keep up
- the watchset clearly came from stale artifacts
- the package cannot be trusted for offline decode or diff work

## Notes

- Offline session packages are meant to be diffable and easy to inspect by hand.
- A partial session should be treated as evidence of a failed run, not a valid package.
- `package-manifest.json` is the authoritative top-level summary for session
  status and integrity.
- `recording-manifest.json` is the authoritative recorder-side source for
  interruption state, marker counts, region summaries, and byte/read-failure totals.
- If the recorder keeps failing, investigate the current artifact chain before changing sample settings.
