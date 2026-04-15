# Handoff — `codex/actor-yaw-pitch`

Updated: 2026-04-15

## Start here in the next conversation

Read these first, in order:

1. `C:\RIFT MODDING\RiftReader\docs\branch-workboard-codex-actor-yaw-pitch.md`
2. `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
3. `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-offline-analysis.json`
4. `C:\RIFT MODDING\RiftReader\docs\artifact-retention.md`

## Branch identity

- Repo: `C:\RIFT MODDING\RiftReader`
- Branch: `codex/actor-yaw-pitch`
- Main problem: recover a trustworthy live actor yaw/pitch source after the April 14, 2026 update without drifting back into stale owner/source assumptions.

## Current state summary

- low-level reader is still usable,
- ReaderBridge snapshot load is working,
- player current and coord-anchor baselines are still useful,
- owner/source refresh is still broken after the update,
- current branch workflow is centered on candidate screening + ledger + recovery + offline analysis,
- no current candidate is trusted yet.

## Most important current evidence

From `actor-orientation-offline-analysis.json`:

- `dead-nonresponsive = 15`
- `drifting = 1`
- `basis-unresolved = 1`
- no candidate currently has surviving positive evidence after the latest merge

Most notable named candidates:

- `0x245CDD91530@0xD4` — pointer-hop, stable nonresponsive
- `0x245CDD820E0@0xD4` — pointer-hop, stable nonresponsive
- `0x245B6D37C20@0xD4` — drifting near-miss (`idle_drift`)
- `0x245D64D1100@0x114` — basis unresolved

## Current workflow truth

- use addon-first orientation probing before old owner/source-chain assumptions,
- use background `PostMessage` for direct turn stimulus on this setup,
- do not treat pre-update owner/source/camera artifacts as current truth unless regenerated after the update.

## Active files / artifacts to preserve focus on

### Active pipeline artifacts
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-ledger.ndjson`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-screen-history.ndjson`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-candidate-screen.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-recovery.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-orientation-offline-analysis.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\screening\*.json`

### Reference captures still worth keeping
- `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-triage-bundle.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-source-chain.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-stat-hub-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-trace-cluster.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-orientation-probe.json`

## Delegation plan to resume from

### Keep local (integrator only)
- choose next live retest candidate
- decide when candidate evidence is trustworthy enough
- decide whether a lane result changes current truth

### Safe delegation lanes
- Lane A: evidence / candidate triage
- Lane B: tooling / recovery scripts
- Lane C: validation / addon support
- Lane D: documentation / branch truth
- Lane E: archive / artifact hygiene

Use the branch workboard doc as the live queue.

## Recommended first action in the next conversation

Start by asking for one of these two things explicitly:

1. **"Pick the next retest target from the latest offline analysis and explain why."**
2. **"Generate the first wave of delegated tasks from the branch workboard."**

That keeps the next conversation on the current critical path.

## Cleanup / archive note

The bulky visual artifacts were moved out of the repo to:

- `C:\RIFT MODDING\RiftReader_local_archive\2026-04-cleanup`

The pointer file is:

- `C:\RIFT MODDING\RiftReader\artifacts\archive\ARCHIVE_LOCATION.txt`

## Open risks

- docs and branch truth can drift if the next conversation ignores the workboard,
- pointer-hop candidates may keep ranking high while still being dead,
- stale pre-update artifacts can still mislead if reused as current truth,
- live retest time can be wasted if clean test-envelope validation is not enforced.
