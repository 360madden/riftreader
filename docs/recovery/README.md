# Recovery

Start here if artifacts, notes, or workflow state drift or get corrupted.

Last reviewed: May 6, 2026.

## Current no-CE coord proof note

As of the May 6/7, 2026 resumed no-CE forward-proof lane, start coord-truth
recovery with:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
- `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-06-144456-current-readback-coord-truth-handoff.md`

The latest live target was `rift_x64` PID `47560` / HWND `0x2122E`. The old
handoff proof cache initially failed closed as stale, then the proof was
refreshed through the user-corrected RiftScan-first candidate workflow without
Cheat Engine and without SavedVariables live truth. The fresh proof anchor
promotes RiftScan candidate `rift-addon-coordinate-candidate-000001` at
`0x2400EA32120` from:

- RiftScan session: `C:\RIFT MODDING\Riftscan\sessions\codex-current-coord-region-passive-20260506-230940`
- RiftScan match file: `C:\RIFT MODDING\Riftscan\reports\generated\codex-current-coord-region-passive-20260506-230940-addon-coordinate-matches.json`
- proof anchor: `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`
- latest readback: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232245.json`
- tracked pointer: `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`

The latest proof-gated `1000 ms W` pulse passed and moved the validated proof
coordinate by planar distance `1.2391483387792066`. Movement is only allowed
after rerunning the current proof-anchor readback preflight for the exact live
PID/HWND, because the proof age gate is short-lived. CE plus SavedVariables
live-truth paths remain forbidden for this lane.

## Current post-update note

After the April 14, 2026 game update:

- `player-current` and the coord-anchor module pattern still survived
- the source-chain / selector-owner / owner-components refresh path drifted
- the April 22, 2026 recovery passes rebuilt the source-chain/accessor-family
  lane strongly enough to restore actor-facing truth
- the April 23, 2026 agentic actor-facing refresh pass promoted the current
  live lead again and refreshed the selector-owner / owner-components /
  owner-graph / stat-hub provenance lane on the same session
- navigation preflight now reuses that live actor-facing truth for a read-only
  turn hint, and `--navigate-waypoints` can now opt into pre-movement
  auto-turn; the first deliberately misaligned live correction proof plus
  forward-travel handoff passed in `navigation-prototype-20260423-195303-923`
- camera notes below the recovery layer should still be treated as historical
  until rebuilt

Start with:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-22-actor-facing-source-chain-behavior-backed-lead.md`

## Use these files only

1. `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
2. `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
3. `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md`
4. `C:\RIFT MODDING\RiftReader\docs\recovery\artifact-tiers.md`
5. `C:\RIFT MODDING\RiftReader\docs\navigation-waypoint-v1.md` when the task
   touches movement, preflight, smoke routes, or auto-turn behavior

## Rules

- `current-truth.md` = what is true right now
- `current-proof-anchor-readback.json` = tracked pointer to the latest validated
  current-readback coordinate proof
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
