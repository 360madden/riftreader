# Coord Discovery Workflow TODO — 2026-04-30

Status: **saved plan / not yet implemented**  
Scope: `C:\RIFT MODDING\RiftReader`  
Constraint: **No Cheat Engine for this lane unless explicitly re-approved.**

## TL;DR

Repo history from initial commit through April 30 shows the project already has most of the pieces needed for efficient coordinate reacquisition: ReaderBridge addon truth, native memory scans, offline session packaging, debug scanner tooling, proof gates, and handoff/current-truth docs.

**Major design correction:** RIFT addon `SavedVariables` files such as
`ReaderBridgeExport.lua` are not live IPC. They are post-save snapshots and
normally refresh only on `/reloadui`, logout, UI shutdown, or another client
save event. Future live coord bundles must use live overlay screenshots/OCR,
validated memory anchors, or another real live bridge as the live truth source.
SavedVariables-derived seeds must carry file timestamps and freshness labels.

The workflow gap is that these pieces are still too often run as separate one-off attempts. The next improvement should be a single reusable **coord evidence bundle** workflow:

> addon movement trace + exact input plan + native memory samples + candidate trajectory scoring + mirror/cache classification + no-CE pointer/base debug scan + promotion gate + next-seed packet.

## Current best seed

| Field | Value |
|---|---|
| Movement-backed candidate | `0x2C990DDE5C0` |
| Likely base | `0x2C990DDE4C0` |
| Coord offset | `+0x100` |
| Status | Current-session movement-backed and base-referenced; not yet restart-durable/proof-grade |
| Preferred next action | Run a bundled multi-vector trace and auto-score this seed plus nearby/mirror candidates |

## Main findings from repo-history review

| # | Finding | Workflow implication |
|---:|---|---|
| 1 | ReaderBridge addon and memory-reader correlation existed from the beginning. | Addon truth should be included in every live movement discovery run. |
| 2 | Offline session packaging already exists. | Coord reacquisition should emit replayable evidence bundles, not loose files. |
| 3 | Past proof-anchor/source-chain work shows restart durability needs provenance, not just matching coords. | Separate current-session proof from restart-reacquirable proof. |
| 4 | Lightweight nameplate reproof passed some gates but missed lead/pointer evidence needed for promotion. | Do not skip source/lead evidence when promotion depends on it. |
| 5 | Current Apr 30 no-CE work found a strong movement-backed candidate but no durable chain yet. | Next run should combine movement capture and debug scan automatically. |

## Candidate lifecycle states

Use these states in future coord packets and reports:

1. `discovered`
2. `movement-backed`
3. `base-referenced`
4. `source-linked`
5. `restart-reacquirable`
6. `proof-grade`

A candidate should not be called proof-grade unless it has current-session movement evidence, a valid source/provenance path, and a passing promotion gate.

## Required bundle artifacts

A future coord evidence bundle should write these artifacts under a timestamped run folder:

| Artifact | Purpose |
|---|---|
| `capture-plan.json` | PID/HWND, hypotheses, target seeds, input plan, required signals, stop conditions, authoritative truth surface |
| `run-summary.json` | Human/machine summary of result, blocker, and next action |
| `input-script.json` | Exact movement sequence executed or requested |
| `addon-trace.json` / `addon-trace.ndjson` | Live addon/runtime coordinate samples with timestamps and labels; do not source this from SavedVariables unless explicitly marked post-flush |
| `truth-surface.json` | Declares whether ground truth came from overlay/OCR, validated memory anchor, or post-flush SavedVariables |
| `savedvariables-freshness.json` | Records SavedVariables path, `LastWriteTimeUtc`, capture start/end, and freshness classification if any file-backed addon data was used |
| `memory-session/` | Native memory samples/watchset output |
| `candidate-trajectory-scores.json` | Candidate ranking vs addon trajectory |
| `mirror-cache-classification.json` | Primary/mirror/cache/static classification |
| `debug-scan-summary.json` | No-CE pointer/base/nearby refs for top candidates |
| `next-seeds.json` | Seeds for the next run to avoid rediscovery |
| `promotion-gate.json` | Fail-closed proof/promote decision and missing evidence |
| `current-truth-patch.json` | Exact proposed current-truth update if gate passes |

## Better live run shape

Avoid one short forward pulse as the default. Prefer a multi-vector movement trace that can be reused for multiple analyses:

1. Baseline stationary samples.
2. Forward movement.
3. Stop/pause.
4. Turn or heading change.
5. Forward movement after heading change.
6. Strafe or lateral movement if safe.
7. Backtrack or reverse direction if safe.
8. Final stop/pause.

The run should be rejected if movement is too small, recorder starts late, live truth is missing, PID/HWND changes, or candidate scoring cannot align memory samples to live truth timestamps. If the run depends on `ReaderBridgeExport.lua` as if it were live, reject it unless a deliberate post-flush snapshot timestamp proves that is the intended truth surface.

## Top 10 TODOs

| # | Action | Why |
|---:|---|---|
| 1 | Build `C:\RIFT MODDING\RiftReader\scripts\invoke-coord-candidate-bundle.ps1`. | Single command should run addon trace, movement, memory record, scoring, and no-CE debug scan. |
| 2 | Add a multi-vector exact-window movement plan. | W-only pulses are low-signal; include stop/turn/strafe/backtrack/pause when safe. |
| 3 | Add `candidate-trajectory-scores.json`. | Automatically rank memory candidates against addon movement trace. |
| 4 | Add lifecycle state to coord packets. | Prevent confusion between current-session, stale, proof-grade, and restart-durable. |
| 5 | Generate `next-seeds.json` after every scan. | Avoid rediscovering candidates from scratch. |
| 6 | Make no-CE debug scan part of the default bundle. | Pointer/base/ref evidence should be collected proactively. |
| 7 | Add coord `promotion-gate.json`. | Match stricter nameplate-style gate discipline. |
| 8 | Add mirror/cache classifier. | Past runs show synchronized mirrors and stale/static triplets can coexist. |
| 9 | Add run-quality fail-closed checks. | Reject bad evidence before it pollutes current-truth docs. |
| 10 | Start next bundle from `0x2C990DDE4C0 + 0x100`. | This is the best current no-CE movement-backed seed from the latest work. |

## SavedVariables design-flaw TODOs

| # | Action | Why |
|---:|---|---|
| 1 | Add `truth-surface.json` to every live bundle. | Prevents confusing overlay truth, memory truth, and post-flush file snapshots. |
| 2 | Add `savedvariables-freshness.json` when `ReaderBridgeExport.lua` is read. | Makes stale file-backed seeds obvious and machine-checkable. |
| 3 | Fail closed if `ReaderBridgeExport.lua` predates capture start and is being used as live truth. | Avoids repeating the `manual-bundle-001` stale-seed mistake. |
| 4 | Prefer overlay screenshot/OCR capture when no validated memory anchor exists. | It is a real live truth surface now. |
| 5 | Rebuild seed scans from extracted live overlay coordinates, not stale SavedVariables coordinates. | Produces candidates in the same time/domain as movement truth. |

## Implementation notes

- Keep this lane **no-CE** unless the user explicitly re-approves CE.
- Use ReaderBridge/addon runtime or overlay coordinates as validation/scaffolding and the native memory reader as the target truth surface. Do not treat `ReaderBridgeExport.lua` SavedVariables as a live feed.
- Every live run should be designed to support offline fan-out analysis after the game state changes.
- Prefer one high-signal bounded run over multiple short one-question runs.
- Do not promote cached/current-player heuristic anchors unless separately re-proven.
