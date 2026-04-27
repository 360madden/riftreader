# Focused PostMessage Refresh Retest

Date: April 15, 2026
Branch: `codex/actor-yaw-pitch`

## Goal

Fix the root refresh failure at the earliest layer:

- reliably acquire the Rift window by process and `MainWindowHandle`
- focus Rift first
- verify Rift is foreground
- post `/reloadui` through the native PowerShell helper
- prove the refresh lane works **without** the AutoHotkey backup

## Root cause being fixed

The earlier failure that surfaced as:

- `AutoHotkey helper exited with code 2`

was a **window-acquisition failure in the legacy AutoHotkey fallback lane**.

The fallback script was attempting:

- `WinGetList("ahk_exe rift_x64.exe")`

and exited before delivery when it could not resolve a target top-level Rift
window.

That meant the correct first fix was not "improve the fallback keystroke
pattern." It was:

- stop depending on the weak window-enumeration fallback for the primary refresh
  path
- reuse the stronger process/HWND/focus model from the live actor-yaw key path

## Code change

Updated:

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-command.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`

The native command helper now supports the same focus-enforced model used by
the working gameplay-key path:

1. resolve Rift by process name
2. require `MainWindowHandle != 0`
3. focus Rift with thread-input assist
4. verify Rift actually became foreground
5. resolve the effective target handle
6. send `/reloadui` via native `PostMessage`
7. verify success by watching `ReaderBridgeExport.lua`

The refresh script now uses that focused native path first instead of the older
no-focus command path.

## Retest command

```powershell
powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1" -Json -NoAhkFallback
```

## Retest result

The retest succeeded **without using the AutoHotkey backup**.

Observed native helper output:

- target process found: `rift_x64 [30888]`
- target window: `0x132068 'RIFT'`
- strategy: `Focused PostMessage delivery`
- foreground verified as Rift:
  - `0x203E4 (rift_x64 [30888])`
- input target:
  - `0x203E4`
- command:
  - `/reloadui`
- strategy used:
  - `enter-then-type`
- verification file advanced successfully

Observed verification timestamp:

- baseline UTC:
  - `2026-04-15T05:29:29.7861675Z`
- updated UTC:
  - `2026-04-16T00:01:26.2506267Z`

Then `--readerbridge-snapshot` loaded successfully and returned a fresh export.

## Conclusion

The root refresh problem is now fixed at the correct layer:

- native window/process binding
- focus verification
- native focused `PostMessage` command delivery

The latest refresh retest proves that:

- the primary refresh path works without the AutoHotkey backup
- the previous AHK failure was not needed to understand whether native
  `/reloadui` could work
- scripts that depend on `refresh-readerbridge-export.ps1` now inherit the
  stronger method automatically

## Operational implication

The AutoHotkey path should now be treated as:

- a legacy backup
- not the main explanation for refresh reliability
- not the default truth source for future live refresh debugging