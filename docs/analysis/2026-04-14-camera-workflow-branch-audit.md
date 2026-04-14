# Camera Workflow Branch Audit (2026-04-14)

## Scope

This note documents what changed in the camera workflow after the April 14,
2026 game update, with emphasis on **where the authoritative scripts now live**
and **which camera findings remain historical-only until revalidated**.

This is a documentation pass, not a repair pass.

## Snapshot metadata

| Field | Value |
|---|---|
| Report date | `2026-04-14` |
| Game update/build date | `2026-04-14` |
| Branch inspected for camera workflow | `feature/camera-orientation-discovery` |
| Worktree used for branch inspection | `C:\RIFT MODDING\RiftReader_camera_feature` |
| Input mode | `read-only inspection only` |
| Validation status | `workflow located; post-update live camera offsets still unverified on main` |

## Commands / evidence sources checked

- inspected `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- inspected `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- inspected `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`
- inspected `C:\RIFT MODDING\RiftReader_camera_feature\docs\camera-orientation-discovery.md`
- inspected `C:\RIFT MODDING\RiftReader_camera_feature\docs\camera-discovery-findings.md`

## What changed

| Area | Current documentation state |
|---|---|
| `main` worktree camera helpers | missing |
| feature-branch camera helpers | present |
| post-update live camera revalidation on `main` | not done |
| last-known camera model | still available, but historical until rebuilt on the updated client |

## Branch / workflow authority

The active camera workflow is currently branch-specific:

- `main` does **not** contain the current live camera helper scripts referenced
  by older recovery notes
- `feature/camera-orientation-discovery` does contain them

Canonical scripts currently found on the feature branch:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\capture-camera-memory-dump.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\search-camera-global.ps1`

## Last-known historical camera model

The last documented camera model on the feature branch is:

- **Yaw**: read from the selected-source preferred orientation basis
- **Pitch**: derived from `entry15` duplicated orbit coordinates
- **Distance**: derived from the same orbit vector magnitude
- **Direct standalone pitch scalar**: still unresolved
- **Yaw mirror family**: `entry5`
- **Orbit-family mirrors**: `entry0`, `entry12`, `entry13`, `entry14`, `entry15`

Historical implementation details found in the inspected scripts/docs:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
  reads `entry15` orbit coordinates from `+0xA8/+0xAC/+0xB0` with a duplicate
  triplet at `+0xB4/+0xB8/+0xBC`
- derived pitch is computed from the player-to-camera orbit vector
- `C:\RIFT MODDING\RiftReader_camera_feature\docs\camera-orientation-discovery.md`
  explicitly says yaw is verified, pitch is usable via orbit derivation, and a
  direct pitch scalar remains unresolved

## What is historical only right now

Until the updated client is revalidated live, treat these as historical-only:

- selected-source basis as the current live yaw source
- `entry15` orbit coordinates as the current live pitch/distance source
- `entry5` as the current live yaw mirror
- any camera candidate captures generated before the April 14, 2026 update

## Practical implication for recovery docs

Recovery notes on `main` should no longer imply that camera live checks can be
run entirely from the `main` worktree.

They should say instead:

- camera live workflow currently lives on
  `feature/camera-orientation-discovery`
- the feature-branch model is the last known camera reference
- post-update camera offsets remain unverified until rerun against the updated
  client

## Immediate next step

Keep camera documentation split into:

1. living truth in `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
2. dated drift/branch audits in `C:\RIFT MODDING\RiftReader\docs\analysis\`
3. feature-branch camera procedure docs until the workflow is either merged or
   retired
