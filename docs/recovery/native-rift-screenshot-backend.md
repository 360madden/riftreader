# Native RIFT Screenshot Backend

_Last updated: May 14, 2026 01:49 EDT / May 14, 2026 05:49 UTC._

## Verdict

The local RIFT game installation is verified to use the in-game
**Take Screenshot** binding **`NUM PAD *` / `VK_MULTIPLY` / `0x6A`**, and the
binding works. A live trial against the current `rift_x64` target created a new
native RIFT screenshot immediately.

This is the canonical local screenshot key for RiftReader workflows on this
machine. Do **not** substitute `Ctrl+P`, `PrtSc`, Windows Snipping Tool
shortcuts, or any stale/default keybinding assumption.

| Rule | Status |
|---|---|
| `NUM PAD *` / `VK_MULTIPLY` | **Allowed and live-proven** |
| `Ctrl+P` / `Control+P` | **Forbidden**; the keybind was removed and must never be retried for screenshots |
| `PrtSc` / Print Screen | **Forbidden for automation**; Windows 11 Snipping Tool intercepts it on this machine |
| `Win+Shift+S` / Snipping Tool | Manual/operator fallback only; not exact-HWND automation |
| `Take Screenshot Without UI` | Not bound in RIFT; do not assume it exists |

## Keybind source of truth

Do not look for the screenshot keybind in `rift.cfg`; that file holds client
settings, not the exported keybinding table. The current keybind proof is the
exported RIFT keybinding file:

`C:\Program Files (x86)\Glyph\Games\RIFT\Live\mykeybindings`

| Field | Value |
|---|---|
| Exported file timestamp | May 14, 2026 01:39:32 EDT |
| Action | `Take Screenshot` |
| Action id | `20010` |
| Default record | `02 2C 07 AA 9C 01` = `PrintScreen` / `VK_SNAPSHOT` / `0x2C` |
| Current exported record | `02 6A 07 AA 9C 01` = `NUM PAD *` / `VK_MULTIPLY` / `0x6A` |

## Latest live proof

| Field | Value |
|---|---|
| Target | `rift_x64` PID `2928`, HWND `0xC0994` |
| Time | May 14, 2026 01:49 EDT / May 14, 2026 05:49 UTC |
| Key sent | `numpad_multiply`, virtual key `0x6A` |
| Input method | `window-message` |
| Fallback used | No |
| Native screenshot file | `C:\Users\mrkoo\OneDrive\Documents\RIFT\Screenshots\2026-05-14_014934.jpg` |
| Repo artifact copy | `C:\RIFT MODDING\RiftReader\scripts\captures\native-screenshot-keybind-20260514-014933\rift-native-numpad-multiply-screenshot-20260514-054934.jpg` |
| Result JSON | `C:\RIFT MODDING\RiftReader\scripts\captures\native-screenshot-keybind-20260514-014933\native-screenshot-result.json` |
| Result Markdown | `C:\RIFT MODDING\RiftReader\scripts\captures\native-screenshot-keybind-20260514-014933\native-screenshot-result.md` |
| MCP frame-change follow-up | `changed=true`, `changePercent=9.5069`, screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260514-014942-533.png` |

Safety note: this proof sent only the approved screenshot key. It did not send
movement, `/reloadui`, Cheat Engine, x64dbg, or provider writes.

## Previous live proof

| Field | Value |
|---|---|
| Target | `rift_x64` PID `49504`, HWND `0x5121A` |
| Time | May 8, 2026 20:08 EDT / May 9, 2026 00:08 UTC |
| Key sent | `numpad_multiply`, virtual key `0x6A` |
| Input method | `window-message` |
| Fallback used | No |
| Native screenshot file | `C:\Users\mrkoo\OneDrive\Documents\RIFT\Screenshots\2026-05-08_200805.jpg` |
| Repo artifact copy | `C:\RIFT MODDING\RiftReader\scripts\captures\native-screenshot-numpad-star-live-20260508-200805\rift-native-numpad-multiply-screenshot-20260509-000805.jpg` |
| Result JSON | `C:\RIFT MODDING\RiftReader\scripts\captures\native-screenshot-numpad-star-live-20260508-200805\native-screenshot-result.json` |
| MCP frame-change follow-up | `changed=true`, `changePercent=2.9424`, screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-200814-887.png` |

## Canonical command

Use this command shape for direct native screenshot trials:

```powershell
python .\scripts\rift_native_screenshot.py `
  --pid <exact-rift-pid> `
  --hwnd <exact-rift-hwnd> `
  --key-chord numpad_multiply `
  --output-root <run-artifact-dir> `
  --timeout-milliseconds 10000 `
  --window-message-timeout-milliseconds 1500 `
  --json
```

The helper must fail closed before input if `--key-chord ctrl+p` or
`--key-chord control+p` is supplied.

## What the helper is allowed to do

1. Verify the exact HWND exists and belongs to the requested PID.
2. Bring the exact RIFT window foreground.
3. Snapshot `C:\Users\mrkoo\OneDrive\Documents\RIFT\Screenshots` before input.
4. Send only `NUM PAD *` (`VK_MULTIPLY`, `0x6A`) for the native screenshot.
5. Poll for a new RIFT-created screenshot file.
6. Copy the captured file into the run artifact directory.
7. Emit JSON with target, key, input method, screenshot path, artifact path, and timing.

## What the helper must never do

- Do not send `Ctrl+P` / `Control+P` for screenshots.
- Do not send `PrtSc` / Print Screen.
- Do not use Windows Snipping Tool as an unattended exact-window backend.
- Do not treat a GDI/MCP/WGC capture failure as permission to try old screenshot keybinds.
- Do not silently rebind or assume `Take Screenshot Without UI`; it is not bound.

## Workflow integration

The turn-key profiler can request native RIFT screenshots with:

```powershell
python .\scripts\profile_turn_keys.py `
  --pid <exact-rift-pid> `
  --hwnd <exact-rift-hwnd> `
  --capture-screenshots `
  --screenshot-backend native-rift
```

This is visual evidence only. Movement truth remains governed by the existing
no-CE proof-anchor/readback gates, exact PID/HWND checks, and post-readback
coordinate validation.

## Failure troubleshooting

If `NUM PAD *` times out without creating a file:

| Check | Why |
|---|---|
| Reconfirm RIFT keybind UI shows `Take Screenshot = NUM PAD *` | Game binding is the source of truth |
| Confirm exact PID/HWND and foreground focus | Prevents wrong-window input |
| Check NumLock / keyboard translation behavior | Numpad keys can be layout-sensitive |
| Try the helper fallback paths for virtual-key or scan-code `VK_MULTIPLY` only | Still uses the same allowed binding |
| Inspect screenshot folder before/after timestamps | Distinguishes input delivery from file-polling issues |

Do **not** retry `Ctrl+P`, `PrtSc`, or Snipping Tool automation as a workaround.
