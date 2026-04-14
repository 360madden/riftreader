# Offline Session Package Implementation Checklist

Scope: **Phase 1–3 foundations** for offline-session package completion.

This checklist is intentionally narrow:

- package integrity
- failure handling
- schema/versioning
- watchset hardening
- recorder robustness

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
- [ ] Add a final package-integrity check before the command reports success.
- [ ] Treat missing or partial artifacts as a failed package, not a warning-only run.
- [ ] Define what happens when recording is interrupted or aborted mid-run.
- [ ] Ensure failed runs either:
  - clean up partial output, or
  - mark the package explicitly as failed/incomplete.
- [ ] Surface integrity failures clearly in console output and generated JSON.
- [ ] Keep the package folder diffable and inspectable by hand.

## Phase 2 — Schema/versioning and watchset hardening

- [ ] Add an explicit schema/version field to all session artifacts that matter.
- [ ] Keep `package-manifest` the top-level summary for the session folder.
- [ ] Keep `recording-manifest` as the recorder-owned metadata source.
- [ ] Keep `watchset.json` as the single exported region list for sampling.
- [ ] Preserve freshness/provenance data from the current artifact chain.
- [ ] Flag stale or cross-run watchset inputs via `capture-consistency.json`.
- [ ] Keep selected-source lineage preferred when artifact sources disagree.
- [ ] Retain owner-component lineage as the preferred stable path.
- [ ] Treat legacy cache/blob-style regions as bootstrap-only, not final anchors.
- [ ] Sort watchset regions deterministically so the same inputs yield the same output.
- [ ] Detect duplicate or overlapping regions during watchset export.
- [ ] Add size/coverage guardrails so one bad artifact cannot explode capture scope.
- [ ] Keep watchset terminology aligned with current discovery names:
  - selected source object
  - owner object / owner container / owner state record
  - identity-bearing components
  - shared hubs

## Phase 3 — Recorder robustness

- [ ] Track sample timing drift during recording.
- [ ] Track per-sample capture duration.
- [ ] Track per-region read failures.
- [ ] Add graceful cancellation/stop support.
- [ ] Emit explicit interrupted-session markers when a run ends early.
- [ ] Normalize warning handling so repeated issues are deduplicated.
- [ ] Add package-size or sample-count guardrails.
- [ ] Support burst/high-frequency sampling without changing the package contract.
- [ ] Validate high-count and fast-interval behavior with smoke runs.
- [ ] Keep the recorder path isolated enough to validate independently of offline analysis.

## Completion criteria for this foundation slice

- [ ] One command can create a complete, valid package from a current watchset.
- [ ] Partial or failed runs are unambiguous.
- [ ] Package schema/versioning is stable enough for offline tools to consume safely.
- [ ] Watchset export is deterministic, provenance-aware, and guarded against stale inputs.
- [ ] Recorder behavior is stable under normal and burst sampling modes.

## Notes

- This checklist covers the package foundation only.
- Offline inspect, diff, and decode tooling belong to later phases.
- Reader CLI and addon validation remain supporting workflows, not the package contract itself.
