# Rift Input Control Workflow

## Purpose

This file defines the **canonical** RIFT input/control stack for this repo so future runs do not drift between overlapping helpers.

Use the smallest reliable layer that matches the task:

1. **real gameplay key input**
2. **command refresh / `/reloadui`**
3. **camera discovery harness**
4. **manual fallback**
5. **experimental probes only when the preferred path has already failed**

## Recommended action order

| Priority | Action | Preferred entrypoint | Why |
|---|---|---|---|
| 1 | Alt+S look-behind toggle | `C:\RIFT MODDING\RiftReader\Run-CameraDiscoveryStable.ps1` or `C:\RIFT MODDING\RiftReader\scripts\test-camera-alts-stimulus-safe.ps1` | Large, discrete camera-orientation change; easiest to diff and verify visually. |
| 2 | Alt+Z alternate zoom toggle | `C:\RIFT MODDING\RiftReader\Run-AltZRetry.ps1` or `C:\RIFT MODDING\RiftReader\scripts\test-camera-altz-stimulus-safe.ps1` | Strong zoom/distance cross-check; helps separate distance fields from orientation fields. |
| 3 | RMB hold + mouse move | `C:\RIFT MODDING\RiftReader\scripts\test-rmb-camera.ps1` | Closest to real camera yaw/pitch behavior when toggles are not enough. |
| 4 | Mouse wheel zoom | `C:\RIFT MODDING\RiftReader\scripts\zoom-camera.ps1` or `C:\RIFT MODDING\RiftReader\scripts\test-camera-stimulus.ps1` | Clean scalar-style zoom stimulus. |
| 5 | Movement nudges (`W/A/S/D`) | `C:\RIFT MODDING\RiftReader\scripts\send-rift-key.ps1` | Best for reacquiring anchors or forcing small movement deltas, not the first camera-discovery stimulus. |

## Canonical entrypoints

| Role | Script | Guidance |
|---|---|---|
| Preferred gameplay key input | `C:\RIFT MODDING\RiftReader\scripts\send-rift-key.ps1` | Default for confirmed gameplay input. Uses `SendInput`; requires foreground focus. |
| Compatibility/background-style key input | `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1` | Keep for existing discovery harnesses and Alt-combo workflows, but do not treat it as the strongest gameplay-input primitive. |
| Preferred ReaderBridge refresh | `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1` | Default `/reloadui` path. Native helper first, AutoHotkey fallback second. |
| Preferred camera discovery runner | `C:\RIFT MODDING\RiftReader\Run-CameraDiscoveryStable.ps1` | Default root-level scripted camera harness. |
| Preferred Alt-Z retry path | `C:\RIFT MODDING\RiftReader\Run-AltZRetry.ps1` | Use when the first Alt-Z pass is weak or partially failed. |
| Preferred manual fallback | `C:\RIFT MODDING\RiftReader\Run-ManualAltSHoldCaptureFixed.ps1` | Use when a human-held Alt-S capture is needed. |

## Script tiers

### Preferred

- `C:\RIFT MODDING\RiftReader\scripts\send-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`
- `C:\RIFT MODDING\RiftReader\Run-CameraDiscoveryStable.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-camera-alts-stimulus-safe.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-camera-altz-stimulus-safe.ps1`
- `C:\RIFT MODDING\RiftReader\Run-AltZRetry.ps1`
- `C:\RIFT MODDING\RiftReader\Run-ManualAltSHoldCaptureFixed.ps1`

### Situational / okay

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-command.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-command-ahk.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-rmb-camera.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\zoom-camera.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-camera-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`

### Experimental / probe only

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-thread-command.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-postmessage-mouse.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-postmessage-mouse2.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-postmessage-rmb.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\quick-camera-keyboard-test.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\simple-camera-memory-test.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-mcp-camera-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\auto-discover-camera-yaw.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\find-camera-by-yaw-scan.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\quick-camera-alts-test.ps1`

## Archived runners

Superseded root-level camera-runner variants now live under:

- `C:\RIFT MODDING\RiftReader\archive\superseded-runners\`

Those files are kept for historical reference only. They are not the supported entrypoints and may not remain runnable from their archived location.
