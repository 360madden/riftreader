# Current Truth

_Last updated: April 23, 2026 (fresh live coord-anchor validation plus actor-facing lead revalidation on the live `rift_x64` session)_

## Current status

| Area | Status |
|---|---|
| Low-level reader | reliable enough for active work |
| ReaderBridge snapshot load | working |
| Player current read | working |
| Coord-anchor module pattern | working |
| Proof coord anchor cache | refreshed again for the current live PID via direct `--read-player-coord-anchor` validation |
| Proof polling watchset | refreshed again and still includes the canonical `coord-trace-coords` region |
| Active movement (`--navigate-waypoints`) | now requires the validated coord-trace anchor only; cached/reacquired anchors are no longer accepted for live movement |
| ReaderBridge orientation probe | still empty on the current client |
| `--read-player-orientation` reader mode | live mode works again when called with `--pid` / `--process-name` through the behavior-backed lead; artifact-only mode remains historical |
| `capture-actor-orientation.ps1` | working again for the current session through a live behavior-backed lead |
| Actor yaw / pitch truth | working on the current live session via source `0x12CAF6F7080` and forward basis row `+0xD4/+0xD8/+0xDC` |
| April 22 source-chain/accessor-family actor-facing result | historical evidence only until separately re-proven on the current session |
| Selector-owner trace | still broken after the update |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |

## Fresh proof coord anchor truth

Fresh live validation on **April 23, 2026** established:

- canonical live coord region: `0x12C9B02B888`
- canonical live coord-trace object base: `0x12C9B02B888`
- current trace-linked source object: `0x12C9B02B840`
- source-object coord offset: `+0x48`
- current proof cache file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`
- current proof watchset file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\proof-polling-watchset.json`

Fresh direct validation on the same live PID showed:

- `--read-player-coord-anchor` still matches the current ReaderBridge coords
- the refreshed proof cache still points at the same `coord-trace-object`
- the refreshed watchset still includes the required `coord-trace-coords` region

Operational interpretation:

- the validated coord-trace anchor remains the **only** proof-grade movement
  source
- `--navigate-waypoints` now fails closed unless that coord-trace anchor is
  available and trusted for the current process
- cached player-current anchors and reacquired player-signature anchors remain
  read-only fallback aids only; they are not accepted as live movement proof
- if the full `resolve-proof-coord-anchor.ps1` refresh path cannot reacquire a
  fresh trace because the CE bootstrap/server is unavailable, use direct
  `--read-player-coord-anchor` validation to confirm the current-process trace
  first before trusting any existing proof cache

## Fresh actor yaw / pitch truth

Fresh live revalidation on **April 23, 2026** kept the current promoted lead:

- canonical live source address: `0x12CAF6F7080`
- canonical forward basis row:
  - `X = +0xD4`
  - `Y = +0xD8`
  - `Z = +0xDC`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

Fresh live checks on the same source:

- `capture-actor-orientation.ps1 -Json -ProcessName rift_x64` resolved the live
  source again through the behavior-backed lead and recomputed yaw/pitch from
  `Basis@0xD4.Forward`
- `dotnet ... -- --process-name rift_x64 --read-player-orientation --json`
  resolved the same live source and the same `Basis@0xD4.Forward`
- the current live yaw/pitch remained derivable from that basis without falling
  back to owner-component artifacts

Operational interpretation:

- the repo now carries a behavior-backed lead file at:
  - `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`
- the current live actor-facing truth is the validated `0xD4` forward row on
  `0x12CAF6F7080`, not the older April 22 source-chain `+0x60/+0x94` result
- the current lead is facing-only truth; the same capture still showed
  `Coord48` / `Coord88` on this source do **not** match the current player
  coords, so this lead is not a movement coord source
- the earlier April 22 source-chain/accessor-family result at
  `0x24F595F8D10 @ +0x60/+0x94` remains useful historical evidence, but it is
  no longer the living authority for the current live session
- `capture-actor-orientation.ps1` and `--read-player-orientation` now agree on
  the same live lead again for the current PID

See the current live lead / proof artifacts:

- `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json`

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

- the April 22 source-chain/accessor-family actor-facing promotion docs are now
  historical-only; do not treat them as the current live authority unless they
  are separately re-proven again
- `trace-player-selector-owner.ps1` can remain `armed` without a live hit
- `player-selector-owner-trace.json` is stale until regenerated with a current-process proof
- `player-owner-components.json` is stale until regenerated with a current-process proof
- fresh coord-trace reacquisition still depends on a working CE/bootstrap path
  when the current trace artifact no longer validates
- `--read-player-orientation` without `--pid` / `--process-name` remains the historical artifact-only path until the owner/source artifact path is rebuilt

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
