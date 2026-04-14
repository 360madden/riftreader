# Camera Orientation Discovery Workflow

> **Current status (April 14, 2026):** live **yaw is verified**, **pitch is usable via orbit derivation**, and a **direct standalone pitch scalar is still unresolved**.
>
> **Do not reuse the old selected-source `+0xB8..+0x150` search window or the selected-source `+0x7D0` basis hypothesis.** Both have been tested live and are no longer the active path.

## Best answer first

The repo now has a working live camera read path:

- **Yaw**: selected-source basis rows
  - `+0x60/+0x68/+0x78`
  - duplicate at `+0x94/+0x9C/+0xAC`
- **Pitch**: derived from the duplicated orbit-coordinate family in **entry 15**
  - `+0xA8/+0xAC/+0xB0`
  - duplicate at `+0xB4/+0xB8/+0xBC`
- **Distance**: derived from the same orbit vector magnitude

Canonical live reader:

```powershell
C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1 -Json
```

## Verified live findings

### 1) Yaw is real and live in the selected-source basis

Current confirmed selected-source basis rows:

- primary: `+0x60/+0x68/+0x78`
- duplicate: `+0x94/+0x9C/+0xAC`

These rows move under live RMB camera yaw stimulus while player coordinates remain stable.

### 2) Pitch is not in the selected-source preferred estimate

Live vertical camera movement changes the scene, but `PreferredEstimate.PitchDegrees` stays flat in the selected-source basis path. Treat that basis as a **yaw source**, not a full camera-angle source.

### 3) Entry 15 carries the strongest live pitch signal

Current best pitch source:

- entry 15 `+0xA8/+0xAC/+0xB0`
- duplicate at `+0xB4/+0xB8/+0xBC`

These coordinates move reversibly under pitch-up / pitch-down stimulus. Derived pitch is computed from:

```text
cameraCoord - playerCoord
pitch = atan2(dy, horizontalDistance)
```

### 4) Mirrored families matter

- **Orbit-family mirrors** exist in `entry0`, `entry12`, `entry13`, `entry14`, `entry15`
- **Yaw mirror** exists in `entry5`
  - `+0x1A0/+0x1A8/+0x1B8`
  - duplicate at `+0x1D4/+0x1DC/+0x1EC`

These families look like **mirrored views / sibling components**, not the final authoritative controller object.

## Important negative results

### Ruled out

- selected-source `+0xB8..+0x150` as the active camera window
- selected-source `+0x7D0/+0x7DC/+0x7E8` basis hypothesis
- `entry4 +0x1D0` as a trustworthy direct pitch scalar

### Meaning

Continuing to scan the old selected-source camera window is low-value. The next high-value target is a **camera/controller object above or beside the current mirrored families**, not another small local scan around the dead window.

## Current workflow

### Step 1: Refresh the live chain

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1 -Json -RefreshSelectorTrace
```

This refreshes the live owner/container/selected-source chain and keeps stale pointers from poisoning later steps.

### Step 2: Read the current live camera state

```powershell
C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1 -Json
```

Use this as the current baseline truth:

- direct yaw
- derived pitch
- derived distance

### Step 3: Run paired candidate verification only when needed

```powershell
C:\RIFT MODDING\RiftReader\scripts\find-live-camera-angle-candidates.ps1 -Json -RefreshOwnerComponents -ScanAllEntries
```

Use this to verify whether a region contains:

- reversible pitch-up / pitch-down deltas
- reversible yaw-left / yaw-right deltas
- scalar-looking angle candidates worth keeping

It is a **verifier**, not the main live reader.

### Step 4: Search upward toward the controller object

```powershell
C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1 -Json -RefreshOwnerGraph -RefreshHubGraph
```

This is the current controller-search entrypoint. It summarizes:

- owner wrapper/backref/state paths
- orbit-family siblings
- entry5 yaw mirror
- shared hub candidates from the stat-hub graph

## Current CE / x64dbg strategy

Do **not** start with exact-value scans in the dead selected-source window.

Start from the verified live anchors instead:

1. Refresh `player-owner-components.json`
2. Watch:
   - selected-source basis rows for yaw
   - entry15 orbit coordinates for pitch / distance
3. Break on **write** or **access** while performing:
   - yaw left/right
   - pitch up/down
   - zoom in/out
4. Trace the common writer / parent object

The highest-value question now is:

> What object owns yaw + pitch + distance together, rather than merely mirroring them?

## What not to do

- Do not treat `entry4 +0x1D0` as verified
- Do not keep searching selected-source `+0xB8..+0x150`
- Do not expect a working pitch scalar in the selected-source preferred estimate
- Do not promote speculative pitch fields into reader code ahead of repeatable live validation

## Current scripts that matter

| Script | Role |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1` | Canonical live yaw + derived pitch reader |
| `C:\RIFT MODDING\RiftReader\scripts\find-live-camera-angle-candidates.ps1` | Paired live verifier for angle candidates |
| `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1` | Refresh live owner/container/source chain |
| `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1` | Walk owner wrappers / backrefs / state links |
| `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1` | Surface shared hubs across sibling components |
| `C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1` | Current parent/controller search entrypoint |
| `C:\RIFT MODDING\RiftReader\scripts\generate-camera-probe.ps1` | Current CE watch/probe generator for live anchors |

## Engineering target from here

The repo is past “is there any yaw?” and into:

1. preserve the current working live read path
2. trace from mirrored orbit / yaw families toward the authoritative camera/controller object
3. replace derived pitch only after a direct source beats it in live repeatability

## Legacy note

Historical docs and scripts that mention selected-source `+0xB8..+0x150` are now background context only. Keep them for evidence, but do not treat them as the active workflow.
