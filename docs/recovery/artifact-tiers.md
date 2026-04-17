# Artifact Tiers

Use this file to decide what must survive, what can be regenerated, and what can be ignored.

## Tier 1 - preserve or rebuild first

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-stat-hub-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json`

## Tier 2 - useful, but easy to re-derive

- `camera-alts-stimulus-safe.json`
- `camera-altz-stimulus-safe.json`
- `player-source-accessor-family.json`
- `session-watchset.json`
- `walk-owner-state-pointers.json`

## Tier 3 - historical evidence

- old session packages under `C:\RIFT MODDING\RiftReader\scripts\sessions\...`
- old camera candidate scans such as `camera-yaw-candidates.json` and `deep-scan-entry15.json`
- older `tmp-*`, `region-*`, and handoff-specific captures
- `C:\RIFT MODDING\RiftReader\scripts\captures\ce-debugger-attach-failures.csv`

## Tier 4 - disposable debug output

- screenshot debris in `C:\RIFT MODDING\RiftReader\artifacts\`
- one-off probe leftovers
- temporary helper dumps

## Rule

If recovery is needed:
1. rebuild Tier 1
2. regenerate Tier 2 if still needed
3. use Tier 3 only for comparison
4. ignore Tier 4 unless a specific bug needs it
