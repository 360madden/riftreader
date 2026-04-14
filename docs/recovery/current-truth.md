# Current Truth

_Last updated: April 14, 2026_

This file is the fastest repo-local statement of what is currently true enough to rebuild from.

## Canonical status

| Area | Current status | Confidence |
|---|---|---|
| Low-level reader | functional and reliable enough for active work | High |
| Player current read | working | High |
| Player orientation read | working | High |
| Camera yaw | **direct** from selected-source basis | High |
| Camera pitch | **derived** from entry15 orbit coordinates | Medium-high |
| Camera distance | **derived** from entry15 orbit vector magnitude | Medium-high |
| Authoritative camera controller object | not yet isolated | Low-medium |

## Canonical live paths

### Core reader
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj`
- build: `dotnet build C:\RIFT MODDING\RiftReader\RiftReader.slnx`

### Core rebuild scripts
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1`

## Camera field truth table

| Field | Source | Direct or derived | Notes |
|---|---|---|---|
| Yaw | selected-source basis rows `+0x60/+0x68/+0x78` and duplicate `+0x94/+0x9C/+0xAC` | Direct | current verified live yaw source |
| Pitch | entry15 orbit coords `+0xA8/+0xAC/+0xB0` and duplicate `+0xB4/+0xB8/+0xBC` relative to player coords | Derived | current working pitch path |
| Distance | same entry15 orbit vector magnitude | Derived | current working distance path |

## Mirror-family truth

| Family | Meaning |
|---|---|
| entry5 | mirrored yaw-family basis |
| entry0/12/13/14/15 | mirrored orbit/cache family |
| owner wrapper/backref/state links | current best upward trace path toward a parent/controller object |

## Current authoritative artifacts

| Artifact | Role |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json` | live selector → owner/source trace |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json` | current owner/container/component table |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-graph.json` | owner wrapper/backref/state graph |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-stat-hub-graph.json` | shared-hub graph for sibling/stat relationships |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json` | current orientation/basis capture |

## Active commands to trust first

```powershell
dotnet build C:\RIFT MODDING\RiftReader\RiftReader.slnx
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1 -Json -RefreshSelectorTrace
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1 -Json -RefreshSelectorTrace
C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1 -Json -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1 -Json
C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1 -Json
C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1 -Json -RefreshOwnerGraph -RefreshHubGraph -RefreshOwnerComponents
```

## Paths and ideas to avoid

Do **not** rebuild from these as if they were current truth:
- selected-source `+0xB8..+0x150` camera-window hypothesis
- selected-source `+0x7D0` camera-basis hypothesis
- `entry4 +0x1D0` as a confirmed direct pitch scalar
- historical handoff docs without checking recovery docs first
