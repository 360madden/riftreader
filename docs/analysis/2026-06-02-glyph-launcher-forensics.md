# Glyph launcher forensics inventory — 2026-06-02

## Verdict

Safe, read-only Glyph launcher forensics completed against the currently running
logged-in Glyph client. The run did **not** attach a debugger, dump process
memory, read process memory, extract credentials, bypass authentication, or send
game/client input.

Primary artifact:

- `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-forensics-inventory-20260602-112122-862149\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-forensics-inventory-20260602-112122-862149\summary.md`

Compact health packet:

- `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-health-packet-20260602-112204-164871\summary.json`

Offline Ghidra artifact:

- Static JSON export from analyzed Ghidra project:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-ghidra-static-export-20260602-104218\glyph-static-summary.json`
  - `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-ghidra-static-export-20260602-104218\postscript.log`
- Full dependency-bundle pass:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-ghidra-bundle-20260602-100440\summary.json`
  - `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-ghidra-bundle-20260602-100440\analyzeHeadless-import.log`
  - Project: `C:\RIFT MODDING\RiftReader\scripts\captures\ghidra-static-projects\glyph-bundle-project-20260602-100440`
  - Bundle: `C:\RIFT MODDING\RiftReader\scripts\captures\glyph-static-bundle-20260602-100440`
- Initial single-binary pass:
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
| Process module enumeration query | `true` |
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
| `CheckRemoteDebuggerPresent` on Glyph PIDs | `ok=true`, value `false` for both `GlyphCrashHandler64.exe` and `GlyphClientApp.exe` |
| `NtQueryInformationProcess(ProcessDebugPort)` | `ntstatus=0`, value `0` for both Glyph PIDs |
| `NtQueryInformationProcess(ProcessDebugObjectHandle / ProcessDebugFlags)` | Query returned status errors, so these two classes remain inconclusive |

Conclusion: there was no obvious debugger process by name, and the two strongest
query-only checks available without attaching (`CheckRemoteDebuggerPresent` and
`ProcessDebugPort`) did not indicate an attached debugger. This is still not a
kernel-grade proof because I did not attach a debugger or inspect debug objects
directly while the client was logged in and live.

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

Signature trust rollup:

| Surface | Status counts | Non-valid count |
|---|---|---:|
| Glyph executables | `NotSigned=3`, `Valid=3` | `3` |
| Launcher/game dependency DLLs | `Valid=7`, `NotSigned=31` | `31` |

Loaded module origin rollup from the live Glyph processes:

| Process/module surface | Result |
|---|---:|
| Glyph processes with module lists | `2` |
| Total loaded modules classified | `187` |
| Modules from Glyph install root | `26` |
| Modules from Windows root | `161` |
| Non-Windows/non-Glyph loaded modules | `0` |
| Unique loaded module paths signature-checked | `131` |
| Loaded module signature statuses | `Valid=111`, `NotSigned=20` |
| Windows loaded module signature statuses | `Valid=105` |
| Glyph-install loaded module signature statuses | `Valid=6`, `NotSigned=20` |
| Non-Windows/non-Glyph non-valid loaded signatures | `0` |

Interpretation: the query-only module inventory did not show obvious injected or
third-party loaded DLLs outside Windows and the Glyph install root. This is not a
kernel-grade anti-tamper proof, but it is a useful non-invasive signal for the
"may already have something attached" concern.

The loaded modules that were `NotSigned` were all inside the Glyph install root:
`GlyphCrashHandler64.exe`, `Qt5Core.dll`, `SSLEAY32.dll`, `Qt5Gui.dll`,
`Qt5Network.dll`, `Qt5Xml.dll`, `Qt5Widgets.dll`,
`libzmq-v120-mt-4_3_5.dll`, `xlpack.dll`, `icuin57.dll`, `LIBEAY32.dll`,
`Qt5Multimedia.dll`, `Qt5WinExtras.dll`, `icuuc57.dll`, `icudt57.dll`,
`qwindows.dll`, `qgif.dll`, `qjpeg.dll`, `qwebp.dll`, and
`qtaudio_windows.dll`.

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
| `C:\Program Files (x86)\Glyph\Games\RIFT\Live\manifest64.txt` | RIFT Live manifest, version `STABLE-1-1152-a-1256395` |
| `C:\Program Files (x86)\Glyph\Games\RIFT\Live\assets64*.manifest` | Large RIFT asset manifests; metadata captured, contents not dumped |
| `C:\Users\mrkoo\AppData\Roaming\RIFT\*.cfg` / `rift.log` | RIFT-side config/log files found adjacent to Glyph/RIFT usage |

Structured config inventory:

| Config surface | Parser | Status | Captured detail |
|---|---|---|---|
| `C:\Program Files (x86)\Glyph\GlyphClient.xml` | XML | passed | root `Config`, `34` elements captured, `25` endpoint references |
| `C:\Program Files (x86)\Glyph\Library\GlyphLibrary.xml` | XML | passed | root `Config`, `120` capped elements captured, `25` endpoint references |
| `C:\Users\mrkoo\AppData\Local\Glyph\GlyphClient.cfg` | key/value | passed | `34` keys |
| `C:\Users\mrkoo\AppData\Roaming\RIFT\recents.cfg` | key/value | passed | `12` keys |
| `C:\Users\mrkoo\AppData\Roaming\RIFT\rift.cfg` | key/value | passed | `79` keys |
| `C:\Users\mrkoo\AppData\Roaming\RIFT\riftconnect.cfg` | key/value | passed | `1` key |
| `C:\Users\mrkoo\AppData\Roaming\RIFT\rifterrorhandler.cfg` | key/value | passed | empty file / `0` keys |
| `C:\ProgramData\Glyph\GlyphLibrary.cfg` | key/value | passed | `2` keys |

The structured config parser stores redacted keys, element paths, endpoint
references, and capped value previews only; sensitive account/auth/cookie/token
values remain redacted.

Registry keys found:

| Key | Notable values |
|---|---|
| `HKCU:\Software\Trion\Instances\C:-Program Files (x86)-Glyph-GlyphClientApp.exe` | `ProcessId=48284`, `MainWindow=5703490`, `ProcessName=GlyphClientApp.exe` |
| `HKCU:\Software\Trion\Recovery\C:-Program Files (x86)-Glyph-GlyphClient.exe` | recovery URL `http://glyph.dyn.triongames.com/glyph/live/GlyphInstall.exe`, proxy fields empty |

## Persistence, services, tasks, uninstall, and network

| Surface | Finding |
|---|---|
| Glyph-owned active TCP connections | none reported by `Get-NetTCPConnection` during the latest helper run |
| Services matching Glyph/Trion/RIFT/gamigo | none found |
| Scheduled tasks matching Glyph/Trion/RIFT/gamigo | none found |
| Startup autorun | `HKCU:\Software\Microsoft\Windows\CurrentVersion\Run`, name `Glyph Client`, value `C:\Program Files (x86)\Glyph\GlyphClient.exe -hidden` |
| Uninstall entry `Glyph` | publisher `Trion Worlds, Inc.`, install location `C:\Program Files (x86)\Glyph\`, uninstall command `C:\Program Files (x86)\Glyph\glyphuninstall.exe` |
| Uninstall entry `RIFT` | publisher `gamigo US Inc.`, install location `C:\Program Files (x86)\Glyph\Games\RIFT\Live`, uninstall command `GlyphClientApp.exe -uninstall -game 1` |

## Manifest, dependency, endpoint, and log aggregation

| Surface | Result |
|---|---:|
| Targeted config/install files found | `21` |
| Structured config files parsed | `8` |
| Structured config endpoint references | `50` |
| Launcher/game dependency DLLs hashed | `38` |
| Parsed manifests | `2` |
| Consolidated endpoints/domains | `115` |
| Log timeline events | `4070` |
| HTTP/download-related log events | `632` |
| Version-related log events | `141` |
| Maintenance-related log events | `17` |
| Selection-server log events | `9` |

Parsed manifests:

| Manifest | Version | Entries | Parsed total size |
|---|---|---:|---:|
| `C:\Program Files (x86)\Glyph\library_manifest.txt` | `stable-251-1-a-335833` | `280` | `31050568` bytes |
| `C:\Program Files (x86)\Glyph\Games\RIFT\Live\manifest64.txt` | `STABLE-1-1152-a-1256395` | `27` | `142548742` bytes |

Top endpoint/domain clusters in the consolidated inventory included:

- `www.glyph.net`
- `glyph.dyn.triongames.com`
- `client.downloader.gamigo.com`
- `store.trionworlds.com`
- `auth.trionworlds.com`
- `webcdn.triongames.com`
- `debug.triongames.com`
- `rift-update.dyn.triongames.com`

The RIFT-side log timeline included a latest character-selection failure:

- selection server status: `failed-all-addresses`
- selection failure event count: `3`
- attempted `144.217.46.224:6527`
- failed, then attempted alternate `144.217.46.224:80`
- failed again with `Failed to connect to selection server using any address`

Structured log summary:

| Log signal | Result |
|---|---:|
| HTTP status codes | `200=40`, `404=6` |
| Glyph task type counts | `GetVersions=51` |
| HTTP/download-related events | `632` |
| Version-related events | `141` |
| Maintenance-related events | `17` |
| Selection-server events | `9` |

Interpretation: Glyph repeatedly completed patch/version checks and also saw
maintenance RSS requests return `404`; the world-entry failure is isolated in
RIFT-side selection-server connection attempts rather than in Glyph login or
patch-version acquisition.

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

## PE/import inventory

The enhanced helper parsed local PE headers/imports without using a debugger.

| File | Format | Machine | Subsystem | Import DLLs | TLS directory |
|---|---|---|---|---:|---|
| `GlyphClientApp.exe` | `PE32` | `I386` | `WINDOWS_GUI` | `29` | present |
| `GlyphCrashHandler64.exe` | `PE32+` | `AMD64` | `WINDOWS_GUI` | `12` | present |
| `GlyphClient.exe` | `PE32` | `I386` | `WINDOWS_GUI` | `9` | present |
| `GlyphCrashHandler.exe` | `PE32` | `I386` | `WINDOWS_GUI` | `15` | present |
| `GlyphDownloader.exe` | `PE32` | `I386` | `WINDOWS_GUI` | `9` | missing |
| `GlyphUninstall.exe` | `PE32` | `I386` | `WINDOWS_GUI` | `11` | missing |

`GlyphClientApp.exe` imports include Windows APIs plus:

- `Qt5Core.dll`, `Qt5Network.dll`, `Qt5Gui.dll`, `Qt5Widgets.dll`,
  `Qt5Xml.dll`, `Qt5Multimedia.dll`, `Qt5WinExtras.dll`
- `SSLEAY32.dll`, `LIBEAY32.dll`
- `libzmq-v120-mt-4_3_5.dll`
- `steam_api.dll`
- `xlpack.dll`

## Ghidra result

Ghidra was run headless against copied static binaries only.

Full dependency-bundle pass:

- Binary copy: `glyph-static-bundle-20260602-100440\GlyphClientApp.exe`
- Bundle included the launcher-adjacent Qt/OpenSSL/ZMQ/Steam/xlpack DLLs.
- Language/compiler: `x86:LE:32:default:windows`
- Import/save: succeeded
- Analysis: succeeded; no timeout
- Total Ghidra analysis time: about `206` seconds
- PDB: not found
- Library search count: `29`
- Missing dependency count in the bundle pass: `0`

Static Ghidra JSON export:

- Program: `GlyphClientApp.exe`
- Language/compiler: `x86:LE:32:default` / `windows`
- Memory blocks captured: `8`
- External libraries captured: `29`
- Functions discovered: `19072`
- Instructions discovered: `592558`
- Interesting symbols captured: `600` capped sample
- Interesting strings captured: `800` capped sample
- Defined string records scanned by Ghidra: `3909`
- Total string references captured: `1040`
- Categorized string counts: `patch=242`, `auth=214`, `glyph=149`,
  `store=69`, `endpoint=61`, `steam=44`, `crash=11`, `registry=9`,
  `rift=4`, `other=97`
- Category reference counts: `patch=298`, `auth=277`, `glyph=221`,
  `other=117`, `store=87`, `endpoint=73`, `steam=35`, `registry=16`,
  `crash=10`, `rift=0`
- Top referenced functions by category are exported in
  `interestingStringSummary.topReferencedFunctionsByCategory`; examples:
  `patch` starts with `FUN_00460680` (`19` string references),
  `FUN_0049f900` (`19`), and `FUN_005126a0` (`13`);
  `auth` starts with `FUN_004ba7b0` (`32` string references),
  `FUN_00523fe0` (`23`), `FUN_00522de0` (`19`), and
  `FUN_00523bb0` (`16`), while `endpoint` starts with `FUN_00415080`
  (`8`), `FUN_0041d950` (`5`), and `FUN_004b5d10` (`5`).
- Example exported strings/functions cluster around auth/login, HTTP, manifests,
  patching, store/commerce, crash handling, support URLs, registry, Steam, and
  Glyph/RIFT naming.

Initial single-binary pass:

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
