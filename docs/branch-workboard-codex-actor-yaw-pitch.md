# Branch Workboard — `codex/actor-yaw-pitch`

Updated: 2026-04-15

## Purpose

This board is the current execution plan for the `codex/actor-yaw-pitch` branch.
It is optimized for low drift, bounded delegation, and easy retasking.

## Critical-path rule

The top-level integrator keeps these tasks local:

1. choose the next live retest candidate or candidate set,
2. decide whether evidence is good enough to trust or reject a candidate,
3. integrate evidence from scripts, docs, addon validation, and ranking outputs,
4. decide when the branch truth changes.

Everything else should be delegated only if the write/read scope is narrow and
materially helps the next critical-path decision.

## Lanes

### Lane A — Evidence / candidate triage

Owns:
- offline summaries of candidate state
- candidate comparison tables
- retest ordering recommendations
- provenance consolidation for the active orientation pipeline

Primary files:
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-ledger.ndjson`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-screen-history.ndjson`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-screen.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-offline-analysis.json`

### Lane B — Tooling / recovery scripts

Owns:
- candidate ranking heuristics
- ledger penalties and rejection reasons
- capture/recovery/screening script behavior
- reader CLI wiring for candidate search and triage

Primary files:
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Models\PlayerOrientationCandidateFinder.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Models\OrientationCandidateLedgerLoader.cs`
- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\recover-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\screen-actor-orientation-candidates.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`

### Lane C — Validation / addon support

Owns:
- addon-visible signal coverage
- test-envelope validation fields
- ReaderBridge probe interpretation
- public vs research addon contract notes

Primary files:
- `C:\RIFT MODDING\RiftReader\addon\ReaderBridgeExport\main.lua`
- `C:\RIFT MODDING\RiftReader\addon\RiftReaderValidator\main.lua`
- `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-orientation-probe.json`
- `C:\RIFT MODDING\RiftReader\docs\rift-api-capabilities.md`

### Lane D — Documentation / branch truth

Owns:
- current truth updates
- dated analysis notes
- branch workboard and handoff docs
- documentation of stale vs active evidence

Primary files:
- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\*.md`
- `C:\RIFT MODDING\RiftReader\docs\artifact-retention.md`
- `C:\RIFT MODDING\RiftReader\docs\branch-workboard-codex-actor-yaw-pitch.md`

### Lane E — Archive / artifact hygiene

Owns:
- active vs archived capture separation
- retention manifest updates
- keeping working-set clutter low without deleting useful evidence

Primary files:
- `C:\RIFT MODDING\RiftReader\docs\artifact-retention.md`
- `C:\RIFT MODDING\RiftReader\artifacts\archive\ARCHIVE_LOCATION.txt`
- `C:\RIFT MODDING\RiftReader\scripts\captures\archive\2026-04-cleanup\...`

## Now / Parallel now / Next / Parked

## Now

| Item | Lane | Why now |
|---|---|---|
| Choose the next live retest target from current evidence | Integrator | This is the current branch bottleneck. |
| Keep ranking pressure on pointer-hop false positives | B | Top-ranked candidates can still be stable-but-nonresponsive. |
| Keep screen/ledger/recovery outputs coherent | A | The branch depends on a single evidence story. |
| Keep current-truth aligned with actual branch findings | D | Prevents drift before the next conversation handoff. |

## Parallel now

| Item | Lane | Output required |
|---|---|---|
| Produce a concise ranked retest table from the latest offline analysis | A | one table + recommended retest order |
| Tighten rejection-reason/reporting clarity in one script family only | B | patch + validation note + changed files |
| Summarize addon-visible validation fields that help test-envelope trust | C | coverage note + gap list |
| Keep branch docs synchronized with the latest lane outputs | D | updated docs + stale/active note |
| Keep archive/retention docs current as cleanup changes land | E | manifest/doc update only |

## Next

| Item | Lane | Trigger |
|---|---|---|
| Re-run post-update triage with the current ledger-aware flow | B | after the next candidate-selection decision |
| Consolidate historical owner/source artifacts into a lighter reference summary | A or D | after live recovery pace stabilizes |
| Formalize addon stable vs research schema split | C + D | after current branch testing needs are clearer |
| Add a branch-local task board summary into README or recovery docs if needed | D | only if the branch workflow becomes stable enough |

## Parked

| Item | Reason parked |
|---|---|
| Camera rediscovery on `main` | not the branch critical path |
| Broad owner/source-chain rebuild | useful reference lane, but not the default first step right now |
| Large repo-wide refactors | too much drift risk while recovery is still unresolved |
| Extra cleanup beyond the current retention pass | no longer the best use of branch time |

## Retasking rules

Every delegated task must return:

- changed files,
- exact scope owned,
- validation attempted,
- doc impact,
- stale/active impact,
- best next retask within the same lane.

When a worker finishes:

1. reuse the same lane if possible,
2. prefer queued `Next` work over ad hoc new work,
3. do not retask into the critical path unless the integrator is blocked.

## Current evidence anchors

The current branch should assume these facts until superseded:

- the latest offline analysis shows **no trusted surviving positive candidate**,
- latest classification summary: `dead-nonresponsive=15`, `drifting=1`, `basis-unresolved=1`,
- pointer-hop candidates `0x245CDD91530@0xD4` and `0x245CDD820E0@0xD4` are currently top-ranked but rejected as stable nonresponsive,
- candidate `0x245B6D37C20@0xD4` is the notable drifting near-miss,
- background `PostMessage` is the trusted direct turn-stimulus path on this setup.

## Definition of ready for handoff

The branch is ready to hand off to a new conversation when:

1. this board is current,
2. `docs/recovery/current-truth.md` is not obviously stale,
3. the next retest target or next queued decision is written down,
4. archive/retention changes are documented,
5. the next conversation can start from docs instead of replaying the full thread.
