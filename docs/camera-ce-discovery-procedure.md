# Camera Yaw/Pitch Discovery via Cheat Engine

> **Updated April 14, 2026:** the old selected-source `+0xB8..+0x150` exact-value scan workflow is obsolete. Use the verified live anchors below.

## Best answer first

Cheat Engine is now most useful for **targeted watch / break-on-write / break-on-access tracing**, not for blind scanning inside the dead selected-source camera window.

Current verified live anchors:

| Anchor | What it gives | Offsets |
|---|---|---|
| selected-source basis | live yaw | `+0x60/+0x68/+0x78`, duplicate `+0x94/+0x9C/+0xAC` |
| entry15 orbit coords | derived pitch + derived distance | `+0xA8/+0xAC/+0xB0`, duplicate `+0xB4/+0xB8/+0xBC` |
| entry5 mirror | mirrored yaw-family basis | `+0x1A0/+0x1A8/+0x1B8`, duplicate `+0x1D4/+0x1DC/+0x1EC` |
| orbit siblings | mirrored/cached orbit family | `entry0/12/13/14/15` |

## Before opening CE

Refresh the live chain first:

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1 -Json -RefreshSelectorTrace
```

Optional current-state summary:

```powershell
C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1 -Json
```

Optional CE watch/probe document:

```powershell
C:\RIFT MODDING\RiftReader\scripts\generate-camera-probe.ps1 -Json
```

## Recommended CE workflow

### 1) Watch the verified live anchors

Add the current session addresses to the CE table:

- selected-source basis rows
- entry15 orbit primary + duplicate coords
- entry5 yaw mirror if present

These are the addresses worth watching live.

### 2) Use stimulus that cleanly separates behaviors

- **Yaw**: RMB hold + horizontal mouse move
- **Pitch**: RMB hold + vertical mouse move
- **Zoom**: mouse wheel

Do not use the old selected-source `+0xB8..+0x150` window as the first search area.

### 3) Break on write / access

Best current CE move:

- break on **write** for entry15 orbit coords during pitch / zoom
- break on **write** for selected-source basis rows during yaw
- if write is too noisy, break on **access** and follow the common writer / caller

The target is no longer “find a random angle float.” The target is:

> find the object or code path that updates yaw + pitch + distance together.

### 4) Climb outward using repo-native graph helpers

Use these between CE passes:

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1 -Json -RefreshSelectorTrace
C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1 -Json -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1 -Json -RefreshOwnerGraph -RefreshHubGraph
```

These scripts surface:

- owner wrapper / backref / state links
- orbit-family sibling relationships
- shared hub candidates across entries `12/13/14/15`

## What to look for

### High-value signs of a real controller object

- responds to **yaw**, **pitch**, and **zoom**
- is referenced by multiple mirrored sibling components
- exposes stable parent/backref structure
- survives repeated paired live tests better than the current derived-pitch path

### Low-value signs

- single noisy scalar in one sibling entry
- values that only move on one trial and vanish on repeat
- anything in the dead selected-source `+0xB8..+0x150` range

## What not to do

- Do not begin with an exact-value float scan in selected-source `+0xB8..+0x150`
- Do not treat `entry4 +0x1D0` as a proven pitch scalar
- Do not assume the mirrored orbit family is the final authoritative controller

## Practical outcome expected from CE now

The next strong win is not just “another float that moved.” It is one of:

1. a parent/controller object above the mirrored orbit family
2. a direct pitch/distance source on the same authoritative object
3. a common write path that explains the selected-source yaw basis and entry15 orbit coords together
