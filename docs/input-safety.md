# Input Safety

Use this page to classify repo scripts by **input risk** before running them
against a live Rift client.

Default rule:

> Treat a script as **read-only only if it is explicitly classified that way**.

This page exists because post-update triage surfaced two separate concerns:

1. some workflows are safe to repeat at high frequency
2. some helper paths are still **UI-intrusive** because they rely on chat,
   `Enter`, `/reloadui`, or focus-sensitive mouse behavior

## Primary classes

| Class | Meaning |
|---|---|
| Read-only | No game input, no focus changes, no chat/reload behavior |
| Direct key input | Sends gameplay-style key input to the Rift window |
| Direct mouse/camera input | Sends RMB / mouse drag / wheel or camera-look style input |
| Chat/reload UI-intrusive | Uses chat command injection, `/reloadui`, or other UI-sensitive helpers |
| Hybrid | Mostly readback/analysis, but may invoke one of the input classes depending on flags or recovery path |

## Main inventory

| Script | Primary class | Secondary behavior | Branch/worktree | Notes |
|---|---|---|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\watch-readerbridge-export.ps1` | Read-only | none | `main` | Watches saved-variable output only |
| `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1` | Read-only | none | `main` | Capture provenance / freshness only |
| `C:\RIFT MODDING\RiftReader\scripts\export-discovery-watchset.ps1` | Read-only | none | `main` | Derived watchset output only |
| `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1` | Direct key input | none | `main` | Gameplay-style key helper |
| `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1` | Direct key input | readback before/after | `main` | Measures actor-orientation deltas around a key stimulus |
| `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1` | Direct key input | readback profiling | `main` | Repeats multiple key stimuli |
| `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1` | Chat/reload UI-intrusive | may fallback to AHK | `main` | Uses `/reloadui`; not safe for unattended probing |
| `C:\RIFT MODDING\RiftReader\scripts\post-rift-command.ps1` | Chat/reload UI-intrusive | none | `main` | Command/chat injection helper |
| `C:\RIFT MODDING\RiftReader\scripts\post-rift-thread-command.ps1` | Chat/reload UI-intrusive | none | `main` | Thread-message variant of command injection |
| `C:\RIFT MODDING\RiftReader\scripts\send-rift-command.ps1` | Chat/reload UI-intrusive | focus-sensitive | `main` | Uses `Enter` + typed command flow |
| `C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1` | Hybrid | may refresh export / reacquire | `main` | Mostly reader-driven, but can invoke helper flows |
| `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1` | Hybrid | may rely on live trace/input path | `main` | Analysis-first, but not purely passive |
| `C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1` | Hybrid | may refresh selector trace | `main` | Downstream of trace workflow |
| `C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1` | Direct mouse/camera input | direct raw readback only | `codex/camera-yaw-pitch` | Preferred live camera drift probe; avoids reload/chat helpers |
| `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1` | Direct mouse/camera input | can combine RMB + readback | `feature/camera-orientation-discovery` | Camera stimulus harness |
| `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-rmb-camera.ps1` | Direct mouse/camera input | manual stepping | `feature/camera-orientation-discovery` | Very focus/UI sensitive |
| `C:\RIFT MODDING\RiftReader_camera_feature\scripts\zoom-camera.ps1` | Direct mouse/camera input | wheel input | `feature/camera-orientation-discovery` | Zoom-only camera input |
| `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1` | Chat/reload UI-intrusive | falls into legacy refresh/reload chain | `feature/camera-orientation-discovery` | Confirmed to open Quest Log / Looking For Group during live test |

## High-risk helpers

These should be treated as **not safe for unattended runs**:

- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-command.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-thread-command.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\send-rift-command.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-rmb-camera.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`

Why:

- chat state may not be what you expect
- `/reloadui` is deliberately disruptive
- focus-sensitive mouse/RMB paths can open menus or hit UI unexpectedly
- the legacy camera angle-candidate script was observed to open Quest Log and
  Looking For Group during a live verification pass

## Branch scope note

The current live camera workflow is **not** on `main`.

Runnable camera-input helpers currently live on:

- branch: `feature/camera-orientation-discovery`
- inspected worktree: `C:\RIFT MODDING\RiftReader_camera_feature`

Do not assume a script path under `C:\RIFT MODDING\RiftReader\scripts\` exists
on `main` just because an older camera note references it.

## Cross-links

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\README.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\_template.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`
