# Current Truth

_Last updated: April 20, 2026 (fresh no-CE actor-yaw / pitch revalidation on the live `rift_x64` session)_

## Current status

| Area | Status |
|---|---|
| Low-level reader | reliable enough for active work |
| ReaderBridge snapshot load | working |
| Player current read | working |
| Coord-anchor module pattern | working |
| ReaderBridge orientation probe | still empty on the current client |
| `--read-player-orientation` reader mode | still historical / stale because it depends on the owner-components artifact |
| `capture-actor-orientation.ps1` | working again for the current session through a live behavior-backed lead |
| Actor yaw / pitch truth | working again on the current live session via source `0x1B115201EB0` and forward basis row `+0xD4/+0xD8/+0xDC` |
| Source-chain refresh | still broken after the update |
| Selector-owner trace | still broken after the update |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |

## Fresh actor yaw / pitch truth

Fresh live validation on **April 20, 2026** established:

- canonical live source address: `0x1B115201EB0`
- canonical forward basis row:
  - `X = +0xD4`
  - `Y = +0xD8`
  - `Z = +0xDC`
- canonical up/right rows:
  - up = `+0xE0/+0xE4/+0xE8`
  - right = `+0xEC/+0xF0/+0xF4`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

Fresh live key-stimulus proof on the same source:

- before `A`: yaw `-93.2956`, pitch `0.0000`
- after `A`: yaw `63.0244`, pitch `0.0000`
- `A` delta: `+156.3200` degrees yaw, `0.0000` pitch
- before `D`: yaw `63.0244`, pitch `0.0000`
- after `D`: yaw `-92.4286`, pitch `0.0000`
- `D` delta: `-155.4530` degrees yaw, `0.0000` pitch

Operational interpretation:

- the current truth-bearing actor-facing basis is **not** the historical
  `+0x60/+0x94` layout
- those historical basis windows read as garbage on this live source and must
  not be promoted over the validated `+0xD4` row
- the repo now carries a behavior-backed lead file at:
  - `C:\RIFT MODDING\RiftReader_facing\scripts\actor-facing-behavior-backed-lead.json`
- `capture-actor-orientation.ps1` now prefers that lead when present and fails
  closed if the live basis no longer validates

See the fresh validation note:

- `C:\RIFT MODDING\RiftReader_facing\docs\analysis\2026-04-20-actor-yaw-pitch-behavior-backed-lead-validation.md`

## ReaderBridge / addon orientation status

Fresh inspection on **April 20, 2026** still showed:

- `orientationProbe` block present
- player unit available
- direct heading API unavailable
- direct pitch API unavailable
- no player detail/state/stat orientation candidates surfaced

So the addon/API lane still does **not** expose a usable direct orientation
signal on the current client. Actor yaw / pitch truth is currently coming from
the validated live memory basis above, not from ReaderBridge orientation fields.

## Broken or stale right now

- `capture-player-source-chain.ps1` still does not rebuild the expected live source chain
- `trace-player-selector-owner.ps1` can remain `armed` without a live hit
- `player-selector-owner-trace.json` is stale until regenerated with a current-process proof
- `player-owner-components.json` is stale until regenerated with a current-process proof
- `--read-player-orientation` remains stale until the owner/source artifact path is rebuilt

## Canonical scripts on `main`

- `C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\profile-actor-orientation-keys.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\refresh-readerbridge-export.ps1`

## Camera script location note

The currently documented live camera helpers are **not present** on the `main`
worktree during this pass.

The active camera workflow currently lives on:

- branch: `feature/camera-orientation-discovery`
- worktree: `C:\RIFT MODDING\RiftReader_camera_feature`

Relevant scripts there:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`

Do not treat camera outputs as current truth on `main` until the camera path is
revalidated on the updated client.
