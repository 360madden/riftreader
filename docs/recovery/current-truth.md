# Current Truth

_Last updated: April 22, 2026 (fresh CE-assisted source-chain actor-facing revalidation on the live `rift_x64` session)_

## Current status

| Area | Status |
|---|---|
| Low-level reader | reliable enough for active work |
| ReaderBridge snapshot load | working |
| Player current read | working |
| Coord-anchor module pattern | working |
| ReaderBridge orientation probe | still empty on the current client |
| `--read-player-orientation` reader mode | live mode works again when called with `--pid` / `--process-name` through the behavior-backed lead; artifact-only mode remains historical |
| `capture-actor-orientation.ps1` | working again for the current session through a live behavior-backed lead |
| Actor yaw / pitch truth | working again on the current live session via source `0x24F595F8D10` and forward basis row `+0x60/+0x64/+0x68` (duplicate `+0x94/+0x98/+0x9C`) |
| Source-chain refresh | working again through the live coord trace cluster and source-accessor-family rebuild |
| Selector-owner trace | still broken after the update |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |

## Fresh actor yaw / pitch truth

Fresh live validation on **April 22, 2026** established:

- canonical live source address: `0x24F595F8D10`
- canonical forward basis row:
  - `X = +0x60`
  - `Y = +0x64`
  - `Z = +0x68`
- duplicate truth-bearing forward basis row:
  - `X = +0x94`
  - `Y = +0x98`
  - `Z = +0x9C`
- canonical up/right rows:
  - primary up = `+0x6C/+0x70/+0x74`
  - primary right = `+0x78/+0x7C/+0x80`
  - duplicate up = `+0xA0/+0xA4/+0xA8`
  - duplicate right = `+0xAC/+0xB0/+0xB4`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

Fresh live key-stimulus proof on the same source:

- primary `+0x60` row:
  - `D` peak yaw deltas: `-146.6686`, `-143.0910`
  - `A` peak yaw deltas: `+143.5635`, `+147.9166`
  - reversible cycles: `2 / 2`
  - coord drift during validation: `0.0`
- duplicate `+0x94` row:
  - `D` peak yaw deltas: `-146.6681`, `-143.0903`
  - `A` peak yaw deltas: `+143.5629`, `+147.9163`
  - reversible cycles: `2 / 2`
  - coord drift during validation: `0.0`

Operational interpretation:

- the current truth-bearing actor-facing basis **is** the refreshed
  source-accessor-family `+0x60/+0x94` layout on `0x24F595F8D10`
- the same current-session validation showed `+0xD4` and `+0x140` on this
  source stayed flat and must not be promoted over the validated `+0x60/+0x94`
  rows
- the earlier all-zero source-chain validation artifact was invalid because
  `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-yaw-candidates.ps1`
  keyed baseline/sample snapshots only by source address; the April 22 fix now
  keys them by `source+offset`, which restored correct same-source multi-offset
  validation
- the repo now carries a behavior-backed lead file at:
  - `C:\RIFT MODDING\RiftReader_facing\scripts\actor-facing-behavior-backed-lead.json`
- `capture-actor-orientation.ps1` now prefers that lead when present and fails
  closed if the live basis no longer validates
- `dotnet run --project ... -- --process-name rift_x64 --read-player-orientation`
  now uses that same current-session lead when a live process selector is
  provided; the no-process artifact-only mode remains historical

See the fresh validation note:

- `C:\RIFT MODDING\RiftReader_facing\docs\analysis\2026-04-22-actor-facing-source-chain-behavior-backed-lead.md`

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

- `trace-player-selector-owner.ps1` can remain `armed` without a live hit
- `player-selector-owner-trace.json` is stale until regenerated with a current-process proof
- `player-owner-components.json` is stale until regenerated with a current-process proof
- `--read-player-orientation` without `--pid` / `--process-name` remains the historical artifact-only path until the owner/source artifact path is rebuilt

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
