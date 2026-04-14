# Recovery Documentation System

This folder is the repo-owned rebuild and recovery system for RiftReader.

Use it when:
- a key artifact is corrupted or missing
- a script or doc path drifted and you need the current truth
- a future session needs to rebuild the current reader/discovery state from scratch
- you need to separate current workflows from historical evidence

## File roles

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\docs\recovery\README.md` | index for the recovery system |
| `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` | current live facts, canonical scripts, and direct-vs-derived field status |
| `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md` | exact rebuild order when artifacts or docs are corrupted |
| `C:\RIFT MODDING\RiftReader\docs\recovery\artifact-tiers.md` | which artifacts are authoritative, rebuild-critical, historical, or disposable |

## Recovery rules

1. Treat `current-truth.md` as the fastest way to re-orient after drift.
2. Treat `rebuild-runbook.md` as the canonical rebuild order.
3. Treat `artifact-tiers.md` as the answer to "what must be preserved vs regenerated vs ignored?"
4. Historical handoff docs remain useful context, but they are **not** the active rebuild workflow.
5. When a meaningful discovery milestone is reached, update this recovery set in the same commit if practical.

## Minimum recovery package

If almost everything else is damaged, these should be enough to rebuild the active state:
- this recovery folder
- `C:\RIFT MODDING\RiftReader\CLAUDE.md`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1`

## Current rebuild bias

Rebuild the smallest trustworthy state first:
1. verify the reader layer
2. refresh the live owner/source chain
3. regenerate the core graph artifacts
4. verify the live camera read path
5. only then rebuild higher-level controller-search evidence
