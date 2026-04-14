# Current Truth

_Last updated: April 14, 2026_

## Current status

| Area | Status |
|---|---|
| Low-level reader | reliable enough for active work |
| Player current read | working |
| Player orientation read | working |
| Camera yaw | direct |
| Camera pitch | derived |
| Camera distance | derived |
| Authoritative camera controller | not yet isolated |

## Canonical scripts

- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1`

## Camera truth

| Field | Source | Type |
|---|---|---|
| Yaw | selected-source basis rows `+0x60/+0x68/+0x78` and duplicate `+0x94/+0x9C/+0xAC` | direct |
| Pitch | entry15 orbit coords `+0xA8/+0xAC/+0xB0` and duplicate `+0xB4/+0xB8/+0xBC` relative to player coords | derived |
| Distance | entry15 orbit vector magnitude | derived |

## Tier-1 artifacts

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-stat-hub-graph.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json`

## Do not trust these as current truth

- selected-source `+0xB8..+0x150` camera window
- selected-source `+0x7D0` camera basis idea
- `entry4 +0x1D0` as a confirmed direct pitch scalar
