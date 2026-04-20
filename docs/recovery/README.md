# Recovery

Start here if artifacts, notes, or workflow state drift or get corrupted.

## Current post-update note

After the April 14, 2026 game update:

- `player-current` and the coord-anchor module pattern still survived
- the source-chain / selector-owner / owner-components refresh path drifted
- actor-orientation and camera notes below the recovery layer should be treated
  as historical until rebuilt
- the repo-native rebuild gate for actor yaw is now
  `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1`; only a
  run whose `actor-yaw-debug-workflow.json` reports
  `Promotion.PromotionReady = true` should be promoted into current truth

## Truth policy

Establish truth in this order:

1. **reader-native baseline first**
   - ReaderBridge snapshot
   - `--read-player-current`
   - `--read-player-coord-anchor`
2. **current-process pattern / module scans second**
   - use these to rebase live addresses in the active `rift_x64.exe`
3. **Cheat Engine only as bounded last-mile validation**
   - use CE only when the remaining question truly requires debugger-level proof

Cheat Engine is **not baseline infrastructure** for current truth.

- CE failures are tooling blockers, not truth by themselves
- stale artifacts may be pattern hints, but they are not live authority
- any artifact with `TraceMatchesProcess = false` is not authoritative for live
  addresses

Start with:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`

## Use these files only

1. `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
2. `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md`
3. `C:\RIFT MODDING\RiftReader\docs\recovery\artifact-tiers.md`

## Rules

- `current-truth.md` = what is true right now
- `rebuild-runbook.md` = what order to rebuild in
- `artifact-tiers.md` = what to preserve vs regenerate vs ignore
- `C:\RIFT MODDING\RiftReader\docs\analysis\README.md` = how to record dated
  update/drift investigations without overwriting current truth
- historical handoff docs are background only unless one of the files above sends you there

## Camera branch note

The current live camera workflow is branch-specific:

- living recovery truth stays on `main`
- the active camera discovery scripts currently live on
  `feature/camera-orientation-discovery`
- inspected worktree path:
  `C:\RIFT MODDING\RiftReader_camera_feature`
