# Recovery

Start here if artifacts, notes, or workflow state drift or get corrupted.

## Current post-update note

After the April 14, 2026 game update:

- `player-current` and the coord-anchor module pattern still survived
- the source-chain / selector-owner / owner-components refresh path drifted
- actor-orientation and camera notes below the recovery layer should be treated
  as historical until rebuilt

Start with:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`

## Use these files only

1. `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
2. `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md`
3. `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-workflow.md`
4. `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-prompt.json`
5. `C:\RIFT MODDING\RiftReader\docs\recovery\artifact-tiers.md`
6. `C:\RIFT MODDING\RiftReader\docs\recovery\ce-reintegration-ranked-todo.md`
7. `C:\RIFT MODDING\RiftReader\docs\recovery\actor-yaw-recovery-prompt.json`

## Rules

- `current-truth.md` = what is true right now
- `rebuild-runbook.md` = what order to rebuild in
- `focused-postmessage-discovery-workflow.md` = the backup detailed live discovery workflow that recovered actor yaw quickly and should be reused for future feature recovery/discovery
- `focused-postmessage-discovery-prompt.json` = machine-readable execution packet for the same focused-PostMessage workflow, generalized for future live feature recovery/discovery
- `artifact-tiers.md` = what to preserve vs regenerate vs ignore
- `ce-reintegration-ranked-todo.md` = ranked CE workflow reintegration checklist and hold items
- `actor-yaw-recovery-prompt.json` = older actor-yaw-specific recovery packet; keep as a historical branch-specific reference when comparing the pre-win and post-win approaches
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
