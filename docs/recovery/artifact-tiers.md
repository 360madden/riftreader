# Artifact Tiers

This file answers: what should be preserved, what can be regenerated, and what is just historical context?

## Tier 1 - Rebuild-critical authoritative artifacts

These are the first artifacts to preserve or regenerate when recovering the repo state.

| Artifact | Why it matters |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json` | current selector → owner/source relationship |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json` | current owner/container/component table |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-graph.json` | current owner wrapper/backref/state graph |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-stat-hub-graph.json` | current shared-hub relationships for sibling/stat-side work |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json` | current basis/orientation capture |

If these are missing or stale, rebuild them before trusting anything above them.

## Tier 2 - Current derived helper artifacts

Useful, but derived from Tier 1 or regenerable quickly.

| Artifact | Role |
|---|---|
| `camera-alts-stimulus-safe.json` | current safe Alt+S helper result |
| `camera-altz-stimulus-safe.json` | current safe Alt+Z helper result |
| `player-source-accessor-family.json` | outward-trace helper from current source chain |
| `session-watchset.json` | owned watchset derived from current discovery state |
| `walk-owner-state-pointers.json` | exploratory pointer-walk evidence |

Keep when useful, but do not treat them as the root truth.

## Tier 3 - Historical evidence

Keep for comparison, but do not use as the first rebuild source.

| Artifact class | Examples |
|---|---|
| old session packages | `C:\RIFT MODDING\RiftReader\scripts\sessions\...` |
| older camera candidate scans | `camera-yaw-candidates.json`, `deep-scan-entry15.json` |
| old handoff-specific captures | older `tmp-*` and `region-*` evidence |

These are useful for regressions, not for first rebuild.

## Tier 4 - Disposable / low-value debris

Useful only for narrow debugging. Safe to regenerate or prune.

| Artifact class | Examples |
|---|---|
| raw screenshots in `artifacts\` | before/after PNGs from input validation |
| temporary helper dumps | `tmp-*` text/json probes |
| one-off ad hoc experiment output | probe leftovers no longer used by the active workflow |

## Preservation rule

When a session produces something important, preserve:
1. Tier 1 first
2. Tier 2 if it materially explains the state
3. Tier 3 only when it provides comparison value
4. Tier 4 only when a specific bug/debug issue needs it

## Rebuild bias

If the repo is partially corrupted, do not try to save everything.
Rebuild the Tier 1 set first, then re-derive Tier 2 from the live process.
