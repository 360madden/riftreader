# RiftReader handoff - ChromaLink live coordinate capture resolved

Created: 2026-05-01 12:27:07 -04:00 local / 2026-05-01 16:27:07Z UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
RiftReader HEAD at handoff: `e3d51a0 Harden ChromaLink capture validation`
RiftReader remote status at handoff: `main...origin/main`
ChromaLink repo: `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink`
ChromaLink HEAD at handoff: `bf4c297 Keep player position in ChromaLink rotation`
ChromaLink remote status at handoff: `main...origin/main`
Status note: this handoff file is newly created in RiftReader and is not committed unless a later step records it.

## TL;DR

- The ChromaLink/RiftReader live coordinate capture blocker was resolved.
- The live RIFT client was resized from `750x468` to the ChromaLink `P360C` profile size `640x360`.
- ChromaLink rotation was patched and pushed so `playerPosition` is emitted in both normal and combat rotation paths.
- `/reloadui` was sent with approval so the loaded addon picked up the rotation change.
- A real RiftReader ChromaLink HTTP capture passed and wrote `live-coords.ndjson` with fresh coordinates.
- RiftReader repo is clean at `e3d51a0`; ChromaLink repo is clean at `bf4c297`.
- Main remaining hardening: make standard ChromaLink watch/stack launchers prefer `--backend screen`, because the successful capture path used `ScreenBitBlt`.

## Current truth snapshot

| Area | Current truth |
|---|---|
| RIFT client geometry | `640x360` client area after approved prepare-window run |
| ChromaLink profile | `P360C`, dual-strip, `640x360` client, `640x24` band, `stripCount = 2` |
| ChromaLink coordinate capability | Directly emits `playerPosition` over optical strip and HTTP world-state when rotation includes `playerPosition` |
| ChromaLink limitations | Does not expose heading/facing/yaw/orientation, route planning, or movement control |
| ReaderBridge role | Still primary/native ReaderBridge truth surface for repo memory/pointer provenance; ChromaLink is external live coordinate truth for scoring/cross-checking |
| SavedVariables | Not used as live truth; ChromaLink capture writes `savedvariables-freshness.json` as `not-used` |
| PlayerCoords addon | Not required for this path; do not reintroduce it as a live truth dependency |

## Commits now on remotes

| Repo | Branch | Commit | Purpose |
|---|---|---:|---|
| `C:\RIFT MODDING\RiftReader` | `main` | `e3d51a0` | Harden ChromaLink capture validation: fail closed on non-2xx HTTP, strict bridge readiness, promotion truth-surface allowlist, capture metadata bundle files |
| `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink` | `main` | `bf4c297` | Keep `playerPosition` in ChromaLink normal and combat rotations |

## Completed work in this slice

| # | Completed item | Evidence |
|---:|---|---|
| 1 | Resized live RIFT client to ChromaLink profile | `prepare-window` reported `AfterClient: 40,63 640x360`, `Success: true` |
| 2 | Verified geometry visually through MCP capture | MCP capture image size changed to `640x360` |
| 3 | Patched ChromaLink normal rotation | `Core/Config.lua` now includes `playerPosition` after initial `playerVitals`/`coreStatus` pair |
| 4 | Patched ChromaLink combat override rotation | `RIFT/Bootstrap.lua` combat rotation now includes `playerPosition` too |
| 5 | Reloaded live addon after code patch | Approved `/reloadui` sent successfully |
| 6 | Verified ChromaLink decoder after geometry and reload | `ChromaLink.Cli.exe live 30 100 --backend screen` returned `AcceptedSamples: 60`, `RejectedSamples: 0` |
| 7 | Verified player coordinates were in the ChromaLink aggregate | `AggregatePlayerPosition: seq=173 ageMs=207 pos=7447.31,887.85,3027.19` |
| 8 | Ran real RiftReader ChromaLink HTTP capture | Capture wrapper returned `status: pass`, `fresh: true`, `exported: true`, `samplesWritten: 1` |
| 9 | Verified capture wrote live coord NDJSON | `live-coords.ndjson` contains fresh sample `x=7447.31`, `y=887.85`, `z=3027.19` |
| 10 | Pushed ChromaLink patch | `bf4c297` pushed to `origin/main` |

## Key successful artifact

Successful real capture bundle:

`C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867`

Important files in that bundle:

| Artifact | Path |
|---|---|
| Live coords | `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867\live-coords.ndjson` |
| Capture plan | `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867\capture-plan.json` |
| Quality gate | `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867\quality-gate.json` |
| Truth surface | `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867\truth-surface.json` |
| Bridge readiness | `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867\chromalink-http-bridge-readiness.json` |
| Contract proof | `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867\chromalink-world-state-contract.json` |
| SavedVariables freshness | `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867\savedvariables-freshness.json` |
| Artifact index | `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867\artifact-index.json` |

Live coordinate NDJSON sample:

```json
{"schemaVersion":1,"mode":"live-coord-sample","source":"chromalink-live-telemetry","sourceView":"chromalink-riftreader-world-state","inputMode":"world-state-url","sourceContractName":"chromalink-live-telemetry","sourceContractSchemaVersion":2,"sourceViewContractName":"chromalink-riftreader-world-state","sourceViewContractSchemaVersion":1,"fresh":true,"stale":false,"aggregateReady":true,"aggregateHealthy":true,"aggregateStale":false,"x":7447.31,"y":887.85,"z":3027.19}
```

## Commands that produced the successful state

### Resize RIFT to ChromaLink profile

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\scripts\Run-ChromaLink.ps1" -Mode prepare-window -Argument1 32 -Argument2 32
```

Observed success:

```text
RequestedClient: 640x360
AfterClient: 40,63 640x360
Success: true
Reason: Window client area matches the requested profile.
```

### Reload addon after rotation patch

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\scripts\Reload-RiftUi.ps1"
```

### Verify ChromaLink live decode and player position

```powershell
& "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\DesktopDotNet\ChromaLink.Cli\bin\Debug\net9.0-windows\ChromaLink.Cli.exe" live 30 100 --backend screen
```

Observed success:

```text
AcceptedSamples: 60
RejectedSamples: 0
FrameCount[PlayerPosition/schema-1]: 7
AggregatePlayerPosition: seq=173 ageMs=207 pos=7447.31,887.85,3027.19
LastBackend: ScreenBitBlt
```

### Successful RiftReader ChromaLink capture pattern

Important: keep a ChromaLink watch loop running with `--backend screen` while calling the RiftReader wrapper.

```powershell
$cliExe = "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\DesktopDotNet\ChromaLink.Cli\bin\Debug\net9.0-windows\ChromaLink.Cli.exe"
$watch = Start-Process -FilePath $cliExe -ArgumentList @('watch','120','100','--backend','screen') -WorkingDirectory "C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink" -WindowStyle Hidden -PassThru

pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\capture-chromalink-live-coords.ps1" `
  -WorldStateUrl "http://127.0.0.1:7337/api/v1/riftreader/world-state" `
  -BundleDirectory "<bundle path>" `
  -StartBridge `
  -BridgeWaitSeconds 10 `
  -BridgeRequestTimeoutSeconds 2 `
  -MaxFreshAgeMilliseconds 5000 `
  -MaxSamples 1 `
  -Json

Stop-Process -Id $watch.Id -Force
```

## Validation already run

| Command / check | Result |
|---|---|
| `dotnet test .\DesktopDotNet\ChromaLink.sln -v minimal` in ChromaLink | Passed, `40/40` |
| `dotnet run --project .\DesktopDotNet\ChromaLink.Cli\ChromaLink.Cli.csproj -- validate` | Passed |
| `git diff --check` in ChromaLink before commit | Passed |
| `ChromaLink.Cli.exe live 30 100 --backend screen` after `/reloadui` | Passed, `60 accepted / 0 rejected` |
| `capture-chromalink-live-coords.ps1 -WorldStateUrl ... -StartBridge` | Passed, wrote `live-coords.ndjson` |
| Process cleanup check | No leftover ChromaLink helper/watch/bridge/capture processes, aside from the command doing the check |
| RiftReader git status | Clean at `main...origin/main` before this handoff file |
| ChromaLink git status | Clean at `main...origin/main` |

## Important caution for the next chat

- The successful capture bundle is under `%TEMP%`; copy it into a durable repo artifact folder before treating it as long-lived evidence.
- Do not promote temp bundle paths into docs as durable truth unless copied or re-captured.
- The previous live approval applied in the prior chat. In a new chat, ask before focusing, resizing, clicking, sending keys, `/reloadui`, or other live game-window input unless the user explicitly renews approval.
- ChromaLink is external/API coordinate truth for scoring and cross-checking. It does not replace ReaderBridge memory/pointer provenance.
- ChromaLink does not provide heading/facing/yaw. Any navigation/facing logic still needs ReaderBridge/native memory or another proven source.

## Remaining blockers / risks

| Blocker or risk | Status | How to resolve |
|---|---|---|
| Standard ChromaLink stack launchers do not force `--backend screen` | Open hardening item | Patch `scripts\Bridge-ChromaLink.cmd` and package launchers to start watch with `--backend screen`, then validate stack readiness and capture again |
| Successful bundle is temp-only | Open hygiene item | Copy `C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867` to a durable `artifacts` or `scripts\captures` path |
| Current proof is one exported sample | Open proof-strength item | Run a 10-30 sample capture while watch loop is active, then use scorer/gate artifacts |
| ReaderBridge vs ChromaLink agreement not yet checked in same moment | Open cross-check item | Run same-time ReaderBridge coordinate read and compare against ChromaLink world-state sample |
| No heading/facing from ChromaLink | Known limitation, not a bug | Keep using ReaderBridge/current native orientation work for facing/yaw |

## Detailed top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Patch `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink\scripts\Bridge-ChromaLink.cmd` so watch starts as `watch <duration> 100 --backend screen`; apply equivalent change to packaged launcher templates if source packaging owns them | The successful live proof used `ScreenBitBlt`; default backend selection can pick a slower backend and temporarily made health fail while frames aged out |
| 2 | Validate the patched launcher by starting the stack, then running `Status-ChromaLinkStack.ps1 -IncludeProcesses` and `Test-ChromaLinkTelemetryReady.ps1 -MaxAgeSeconds 5 -RequireAnyFrame` | Confirms the standard operator path, not just the manual command, produces a fresh healthy snapshot |
| 3 | Run a fresh `capture-chromalink-live-coords.ps1` with `-MaxSamples 10` or `-MaxSamples 30` while the `--backend screen` watch loop is active | A single coordinate point proves plumbing; multiple samples are better for trajectory scoring and promotion-gate evidence |
| 4 | Copy the successful or next fresh capture bundle from `%TEMP%` into a durable path under `C:\RIFT MODDING\RiftReader\artifacts\` or `C:\RIFT MODDING\RiftReader\scripts\captures\` | Temp paths can disappear; durable evidence is needed for handoffs, scoring, review, and future agents |
| 5 | Add a RiftReader preflight/helper check that fails fast if ChromaLink world-state lacks fresh `player.position` before export/scoring | Prevents readiness/API/schema from being mistaken for coordinate truth when rotation or freshness regresses |
| 6 | Add/adjust docs in `C:\RIFT MODDING\RiftReader\docs\candidate-trajectory-promotion-gate.md` to state the repeatable ChromaLink live capture recipe: `640x360`, `/reloadui` after addon changes, `watch ... --backend screen`, then capture wrapper | This prevents future drift back to PlayerCoords, SavedVariables, wrong geometry, or backend-default assumptions |
| 7 | Run a same-moment ReaderBridge coordinate read and ChromaLink coordinate read, then record the delta in a small JSON artifact | Confirms external ChromaLink truth agrees with ReaderBridge/native truth for the current session |
| 8 | Feed the durable ChromaLink `live-coords.ndjson` into `score-candidate-trajectories.ps1` or the wrapper gate once there is matching memory/candidate data | Turns the ChromaLink truth stream into actual candidate scoring evidence instead of just a plumbing proof |
| 9 | If touching ChromaLink again, run `dotnet test .\DesktopDotNet\ChromaLink.sln -v minimal` and `dotnet run --project .\DesktopDotNet\ChromaLink.Cli\ChromaLink.Cli.csproj -- validate` before commit | These are the repo's proven drift guards for protocol, reader, HTTP bridge, and schema behavior |
| 10 | In the new chat, read this handoff first and inspect only the files/commits named here before broad searching | Keeps the new session on the current proven path and avoids reopening stale PlayerCoords/SavedVariables/geometry theories |

## Ready-to-paste resume prompt for new chat

```text
Resume from handoff: C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-01-122706-chromalink-live-coords-resolved-handoff.md

Start by reading that file. Keep scope narrow.
Current truth: RiftReader main is clean at e3d51a0; ChromaLink main is clean and pushed at bf4c297. ChromaLink live coordinate capture was resolved by resizing RIFT to 640x360, adding playerPosition to ChromaLink normal/combat rotations, /reloadui, and using ChromaLink watch with --backend screen. Successful temp bundle: C:\Users\mrkoo\AppData\Local\Temp\RiftReader-real-chromalink-capture-f371fa20dbcc4e5f995a85b058fef867.

Continue with the next best action: make the standard ChromaLink stack/launcher path use --backend screen, validate it, then create a durable multi-sample RiftReader ChromaLink capture bundle. Ask before any live RIFT focus/resize/key/slash input unless I explicitly renew approval.
```
