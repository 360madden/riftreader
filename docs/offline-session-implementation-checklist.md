# Offline Session Package Implementation Checklist

Scope: **Phase 1–5 foundations** for offline-session package completion.

This checklist is intentionally narrow:

- package integrity
- failure handling
- schema/versioning
- watchset hardening
- recorder robustness
- marker/event capture
- offline inspection

## Phase 1 — Package integrity and failure handling

- [ ] Re-run the full package flow on a known-good live session.
- [ ] Verify every successful session writes the expected core artifacts:
  - `package-manifest.json`
  - `recording-manifest.json`
  - `watchset.json`
  - `samples.ndjson`
  - `markers.ndjson`
  - `modules.json`
  - `capture-consistency.json`
  - `readerbridge-snapshot.json` when truth is available
  - `artifacts\`
- [x] Add a final package-integrity check before the command reports success.
- [x] Treat missing or partial artifacts as a failed package, not a warning-only run.
- [ ] Define what happens when recording is interrupted or aborted mid-run.
- [x] Ensure failed runs either:
  - clean up partial output, or
  - mark the package explicitly as failed/incomplete.
- [x] Surface integrity failures clearly in console output and generated JSON.
- [ ] Keep the package folder diffable and inspectable by hand.

## Phase 2 — Schema/versioning and watchset hardening

- [x] Add an explicit schema/version field to all session artifacts that matter.
- [x] Keep `package-manifest` the top-level summary for the session folder.
- [x] Keep `recording-manifest` as the recorder-owned metadata source.
- [x] Keep `watchset.json` as the single exported region list for sampling.
- [x] Preserve freshness/provenance data from the current artifact chain.
- [x] Flag stale or cross-run watchset inputs via `capture-consistency.json`.
- [x] Keep selected-source lineage preferred when artifact sources disagree.
- [x] Retain owner-component lineage as the preferred stable path.
- [x] Treat legacy cache/blob-style regions as bootstrap-only, not final anchors.
- [x] Sort watchset regions deterministically so the same inputs yield the same output.
- [x] Detect duplicate or overlapping regions during watchset export.
- [x] Add size/coverage guardrails so one bad artifact cannot explode capture scope.
- [x] Keep watchset terminology aligned with current discovery names:
  - selected source object
  - owner object / owner container / owner state record
  - identity-bearing components
  - shared hubs

## Phase 3 — Recorder robustness

- [x] Track sample timing drift during recording.
- [x] Track per-sample capture duration.
- [x] Track per-region read failures.
- [x] Add graceful cancellation/stop support.
- [x] Emit explicit interrupted-session markers when a run ends early.
- [x] Normalize warning handling so repeated issues are deduplicated.
- [x] Add package-size or sample-count guardrails.
- [x] Support burst/high-frequency sampling without changing the package contract.
- [x] Validate high-count and fast-interval behavior with smoke runs.
- [x] Keep the recorder path isolated enough to validate independently of offline analysis.

## Phase 4 — Marker/event system

- [x] Expand marker schema beyond start/end/label.
- [x] Support manual markers via `--session-marker-input-file`.
- [x] Support script-driven markers via `append-session-marker.ps1`.
- [x] Normalize marker kinds so common stimulus names stay stable.
- [x] Capture marker source and structured metadata.
- [x] Align markers to nearby sample windows via `SampleIndex`.
- [x] Validate marker ordering and marker/sample alignment during offline inspection.
- [x] Summarize marker counts and marker kinds in package and recording manifests.
- [x] Document the marker workflow for manual/scripted stimulus tagging.

## Phase 5 — Offline inspection foundation

- [x] Load package manifests without attaching to a live process.
- [x] Load recording manifests, sample NDJSON, and marker NDJSON as one inspection result.
- [x] Surface required-region read-failure summaries from the recorded package.
- [x] Surface recent marker timeline data in text output.
- [x] Surface ReaderBridge truth context when a frozen snapshot is present and loadable.
- [x] Surface module/process summary from the recording manifest.
- [x] Emit machine-readable JSON with package + recording + samples + markers + region summaries.
- [x] Keep raw recorded region/sample bytes accessible through offline JSON output.

## Completion criteria for this foundation slice

- [ ] One command can create a complete, valid package from a current watchset.
- [x] Partial or failed runs are unambiguous.
- [x] Package schema/versioning is stable enough for offline tools to consume safely.
- [x] Watchset export is deterministic, provenance-aware, and guarded against stale inputs.
- [x] Recorder behavior is stable under normal and burst sampling modes.
- [x] Manual/scripted markers can be appended without changing the package contract.
- [x] Offline inspection can summarize a recorded package without live process access.

## Notes

- This checklist covers the package foundation only.
- Package diff and targeted decoders still belong to later phases.
- Reader CLI and addon validation remain supporting workflows, not the package contract itself.
- `--session-summary` now loads package + recording manifest + samples + markers
  into one offline inspection result without attaching to a live process.
