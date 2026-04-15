# Artifact Retention

Updated: 2026-04-15

## Goal

Reduce local file count and clutter without losing high-value reverse-engineering evidence.

## Keep in active working set

### Current actor-orientation pipeline
- `scripts/captures/actor-orientation-candidate-ledger.ndjson`
- `scripts/captures/actor-orientation-candidate-screen-history.ndjson`
- `scripts/captures/actor-orientation-candidate-screen.json`
- `scripts/captures/actor-orientation-recovery.json`
- `scripts/captures/actor-orientation-offline-analysis.json`
- `scripts/captures/screening/*.json`

### Key reference captures to preserve
- `scripts/captures/post-update-triage-bundle.json`
- `scripts/captures/player-owner-components.json`
- `scripts/captures/player-selector-owner-trace.json`
- `scripts/captures/player-source-chain.json`
- `scripts/captures/player-owner-graph.json`
- `scripts/captures/player-stat-hub-graph.json`
- `scripts/captures/player-coord-write-trace.json`
- `scripts/captures/player-coord-trace-cluster.json`
- `scripts/captures/session-watchset.json`
- `scripts/captures/readerbridge-orientation-probe.json`

## Archived during 2026-04 cleanup

### Low-value scratch or superseded captures
Moved under `scripts/captures/archive/2026-04-cleanup/`:
- `scratch/` for `tmp-*`
- `raw-region-traces/` for hotspot/region/CE write-trace captures
- `historical-camera/` for stale camera discovery artifacts on `main`
- `historical-addon-probes/` for older addon probe baseline/after/diff permutations

### Bulky visual artifacts
Moved out of the repo to:
- `C:\RIFT MODDING\RiftReader_local_archive\2026-04-cleanup`

A pointer file remains at:
- `artifacts/archive/ARCHIVE_LOCATION.txt`

## Safe to regenerate or remove locally
- `tools/rift-game-mcp/.runtime/`
- `tools/rift-game-mcp/node_modules/`
- `reader/RiftReader.Reader/bin/`
- `reader/RiftReader.Reader/obj/`
- `.kilo/`

## Cleanup rule

Keep a file in the active tree only if it is:
1. used by the current automation,
2. the best current reference for a still-useful discovery path, or
3. directly cited by current docs/analysis.

Archive scratch, one-off raw traces, screenshot spam, and stale branch-specific camera artifacts instead of deleting useful evidence.
