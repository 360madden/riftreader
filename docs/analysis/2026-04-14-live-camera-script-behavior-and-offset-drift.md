---
state: historical
as_of: 2026-04-14
---

# Live Camera Script Behavior and Offset Drift (2026-04-14)

## Scope

This report freezes the first post-update live camera check on
`codex/camera-yaw-pitch`.

It documents:

- what the legacy camera scripts actually did to the live client
- whether the pre-update camera object addresses still read successfully
- what the new safe probe found during direct RMB/raw-read testing

This is a drift report, not a repaired camera workflow.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `historical` |
| As of | `2026-04-14` |
| Report date | `2026-04-14` |
| Game update/build date | `2026-04-14` |
| Branch | `codex/camera-yaw-pitch` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Input mode | `direct mouse/RMB stimulus + direct raw reads` |
| Validation status | `historical offsets stale; safe replacement not yet recovered` |

## Commands run

```powershell
& 'C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1' -Json
& 'C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1' -Json
& 'C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1' -Json -MaxHits 4 -RegionLength 384 -MousePixels 80
& 'C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1' -Json -MaxHits 4 -RegionLength 384 -MousePixels 40
```

## Artifacts checked

- `C:\Users\mrkoo\AppData\Local\Temp\rift-legacy-baseline.png`
- `C:\Users\mrkoo\AppData\Local\Temp\rift-after-read-live-camera.png`
- `C:\Users\mrkoo\AppData\Local\Temp\rift-after-legacy-camera-angle-script.png`
- `C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`

## Historical camera model that drifted

These were the last-known camera offsets before the April 14, 2026 update:

| Signal | Historical source |
|---|---|
| camera yaw | selected-source basis `+0x60/+0x68/+0x78`, duplicate `+0x94/+0x9C/+0xAC` |
| camera pitch | `entry15` orbit coords `+0xA8/+0xAC/+0xB0`, duplicate `+0xB4/+0xB8/+0xBC` |
| camera distance | derived from the same `entry15` orbit vector |

The last-known pre-update object addresses for that model were:

- selected-source base: `0x1FDA0D13170`
- `entry15` base: `0x1FD9FA6F190`

Direct raw reads against those addresses failed on the updated client with
`ReadProcessMemory ... Win32: 299`.

## Legacy script behavior

| Script | Result | Notes |
|---|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1` | partial / unreliable | did not obviously spam menus, but it hung on the stale chain |
| `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1` | unsafe | fell into legacy refresh/reload flow and opened extra UI windows |

Observed UI behavior:

- `read-live-camera-yaw-pitch.ps1`
  - screenshot delta vs baseline: about `2.367%`
  - after image remained visually close to baseline
- `find-live-camera-angle-candidates.ps1`
  - screenshot delta vs baseline: about `37.2673%`
  - after image showed:
    - `Quest Log`
    - `Looking For Group`
    windows opened

The legacy angle-candidate path also fell into:

- `refresh-readerbridge-export.ps1`
- `/reloadui`
- AHK command fallback

So it is now classified as UI-intrusive and unsafe for unattended live use.

## Safe probe findings

The new preferred live probe on this branch is:

- `C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1`

Its design intent is narrower:

- direct raw memory reads only
- direct RMB camera motion only
- no `/reloadui`
- no legacy refresh chain
- no CE debugger
- now supports explicit `-BaseAddresses` so future runs can stay on a smaller
  curated candidate set instead of every coord-hit-derived base

### Probe run 1

Command:

```powershell
& 'C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1' -Json -MaxHits 4 -RegionLength 384 -MousePixels 80
```

Result summary:

- one weak yaw candidate at base `0x2BCC35D9B98`, offset `0x020`
- top pitch-like offsets appeared at:
  - base `0x2BC8A2AF9D8`, offset `0x078`
  - base `0x2BC8A2AF998`, offset `0x0B8`
- those pitch-like candidates also carried absurd delta magnitudes, so they
  were not trustworthy as-is

### Probe run 2

Command:

```powershell
& 'C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1' -Json -MaxHits 4 -RegionLength 384 -MousePixels 40
```

Result summary:

- no repeatable yaw candidates
- pitch-like candidates moved to unrelated garbage offsets:
  - `0x008`
  - `0x048`

Interpretation:

- the first run's `0x078` / `0x0B8` hints did not repeat
- no stable post-update camera yaw/pitch replacement was recovered in this pass

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| pre-update selected-source camera base | stale | exact historical address no longer readable |
| pre-update `entry15` camera base | stale | exact historical address no longer readable |
| legacy angle-candidate workflow | unsafe | invokes refresh/reload chain and pops UI windows |
| safe probe candidate quality | weak | first-pass hints did not repeat cleanly |

## Branch / workflow authority

Camera logic is currently split:

- branch `feature/camera-orientation-discovery`
  - still holds the last-known historical camera workflow
- branch `codex/camera-yaw-pitch`
  - now holds the safe drift-probe path for post-update checks

For post-update live work, prefer the `codex/camera-yaw-pitch` safe probe until
the feature-branch logic is either repaired or retired.

## Input mode and safety notes

This pass used direct mouse/RMB stimulus and direct raw memory reads.

It intentionally did **not** use:

- CE debugger
- breakpoint traces
- selector-owner trace scripts
- chat command injection for the safe probe

One legacy verification run did prove that the old angle-candidate workflow can
still fall into `/reloadui` and open extra UI windows.

## Immediate next step

Keep the old camera offsets marked historical, keep the safe probe as the
default live path, and resume with `-BaseAddresses` against a deliberately
curated small base set instead of every coord-hit-derived base.
