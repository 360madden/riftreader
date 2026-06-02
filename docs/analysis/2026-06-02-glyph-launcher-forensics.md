# Glyph launcher forensics inventory — 2026-06-02

## Verdict

Safe, read-only Glyph launcher forensics completed against the currently running
logged-in Glyph client. The run did **not** attach a debugger, dump process
memory, read process memory, extract credentials, bypass authentication, or send
game/client input.

Primary artifact:

- `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-forensics-inventory-20260602-095053-584299\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-forensics-inventory-20260602-095053-584299\summary.md`

Offline Ghidra artifact:

- `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-ghidra-20260602-094338\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-ghidra-20260602-094338\analyzeHeadless-import.log`
- Project: `C:\RIFT MODDING\RiftReader\scripts\captures\ghidra-static-projects\glyph-project-20260602-094338`
- Imported copy: `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-static-binaries\GlyphClientApp-0fdc197aa714.exe`

## Safety posture

| Check | Result |
|---|---|
| Debugger attached by helper | `false` |
| x64dbg / Cheat Engine attach | `false` |
| Process memory dumped | `false` |
| Process memory read | `false` |
| Target bytes written | `false` |
| Credential/token extraction attempted | `false` |
| Redaction enabled | `true` |

## Running Glyph process tree

| Process | PID | Parent PID | Path | Start |
|---|---:|---:|---|---|
| `GlyphCrashHandler64.exe` | `59540` | `61908` | `C:\Program Files (x86)\Glyph\x64\GlyphCrashHandler64.exe` | `2026-06-02T05:08:37.188541-04:00` |
| `GlyphClientApp.exe` | `48284` | `59540` | `C:\Program Files (x86)\Glyph\GlyphClientApp.exe` | `2026-06-02T05:08:37.364058-04:00` |

Interpretation: the active UI/client process is `GlyphClientApp.exe`; the
64-bit crash handler is its parent and launches it with the Glyph install root.

## Debugger / "already attached" indicators

| Probe | Result |
|---|---|
| Known debugger-like process names (`x64dbg`, `cheat`, `ida`, `ghidra`, `windbg`, etc.) | None found in the local process list during this run |
| `CheckRemoteDebuggerPresent` on Glyph PIDs | Query attempted but returned `ok=false` |
| `NtQueryInformationProcess` debug classes | Returned access-denied / invalid-info statuses, so status is inconclusive |

Conclusion: there was no obvious debugger process by name, but the query-only
debugger checks were inconclusive. I did not use a debugger attach to resolve
that ambiguity because the client was logged in and live.

## Executable inventory

| File | SHA-256 | Version | Authenticode |
|---|---|---|---|
| `GlyphClientApp.exe` | `0fdc197aa71417542da7df73b2296969b11bf8c4763c0352ea78d9ee6bd2b7ec` | `1.251.1.335833` | `Valid`, signer `gamigo AG` |
| `GlyphClient.exe` | `948ef92a4df4293b278b1fb5bcd82f59a9380b9dfa12e5472c774069f96785b4` | `1.0.0.0` | `Valid`, signer `gamigo AG` |
| `GlyphUninstall.exe` | `8824c0b77b5679e18288f3e1125745df7666b6bc892d853edbe192be519d7ffa` | `1.0.0.0` | `Valid`, signer `gamigo AG` |
| `GlyphCrashHandler64.exe` | `29add54345f52f5f2dd30cc8e7ffc50d648e0fd4f410eea025a8e397af3074b0` | not reported | `NotSigned` locally |
| `GlyphCrashHandler.exe` | `218eaae1f0b6e1d6e039b385dbd0a01a98789c85e0231825c1bdace44eb8f68e` | `1.0.0.0` | `NotSigned` locally |
| `GlyphDownloader.exe` | `058aaa2a82564258c22b89f98be5cb3a42ce515dea15770027e850603d905b70` | `1.0.0.0` | `NotSigned` locally |

`GlyphClientApp.exe` product/version string observed in static strings:
`Glyph (stable-251-1-a-335833)`.

## Config and log locations found

| Path | Purpose / notable content |
|---|---|
| `C:\Program Files (x86)\Glyph\GlyphClient.xml` | Main client config: game base path, self-update URLs, auth/store/commerce endpoints, support URL, client metrics/log upload endpoints, notification server |
| `C:\ProgramData\Glyph\GlyphLibrary.cfg` | Install registry for Glyph/RIFT: `RIFT-Live` installed under `Games/RIFT/Live` |
| `C:\Users\mrkoo\AppData\Local\Glyph\GlyphClient.cfg` | User Glyph settings: language, last game, keep logged in, games path, depot list, RIFT EULA flag; account/email fields redacted |
| `C:\Users\mrkoo\AppData\Local\Glyph\Logs\GlyphClient.0.log` | Current/rotated client log; showed RIFT version checks and patch endpoint requests |
| `C:\Users\mrkoo\AppData\Local\Glyph\Logs\GlyphClient.1.log` | Prior client log; mostly TLS certificate material in tail |
| `C:\Users\mrkoo\AppData\Local\Glyph\Logs\GlyphClient.9.log` | Older client log; mostly TLS certificate material in tail |
| `C:\Program Files (x86)\Glyph\library_manifest.txt` | Glyph library manifest |
| `C:\Program Files (x86)\Glyph\Library\GlyphLibrary.xml` | Installed library metadata |
| `C:\Program Files (x86)\Glyph\Notification.log` | Notification TCP connect/disconnect history |
| `C:\Users\mrkoo\AppData\Roaming\RIFT\*.cfg` / `rift.log` | RIFT-side config/log files found adjacent to Glyph/RIFT usage |

Registry keys found:

| Key | Notable values |
|---|---|
| `HKCU:\Software\Trion\Instances\C:-Program Files (x86)-Glyph-GlyphClientApp.exe` | `ProcessId=48284`, `MainWindow=5703490`, `ProcessName=GlyphClientApp.exe` |
| `HKCU:\Software\Trion\Recovery\C:-Program Files (x86)-Glyph-GlyphClient.exe` | recovery URL `http://glyph.dyn.triongames.com/glyph/live/GlyphInstall.exe`, proxy fields empty |

## Network/service endpoints observed

| Source | Endpoint / domain | Use inferred from context |
|---|---|---|
| `GlyphClient.xml` / logs | `http://glyph.dyn.triongames.com/glyph/live` | Glyph self-update / manifest |
| logs | `http://rift-update.dyn.triongames.com/ch1-live-streaming-client-patch/public/ch1-live64.txt` | RIFT Live 64-bit version file |
| `GlyphClient.xml` | `https://auth.trionworlds.com` | Authentication |
| `GlyphClient.xml` | `https://store.trionworlds.com` | Store/client metrics/log upload |
| `GlyphClient.xml` | `https://commerce.trionworlds.com` | Commerce/account services |
| logs | `http://client.downloader.gamigo.com/rss/RIFT-maintenance-en.xml` | Maintenance/news RSS; returned `404` during the inspected tail |
| `Notification.log` / config | `34.159.88.99:6666` and `34.159.88.99:6667` | Notification socket attempts |
| crash handler strings | `debug.triongames.com` | Crash report service |

Sensitive cookies/account values in logs and config were redacted.

## Static reverse-engineering notes

Static strings and Ghidra import indicate a Qt-based launcher/patcher with:

- Authentication/login/autologin flows (`AuthAPI`, `AuthUrl`, `AnonymousLogin`,
  `refresh_auth_token`, `weblogin`, `sendAuthCode`).
- Patch/manifest engine (`DownloadManifest`, `ManifestName`,
  `RecoveryManifestName`, `assets.manifest`, `manifest.txt`, `.patch`,
  `PatchingEngine*.cpp`, `PatchingDirector*.cpp`).
- Self-recovery/bootstrapper behavior (`GlyphClient.exe`, recovery URL,
  `GlyphInstall.exe`, crash-handler kill/relaunch strings).
- Crash packaging/upload workflow (`TWN_crash.dmp`, `TWN_crash.zip`,
  `CrashServicePath`, `CrashServiceServer`).
- Registry usage under `SOFTWARE\Trion` and runtime instance keys under
  `HKCU:\Software\Trion`.
- Steam integration strings and `steam_api.dll` dependency references.

## Ghidra result

Ghidra was run headless against a copied static binary only:

- Binary copy: `GlyphClientApp-0fdc197aa714.exe`
- Language/compiler: `x86:LE:32:default:windows`
- Import/save: succeeded
- PDB: not found
- Analysis timeout: 120-second per-file budget was hit after about 156 seconds,
  but the project saved successfully.
- TLS callback locations were reported by Ghidra.
- Import/library references included Windows DLLs plus third-party/runtime
  names such as `QT5CORE.DLL`, `QT5NETWORK.DLL`, `QT5GUI.DLL`,
  `QT5WIDGETS.DLL`, `SSLEAY32.DLL`, `LIBEAY32.DLL`,
  `LIBZMQ-V120-MT-4_3_5.DLL`, `STEAM_API.DLL`, and `XLPACK.DLL`.

## Maintenance-relevant log evidence

The latest inspected `GlyphClient.0.log` tail showed:

- Local RIFT version: `STABLE-1-1152-a-1256395`
- Remote version check against
  `http://rift-update.dyn.triongames.com/ch1-live-streaming-client-patch/public/ch1-live64.txt`
- Successful HTTP `200` version-file download at `2026-06-02T09:38:44Z`
- `RIFT-maintenance-en.xml` request returned `404` in the inspected tail
- A game/auth cookie was present in the log line and was redacted in all
  repo-owned summaries

This supports that Glyph could still log in and check patch state while RIFT
world entry was unavailable or under maintenance.

## What was not done

- No live debugger attach to Glyph.
- No memory dump or token extraction.
- No attempt to bypass launcher, authentication, patching, DRM, or maintenance.
- No network interception or packet capture.
- No destructive or write operations against the Glyph install/config.

# END_OF_GLYPH_LAUNCHER_FORENSICS
