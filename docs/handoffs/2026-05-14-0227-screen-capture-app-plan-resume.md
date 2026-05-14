# Screen capture app plan resume handoff

_Last updated: 2026-05-14 02:27 local / 06:27 UTC._

## Verdict

The RIFT full-window capture lane is currently in **planning + documented-proof
state**, not implementation-complete state. The durable resume anchor is:

`docs/recovery/rift-window-capture-app-plan.md`

Next coding should start with the smallest safe implementation slice: exact
`--hwnd` targeting, process-start validation, output-root bundle,
`manifest.json`, `logs/run.jsonl`, and preserved wrapper compatibility.

## Current repo state at handoff

| Path | State | Meaning |
|---|---|---|
| `docs/recovery/rift-window-capture-app-plan.md` | New/untracked | Full screen-capture app implementation plan saved for resume. |
| `docs/recovery/README.md` | Modified | Earlier native RIFT screenshot keybind/current-truth documentation update. |
| `docs/recovery/current-truth.json` | Modified | Earlier native screenshot proof/current truth update; JSON validation passed earlier. |
| `docs/recovery/current-truth.md` | Modified | Earlier native screenshot proof/current truth update. |
| `docs/recovery/native-rift-screenshot-backend.md` | Modified | Earlier keybind proof update. |

No commit was made during this handoff.

## Proven screenshot/keybind facts from this session

| Item | Current evidence |
|---|---|
| Local RIFT screenshot key | `NUM PAD *` / `VK_MULTIPLY` / `0x6A`. |
| Keybind source | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\mykeybindings`. |
| Live verification result | Native screenshot capture worked with Numpad `*`. |
| Native screenshot artifact | `C:\Users\mrkoo\OneDrive\Documents\RIFT\Screenshots\2026-05-14_014934.jpg`. |
| Repo proof copy | `scripts/captures/native-screenshot-keybind-20260514-014933/rift-native-numpad-multiply-screenshot-20260514-054934.jpg`. |
| Important boundary | Native screenshot helper sends screenshot input; it is a separate proof path, not the general full-window capture standard. |

## Existing full-window capture helper facts

| Item | Current evidence |
|---|---|
| Existing project | `tools/rift-window-capture/RiftWindowCapture.csproj`. |
| Framework | `net10.0-windows10.0.19041.0`. |
| Current dependencies | `Vortice.Direct3D11`, `Vortice.DXGI`, `System.Drawing.Common`. |
| Existing wrapper | `scripts/capture-rift-window-wgc.ps1`. |
| Current known behavior | WGC exact-window and DXGI desktop fallback were tested earlier and returned usable BMP artifacts. |
| Main gap | Not yet promoted to a polished canonical capture engine with explicit `--hwnd`, manifest/log bundle, Raw `BGRA32` contract, PNG standard, crop profiles, benchmark/offline commands, and Python wrapper. |

## Saved app plan summary

The saved plan says the repo-standard screen capture app should be:

| Requirement | Planned standard |
|---|---|
| Low-level core | C# / `.NET 10`. |
| Primary backend | Windows.Graphics.Capture exact HWND/window. |
| Fallback backend | DXGI Desktop Duplication + crop. |
| Internal processing | Raw `BGRA32`. |
| Human/debug artifact | PNG. |
| Logging | Timestamped `manifest.json` + `logs/run.jsonl` + `summary.md`. |
| Offline support | `inspect`, `validate`, `convert`, `crop`, `diff`, `benchmark`. |
| Automation | Python wrapper; PowerShell only thin launcher/legacy leaf. |
| Promotion rule | Do not call it canonical until build + exact-HWND live smoke + manifest/log validation pass. |

## Safety boundaries for resume

| Boundary | Rule |
|---|---|
| Game input | Do not send movement/input from the screen-capture app. |
| Native screenshot key | Allowed only through the separate native screenshot proof helper when explicitly needed. |
| CE/x64dbg | Do not use unless explicitly reauthorized in the current conversation. |
| Stale PID/HWND | Re-check target PID/HWND/process-start before any live smoke. |
| Capture truth | Old screenshots are artifacts only; freshness must come from manifest timestamps and current target validation. |
| ChromaLink | Treat as external provider; do not edit provider repo from this RiftReader-focused lane. |

## Recommended next coding slice

| # | Action | Why |
|---:|---|---|
| 1 | Inspect current `tools/rift-window-capture` source | Avoid rewriting working capture behavior blindly. |
| 2 | Add explicit `--hwnd` support if missing | Exact window targeting is the first reliability requirement. |
| 3 | Add process-start validation option | Prevent stale PID/HWND mistakes. |
| 4 | Add `--output-root` bundle mode | Gives every run a durable artifact directory. |
| 5 | Add `manifest.json` | Makes target, timing, backend, quality, and artifacts machine-readable. |
| 6 | Add `logs/run.jsonl` | Captures timestamped stages/errors for debugging. |
| 7 | Preserve existing wrapper compatibility | Avoid breaking proven helper calls. |
| 8 | Build the C# project | First validation gate. |
| 9 | Run non-live/offline tests first | Avoid live dependency during basic validation. |
| 10 | Only then run exact-HWND live smoke if approved/current | Validate the real target after safer gates pass. |

## Resume prompt for new chat

```text
Resume RiftReader screen-capture app work from:
docs/handoffs/2026-05-14-0227-screen-capture-app-plan-resume.md
and
docs/recovery/rift-window-capture-app-plan.md.

First inspect git status and current tools/rift-window-capture source. Preserve
existing uncommitted docs. Implement the smallest safe first slice:
explicit --hwnd targeting, process-start validation if missing, output-root
manifest/log bundle, and preserved wrapper compatibility. Build/test before any
live smoke. Do not send game input, do not move the player, do not use CE/x64dbg,
and do not promote the helper as canonical until exact-HWND live capture plus
manifest validation pass.
```
