# RiftReader waypoint-discovery live handoff

Created: 2026-04-30 09:58:54 America/New_York  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Status: `main...origin/main [ahead 1]` plus uncommitted waypoint/telemetry fixes

## TL;DR

Waypoint coordinate discovery is no longer the primary blocker. The current
proof coord anchor was re-acquired and normalized successfully, telemetry can
read memory coords, and a proof-anchor-first smoke route can be generated.

The remaining blocker is actor-facing. The behavior-backed lead at
`0X216FE3C6280 @ 0XD4` is stale/unreadable in the live process, and live
rediscovery did not produce a promotable behavior-backed replacement. Owner
component fallback can produce an orientation sample and route, but it should be
treated as fallback/candidate unless separately promoted.

No route-navigation movement run was executed in the final validated slice.
Live helper work did include `/reloadui`, proof-anchor key stimulus, actor-facing
stimulus attempts, and short owner/coord refresh pulses.

## Current live target from this handoff

These are session-specific and must be rediscovered after a restart.

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `41220` |
| HWND | `0xBD0D94` |
| Title | `RIFT` |
| Character | `Atank` |
| Location | `Sanctum Watch` |
| Evidence root | `C:\RIFT MODDING\RiftReader\scripts\captures\waypoint-discovery-live-20260429-212204` |

## Current proof coord truth

Latest normalized proof coord cache:

`C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`

Key values:

| Field | Value |
|---|---|
| `GeneratedAtUtc` | `2026-04-30T02:09:36.7701158+00:00` |
| `CanonicalCoordSourceKind` | `coord-trace-source-object` |
| `MatchSource` | `readerbridge-live` |
| `ObjectBaseAddress` | `0x216F2F26020` |
| `CoordRegionAddress` | `0x216F2F26068` |
| `CoordXRelativeOffset` | `0` |
| `CoordYRelativeOffset` | `4` |
| `CoordZRelativeOffset` | `8` |
| `MemorySample` | `7237.62, 873.4722, 3051.0586` |
| ReaderBridge expected | `7237.6196289062, 873.46997070312, 3051.0598144531` |
| Delta | `0.00048828125, 0.0022583008, -0.0012207031` |

Important fix: `resolve-proof-coord-anchor.ps1` previously emitted non-zero
source-object offsets with `CoordRegionAddress` already shifted. That made some
readers double-add the offset and read garbage/zeroes. The script now normalizes
the selected coord region so the region address points directly at the 12-byte
XYZ triplet and the relative offsets are `0/4/8`.

## Current ReaderBridge truth

Latest live refresh evidence:

`C:\RIFT MODDING\RiftReader\scripts\captures\waypoint-discovery-live-20260429-212204\refresh-readerbridge-after-w-pulse-20260429-2212.stdout.txt`

Current ReaderBridge coords at that point:

```text
X = 7237.6196289062
Y = 873.46997070312
Z = 3051.0598144531
```

## Current telemetry truth

Latest live preflight:

`C:\RIFT MODDING\RiftReader\scripts\captures\waypoint-discovery-live-20260429-212204\telemetry-preflight-after-normalized-anchor-cache-20260429-2219.stdout.txt`

Result:

| Check | Value |
|---|---|
| `MemoryCoordAvailable` | `true` |
| `MemoryCoordValid` | `true` |
| `EffectivePositionSource` | `memory` |
| `MemoryFacingAvailable` | `true` |
| `FacingValid` | `false` |
| `EffectiveFacingSource` | `none` |

Telemetry position is now usable from memory. Telemetry facing still fails
because the behavior-backed lead address is unreadable.

## Generated route / read-only navigation check

Generated smoke route:

`C:\RIFT MODDING\RiftReader\scripts\captures\waypoint-discovery-live-20260429-212204\proof-anchor-owner-fallback-smoke-waypoints-20260429-2222.json`

Generation output:

`C:\RIFT MODDING\RiftReader\scripts\captures\waypoint-discovery-live-20260429-212204\new-forward-smoke-route-owner-fallback-20260429-2222.stdout.txt`

Read-only navigation current check:

`C:\RIFT MODDING\RiftReader\scripts\captures\waypoint-discovery-live-20260429-212204\read-navigation-current-owner-fallback-route-20260429-2222.stdout.txt`

Key result:

| Field | Value |
|---|---|
| `AnchorSource` | `coord-trace-anchor` |
| `CurrentAddressHex` | `0x216F2F26068` |
| `CurrentPosition` | `7237.6201171875, 873.4722290039062, 3051.05859375` |
| `DestinationPosition` | `7240.219132459354, 873.4722290039062, 3051.1301452466387` |
| `PlanarDistance` | `2.600000000000413` |
| `WithinArrivalRadius` | `false` |
| `Facing.Status` | `read-failed` |

This proves route generation and read-only coord/path projection now work, but
it does not prove live movement or actor-facing alignment.

## Actor-facing status

Behavior-backed lead:

`C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`

Current status:

| Item | Status |
|---|---|
| Lead source | `0X216FE3C6280` |
| Basis offset | `0XD4` |
| Read result | Failed, Win32 `299` |
| Telemetry facing | Invalid |
| Route generation with normal behavior-backed lead | Fails |

Live actor-facing rediscovery attempts:

| Evidence | Result |
|---|---|
| `refresh-actor-facing-discovery-20260429-2135.stdout.txt` | AutoHotkey attempt failed because foreground was Codex before first stimulus |
| `refresh-actor-facing-discovery-postmessage-20260429-2140.stdout.txt` | Completed but no promotable candidate |
| `refresh-actor-facing-discovery-ahk-focused-20260429-2147.stdout.txt` | Completed but no promotable candidate |
| `actor-yaw-validation-right-left-20260429-2157.json` | `TruthLikeCandidateCount=0` |

Owner-component fallback orientation can be read after the patch:

`C:\RIFT MODDING\RiftReader\scripts\captures\waypoint-discovery-live-20260429-212204\capture-actor-orientation-ignore-lead-current-anchor-20260429-2220.stdout.txt`

Fallback sample:

| Field | Value |
|---|---|
| Selected source | `0x216F2F26020` |
| Basis | `Basis60.Forward` |
| Basis offset | `0x60` |
| Yaw | `88.42303214749626` degrees |
| Coord match | Live source coords matched current ReaderBridge coords |

Treat that as a fallback/candidate, not as a promoted behavior-backed lead.

## Code changes currently uncommitted

| File | Purpose |
|---|---|
| `reader/RiftReader.Reader/Telemetry/TelemetrySources.cs` | Read proof cache even when stale-aged, then validate live memory coords against ReaderBridge before publishing memory coords. Rejects mismatched anchors. |
| `scripts/resolve-proof-coord-anchor.ps1` | Normalizes coord-region address and offsets for non-zero source-object coord selections. |
| `scripts/navigation/new-forward-smoke-route.ps1` | Generates start coords from validated proof coord memory reads instead of ReaderBridge-only / resolver skip-refresh; added `-IgnoreBehaviorBackedLead` fallback path. |
| `scripts/capture-actor-orientation.ps1` | Fixes `-IgnoreBehaviorBackedLead` so artifact/owner-component fallback does not still force live behavior-backed lead mode. |

Git status at handoff creation:

```text
## main...origin/main [ahead 1]
 M reader/RiftReader.Reader/Telemetry/TelemetrySources.cs
 M scripts/capture-actor-orientation.ps1
 M scripts/navigation/new-forward-smoke-route.ps1
 M scripts/resolve-proof-coord-anchor.ps1
```

Local unpushed commit already on `main` before these edits:

```text
70a80a6 Add exact-target propagation regression tests
```

## Validation already run

| Command | Result |
|---|---|
| PowerShell parse checks for edited scripts | Passed |
| `dotnet build .\RiftReader.slnx` | Passed |
| `dotnet test reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --filter "FullyQualifiedName~Telemetry"` | Passed, `11/11` |
| `scripts\navigation\test-navigation-proof-suite.ps1` | Passed |
| `scripts\test-actor-facing-proof-suite.ps1` | Passed |
| `git diff --check` | Passed; only CRLF conversion warnings |
| Live telemetry preflight | Coord valid; facing invalid |
| Live `read-navigation-current` for generated route | Coord/path valid; facing invalid |

## Known blockers / risks

1. Behavior-backed actor-facing is stale and unreadable.
2. The owner-component fallback route generation is useful, but not yet a
   replacement for promoted behavior-backed actor-facing.
3. `read-navigation-current` still reports facing failed because core
   navigation-facing summary reads only the behavior-backed lead.
4. Route movement has not been run after these fixes.
5. The exact live PID/HWND values are session-local and must be rediscovered
   after any Rift restart.

## Resume commands

Rediscover target first:

```powershell
Get-Process -Name rift_x64 | Where-Object { $_.MainWindowHandle -ne 0 } |
  Select-Object Id,ProcessName,MainWindowHandle,MainWindowTitle,StartTime
```

Check proof coord anchor:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\resolve-proof-coord-anchor.ps1 `
  -ProcessId <PID> -TargetWindowHandle <HWND_HEX> -SkipRefresh -RefreshAttempts 0 -Json
```

If stale/mismatched, reacquire proof coord anchor:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\resolve-proof-coord-anchor.ps1 `
  -ProcessId <PID> -TargetWindowHandle <HWND_HEX> -RefreshAttempts 2 -Json
```

Run telemetry preflight:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --pid <PID> `
  --telemetry-preflight `
  --telemetry-proof-anchor-file .\scripts\captures\telemetry-proof-coord-anchor.json `
  --telemetry-diagnostics `
  --json
```

Generate owner-component-fallback route without using the stale behavior-backed
lead:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\navigation\new-forward-smoke-route.ps1 `
  -ProcessId <PID> `
  -TargetWindowHandle <HWND_HEX> `
  -SkipRefresh `
  -IgnoreBehaviorBackedLead `
  -WaypointFile .\scripts\navigation\smoke-test-waypoints.json
```

Read-only navigation current check:

```powershell
dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --pid <PID> `
  --read-navigation-current `
  --destination-waypoint smoke_destination `
  --navigation-waypoint-file .\scripts\navigation\smoke-test-waypoints.json `
  --scan-context 192 `
  --max-hits 12 `
  --arrival-radius 2.1 `
  --json
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Add a regression test for normalized non-zero proof coord offsets. | Prevents the critical `CoordRegionAddress + offset` double-add bug from returning. |
| 2 | Decide whether to commit the four-file coord/fallback fix as-is. | Coord waypoint discovery is materially better and validated. |
| 3 | Keep behavior-backed lead disabled/ignored for route generation until replaced. | `0X216FE3C6280 @ 0XD4` is unreadable and should not gate route generation. |
| 4 | Rework actor-facing rediscovery around `0x216F2F26020` and nearby basis fields. | That source currently matches player coords and exposes a usable fallback basis. |
| 5 | Add a read-only navigation-facing fallback mode or explicit warning path. | `read-navigation-current` still only reports behavior-backed facing, even when owner fallback generated the route. |
| 6 | Refresh ReaderBridge before each proof/route check. | Addon coords are used as the live validation reference for proof-cache acceptance. |
| 7 | Keep route movement deferred until coord and facing readiness are both green or explicitly bypassed. | Prevents confusing movement failures caused by facing truth, not waypoint coords. |
| 8 | Preserve the evidence root with this handoff. | The live artifacts capture the update regression and the recovered proof source. |
| 9 | After actor-facing is fixed, rerun telemetry preflight and route read-only checks. | Need `MemoryCoordValid=true` and `FacingValid=true` before real auto-turn proof. |
| 10 | Only then run a short live movement smoke with exact PID/HWND. | Avoids stale-window or stale-anchor input risk. |


## Continuation update — 2026-04-30 10:13:19 -04:00

Additional offline hardening completed after the original handoff:

| Area | Change |
|---|---|
| Proof coord regression | Added scripts/test-resolve-proof-coord-anchor-normalization.ps1 to prove source-object coord selections are persisted with CoordRegionAddress shifted to the XYZ triplet and offsets normalized to  /4/8. |
| Navigation proof suite | Wired the new normalization regression into scripts/navigation/test-navigation-proof-suite.ps1. |
| Read-only navigation facing | Updated --read-navigation-current to keep canonical behavior-backed facing unchanged, but when that path is unavailable it can report owner-component artifact orientation as allback-candidate / owner-components-artifact-candidate-facing. This is report-only and not actionable turn truth. |
| Safety guard | Added tests proving fallback-candidate facing is not accepted by NavigationMath.BuildTurnPlan as actionable movement/turn input. |

Additional validation run:

| Command | Result |
|---|---|
| pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-resolve-proof-coord-anchor-normalization.ps1 | Passed |
| dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --filter "FullyQualifiedName~NavigationMathTests" | Passed, 7/7 |
| dotnet build .\RiftReader.slnx | Passed |
| pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\navigation\test-navigation-proof-suite.ps1 | Passed |
| dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --filter "FullyQualifiedName~Telemetry" | Passed, 11/11 |
| git diff --check | Passed; only CRLF conversion warnings |

Updated working tree additions since the original handoff:

| File | Purpose |
|---|---|
| eader/RiftReader.Reader/Program.cs | Read-only navigation now attempts owner-component artifact candidate reporting only after behavior-backed facing is unavailable. |
| eader/RiftReader.Reader/Navigation/NavigationMath.cs | Added candidate-facing summary builder that preserves non-actionable status. |
| eader/RiftReader.Reader.Tests/Navigation/WaypointNavigationTests.cs | Added candidate-facing and turn-plan safety tests. |
| scripts/test-resolve-proof-coord-anchor-normalization.ps1 | New deterministic offline resolver normalization regression. |
| scripts/navigation/test-navigation-proof-suite.ps1 | Runs the new normalization regression in the non-live navigation proof gate. |
