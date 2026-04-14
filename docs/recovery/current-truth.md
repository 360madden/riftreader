# Current Truth

_Last updated: April 14, 2026 (post-update triage)_

## Current status

| Area | Status |
|---|---|
| Low-level reader | reliable enough for active work |
| ReaderBridge snapshot load | working |
| Player current read | working |
| Coord-anchor module pattern | working |
| Source-chain refresh | broken after the update |
| Selector-owner trace | broken after the update |
| Player orientation read | stale; resume actor yaw/pitch recovery via addon-first orientation probing before rebuilding the old owner/source chain |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |

## Post-update note

Use this report before trusting older actor/camera captures:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-live-camera-script-behavior-and-offset-drift.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-actor-orientation-stop-point-and-resume-plan.md`
- `C:\RIFT MODDING\RiftReader\docs\input-safety.md`

## Surviving baselines

### Player current

Still working from the cache/blob family:

- family id: `fam-6F81F26E`
- signature: `level@-144|health[1]@-136|health[2]@-128|health[3]@-120|coords@0`

### Coord anchor

Still working as a module-local pattern:

- pattern: `F3 0F 10 86 5C 01 00 00`
- updated module offset observed during triage: `0x93560E`
- inferred coord offsets: `0x158 / 0x15C / 0x160`

## Broken or stale right now

- `capture-player-source-chain.ps1` no longer locates the expected source-container load
- `trace-player-selector-owner.ps1` can remain `armed` without a hit
- `player-selector-owner-trace.json` is stale until regenerated
- `player-owner-components.json` is stale until regenerated
- `player-actor-orientation.json` is stale until regenerated

## Actor yaw / pitch recovery direction

The current recommended recovery path is:

1. addon-first orientation probing
2. export any API-visible heading / pitch / facing candidates
3. only then fall back to raw-memory rediscovery if the addon layer yields nothing useful

Do **not** treat the old debugger-driven owner/source chain as the default first
step for actor yaw / pitch recovery on the updated client. Use:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-actor-orientation-stop-point-and-resume-plan.md`

## Canonical scripts on `main`

- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`

## Camera script location note

The currently documented live camera helpers are **not present** on the `main`
worktree during this post-update triage pass.

The active camera workflow currently lives on:

- branch: `feature/camera-orientation-discovery`
- worktree: `C:\RIFT MODDING\RiftReader_camera_feature`

Relevant scripts there:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`

Do not treat camera outputs as current truth on `main` until the actor/source
chain is rebuilt and the camera path is revalidated on the updated client.

## Camera offset drift snapshot

As of `2026-04-14`, these old camera references are **historical only**:

- yaw basis on selected-source:
  - `+0x60/+0x68/+0x78`
  - duplicate `+0x94/+0x9C/+0xAC`
- pitch / distance via `entry15` orbit coordinates:
  - `+0xA8/+0xAC/+0xB0`
  - duplicate `+0xB4/+0xB8/+0xBC`

The last-known pre-update object addresses used for that model are now stale:

- selected-source base: `0x1FDA0D13170`
- `entry15` base: `0x1FD9FA6F190`

Direct raw reads against those addresses failed during the live drift check, so
they should not be reused as current offsets without a fresh object recovery.

Preferred live camera probe for post-update work:

- `C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1`

Do **not** use the legacy angle-candidate script as the default live camera
probe path.

## Tier-1 artifacts

These remain Tier 1, but they are currently **pre-update stale** until rebuilt:

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-stat-hub-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json`

## Do not trust these as current truth

- pre-update owner/source/actor-orientation artifacts unless regenerated after the update
- selected-source `+0xB8..+0x150` camera window
- selected-source `+0x7D0` camera basis idea
- `entry4 +0x1D0` as a confirmed direct pitch scalar
