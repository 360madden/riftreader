# C# SendInput ScanCode movement proof — 2026-05-11

## Verdict

**C# `SendInput` ScanCode is proof-backed for bounded RIFT forward movement calibration.**

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

## Backend policy update

1. `tools/RiftReader.SendInput` / `scripts/send-rift-key-csharp.ps1` is now the preferred SendInput diagnostic path.
2. Use `--input-mode ScanCode` first for RIFT movement tests.
3. Legacy `scripts/send-rift-key.ps1` remains diagnostic/legacy and should not be treated as the authoritative SendInput implementation.
4. `scripts/post-rift-key.ps1 -SkipBackgroundFocus -UseWindowMessage` remains a working exact-HWND window-message backend.
5. Do **not** auto-send `Esc`; RIFT must be in gameplay input mode, and chat/text-entry mode is currently operator-managed because no reliable detector exists.
6. Proof-anchor validity is not required for bounded backend calibration, but it remains required for navigation/proof promotion.

## Interpretation

- C# SendInput ScanCode is proof-backed for bounded forward movement calibration on this target/session.
- PowerShell send-rift-key.ps1 remains legacy/diagnostic; earlier PowerShell VirtualKey and ScanCode tests delivered but did not produce movement.
- post-rift-key.ps1 -SkipBackgroundFocus -UseWindowMessage remains a working alternative backend.
- Do not auto-send Esc. Operator must keep RIFT in gameplay input mode because no reliable chat/text-entry detector exists.
