# Glyph launcher read-only inspection — future automation notes

## Verdict

Glyph is running, but it is currently a hidden/minimized launcher surface. It should be treated as a process/tree signal, not as a ready-to-click visible UI.

| Field | Value |
|---|---|
| Generated UTC | `2026-05-20T17:37:23.611408+00:00` |
| Launcher process | `GlyphClientApp.exe` PID `31812` |
| Launcher path | `C:\Program Files (x86)\Glyph\GlyphClientApp.exe` |
| Launcher command | `GlyphClientApp.exe -hidden` |
| Launcher main HWND | `0x27017C` title `Glyph`, class `Qt5QWindowIcon` |
| Launcher window state | visible flag true but minimized/offscreen at `-32000,-32000`, client `0x0` |
| Hidden form HWND | `0x10A86`, title `Form`, class `Qt5QWindowIcon`, client `400x425`, not visible |
| Tray message HWND | `0x10A8E`, title `QTrayIconMessageWindow`, class `QTrayIconMessageWindowClass`, not visible |
| UIA result | root pane only; no button/control tree captured while hidden/minimized |
| Glyph library version | `stable-249-1-a-335557` |
| RIFT live manifest version | `STABLE-1-1149-a-1256380` |
| Current RIFT child process | `rift_x64.exe` PID `80072`, parent PID `31812` |

## Read-only artifacts

| Artifact | Path |
|---|---|
| Redacted summary JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-launcher-inspection-summary.json` |
| Raw window enum JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-launcher-window-enum.json` |
| UI Automation JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-launcher-uia.json` |
| Process tree JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-process-tree.json` |
| Notification log tail | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-notification-log-tail.txt` |
| Glyph library manifest excerpt | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-library-manifest-head-tail.txt` |
| RIFT live manifest | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\rift-live-manifest64.txt` |

## Future automation implications

1. Detect launcher presence by `GlyphClientApp.exe`, not by visible window geometry alone.
2. Use `rift_x64.exe` parent PID to associate the running game with Glyph; current parent is PID `31812`.
3. Do not reuse or persist RIFT command-line auth/session arguments; tracked docs must keep them redacted.
4. Hidden/minimized Glyph has no reliable button-level UIA tree; future button automation needs an explicit restore/show step plus screenshot classification.
5. `Notification.log` is useful historical context but not reliable current launch proof for the 2026-05-20 RIFT session.
6. Future launcher-button automation must be exact PID/HWND gated, screenshot verified, explicit-approval gated, and limited to one action per approval.
7. Prefer observing launcher/game process state over pressing launcher buttons for crash/relogin recovery until a robust visible-state classifier exists.
8. Treat launcher UI and game UI as separate target surfaces with separate approval tokens and stale-target invalidation.

## Safety

No launcher buttons were pressed. No focus, click, key input, launch attempt, process termination, provider write, Git mutation, CE, or x64dbg attach was performed.

## Continuation update — 2026-05-20 13:49 EDT — tracked helper + workflow status integration

| Field | Value |
|---|---|
| Helper | `scripts\riftreader-launcher-inspection.cmd --json` |
| Core module | `scripts\rift_live_test\launcher_inspection.py` |
| Wrapper | `scripts\launcher_inspection.py` |
| Tests | `scripts\test_launcher_inspection.py` |
| Workflow status key | `launcher-inspection` |
| Latest helper run | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-174905-389594` |
| Latest summary JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-174905-389594\launcher-inspection-summary.json` |
| Launcher state | `launcher-and-game-present` |
| Relogin state | `observe-current-game-child` |
| Launcher window state | `minimized-or-offscreen` |
| Button automation policy | `blocked-hidden-or-minimized` |

### Defensive coding choices

- Command lines are redacted before artifacts are written; raw RIFT/Glyph command lines are not stored by the helper.
- The helper records process-tree relation, launcher window geometry, RIFT HWND geometry, manifest versions, and Notification.log metadata without treating logs as current launch proof.
- Launcher button automation remains blocked while Glyph is hidden/minimized or has no verified visible client area.
- Workflow status reads the latest helper artifact only; it does not implicitly press buttons, restore windows, or launch the game.

### Validation

- `python -m py_compile scripts\rift_live_test\launcher_inspection.py scripts\launcher_inspection.py tools\riftreader_workflow\status_packet.py` -> passed.
- `python -m unittest scripts.test_launcher_inspection scripts.test_opencode_status_packet` -> 18 tests OK.
- `scripts\riftreader-launcher-inspection.cmd --json` -> passed; no focus/click/key/launch/button action sent.

### Latest workflow-status artifact

- Compact SITREP with launcher section: `C:\RIFT MODDING\RiftReader\.riftreader-local\workflow-status\20260520-175126Z\compact-sitrep.json`.
- Expected status remains `blocked` because RIFT is at character selection and movement/world-entry remains approval-gated.
