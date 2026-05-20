# C# SendInput ScanCode movement proof — 2026-05-11

## Verdict

**C# `SendInput` ScanCode is proof-backed for bounded RIFT movement-key calibration and is now the only allowed diagnostic movement backend.**

This supersedes the earlier working assumption that SendInput was only delivering at the Windows API level without producing gameplay movement. The measured run below proves a fresh API-coordinate displacement after the repo-owned C# sender pressed `w` for `750 ms`.

## Measured proof

| Field | Value |
|---|---|
| Status | `passed-csharp-sendinput-scancode-displacement` |
| Target | `rift_x64` PID `35728`, HWND `0x60E42` |
| Tool | `RiftReader.SendInput` |
| Commit | `06d82cd29bc173d4145829513b8eb521c0d9c6f5` |
| Wrapper | `scripts/send-rift-key-csharp.ps1` |
| Project | `tools/RiftReader.SendInput/RiftReader.SendInput.csproj` |
| Method | `scripts/send-rift-key-csharp.ps1 --input-mode ScanCode --key w --hold-ms 750` |
| Key | `w` |
| Virtual key | `0x57` |
| Scan code | `0x11` |
| Hold | `750 ms` |
| Sent input events | `2` |
| Exact HWND foreground | `true` |
| Target process foreground | `true` |

## Coordinate evidence

| Coordinate | X | Y | Z | Captured UTC |
|---|---:|---:|---:|---|
| Before | `7405.9297` | `871.78` | `3028.05` | `2026-05-11T04:06:35.7533031Z` |
| After | `7405.0498` | `871.78` | `3027.7` | `2026-05-11T04:07:04.5383657Z` |

| Delta | Value |
|---|---:|
| DeltaX | `-0.8798999999999069` |
| DeltaY | `0.0` |
| DeltaZ | `-0.3500000000003638` |
| Planar distance | `0.9469551256527897` |
| Spatial distance | `0.9469551256527897` |

## Safety/provenance

| Item | Value |
|---|---|
| Automatic `Esc` used | `false` |
| Proof anchor required for backend calibration | `false` |
| Cheat Engine used | `false` |
| SavedVariables live truth used | `false` |
| `/reloadui` used | `false` |
| Run root | `C:\RIFT MODDING\RiftReader\scripts\captures\csharp-sendinput-measured-proof-20260511-000537` |


## 2026-05-20 post-incident retests

| Key | Binding | Target | Hold | Result | Fresh coordinate delta | Artifact |
|---|---|---|---:|---|---|---|
| `W` | Move Forward | PID `1948`, HWND `0x3C0D58` | `150 ms` | `passed`; exact HWND foreground true; post-release stability passed | spatial ~`1.0002m` | `.riftreader-local/spin-diagnosis/csharp-w-test/csharp-w-test-summary.json` |
| `Q` | Strafe Left | PID `1948`, HWND `0x3C0D58` | `250 ms` | `passed`; exact HWND foreground true; post-release stability passed | `dx=-1.35`, `dy=-0.49`, `dz=+0.99`, spatial `1.7443m` | `.riftreader-local/q-key-retest-csharp/clean-run-20260519-222554/q-retest-summary.json` |

The `Q` retest used a clean game-only baseline; an earlier same-key visual delta was discarded because a Windows context menu overlay contaminated the screenshot. These retests promote the backend for bounded diagnostics only, not route/navigation automation.
## Backend policy update

1. `tools/RiftReader.SendInput` / `scripts/send-rift-key-csharp.ps1` is now the preferred SendInput diagnostic path.
2. Use `--input-mode ScanCode` first for RIFT movement tests.
3. Legacy `scripts/send-rift-key.ps1` remains diagnostic/legacy and should not be treated as the authoritative SendInput implementation.
4. Legacy `scripts/post-rift-key.ps1 -SkipBackgroundFocus -UseWindowMessage` is retired for diagnostic movement automation after the 2026-05-20 spin incident; current gates fail it closed.
5. Do **not** auto-send `Esc`; RIFT must be in gameplay input mode, and chat/text-entry mode is currently operator-managed because no reliable detector exists.
6. Proof-anchor validity is not required for bounded backend calibration, but it remains required for navigation/proof promotion.
7. Route/navigation automation remains paused until the movement gate is explicitly cleared; C# ScanCode proof does not by itself clear route automation.

## Interpretation

- C# SendInput ScanCode is proof-backed for bounded movement-key calibration and is the only allowed diagnostic movement backend.
- PowerShell send-rift-key.ps1 remains legacy/diagnostic; earlier PowerShell VirtualKey and ScanCode tests delivered but did not produce movement.
- post-rift-key.ps1 -SkipBackgroundFocus -UseWindowMessage is retired for movement diagnostics after the spin incident; current gates fail it closed.
- Do not auto-send Esc. Operator must keep RIFT in gameplay input mode because no reliable chat/text-entry detector exists.
