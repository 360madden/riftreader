# Current Truth

_Last updated: April 20, 2026 (live actor-coordinate + actor-orientation truth operationalized in `RiftReader.Reader`)_

## Current status

| Area | Status |
|---|---|
| Low-level reader | reliable enough for active work |
| ReaderBridge snapshot load | working |
| Player current read | working |
| Coord-anchor module pattern | working |
| Actor coordinates truth | working through `--read-player-actor-coords` |
| Combined actor truth | working through `--read-player-actor-truth` |
| ReaderBridge orientation probe | still empty on the current client |
| `--read-player-actor-orientation` reader mode | working on the live client |
| `--read-player-orientation` reader mode | historical when used offline; live process-attached use now routes to the current actor-orientation truth path |
| `capture-actor-orientation.ps1` | working again for the current session through a live behavior-backed lead |
| Actor yaw / pitch truth | working again on the current live session via canonical pointer-hop forward basis row `+0xD4/+0xD8/+0xDC` |
| Source-chain refresh | still broken after the update |
| Selector-owner trace | still broken after the update |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |

## Fresh actor coordinate truth

Fresh live validation on **April 20, 2026** established:

- canonical coord-read instruction anchor:
  - `rift_x64.exe+0x93560E`
  - `movss xmm0,[rsi+15Ch]`
- traced execution-side coord layout:
  - `X = +0x158`
  - `Y = +0x15C`
  - `Z = +0x160`
- promoted source-object coord surface used by the reader:
  - base register/object = `RDI`
  - coord row = `+0x48/+0x4C/+0x50`

Operational interpretation:

- `--read-player-actor-coords` is now the canonical live reader mode for actor
  coordinate truth
- `--read-player-actor-truth` now returns the current live actor-coordinate and
  actor-orientation truth surfaces in one combined result
- stale coord-trace artifacts are auto-refreshed when the current live native
  trace can reacquire them
- missing `ReaderBridge` player coord blocks no longer block the actor-coordinate
  truth path because the reader can bootstrap from the refreshed trace-backed
  source object

## Fresh actor yaw / pitch truth

Fresh live validation on **April 20, 2026** established:

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
- the canonical live reader mode is now
  `--read-player-actor-orientation`
- process-attached `--read-player-orientation` now routes to that same live
  truth path as a compatibility wrapper
- those historical basis windows read as garbage on this live source and must
  not be promoted over the validated `+0xD4` row
- the repo now carries a behavior-backed lead file at:
  - `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`
- `capture-actor-orientation.ps1` now prefers that lead when present and fails
  closed if the live basis no longer validates

See the fresh validation note:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-20-actor-yaw-pitch-behavior-backed-lead-validation.md`

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
- offline `--read-player-orientation` remains a historical owner-artifact view until the owner/source artifact path is rebuilt
- `player-owner-components.json` and the selected-source artifact chain are still stale until regenerated with a current-process proof

## Canonical scripts on `main`

- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`

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
