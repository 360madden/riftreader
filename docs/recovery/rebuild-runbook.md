# Rebuild Runbook

Use this order when you need to reconstruct the active state.

If you need the **detailed fast live-discovery method** that recovered actor yaw
quickly, use:

- `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-workflow.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-prompt.json`

This file is the reusable backup workflow for future live recovery/discovery of
other features that depend on focus-enforced input plus live memory readback.

The JSON packet is the machine-readable companion for the same workflow and is
the preferred starting packet when an AI needs to rerun or adapt the method
without re-deriving the full recovery ladder from scratch.

## 0. After a game update, triage the surviving baselines first

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --readerbridge-snapshot --json
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-coord-anchor --json
```

Expected during the current post-update state:

- ReaderBridge snapshot should still load
- player-current should still match ReaderBridge
- coord-anchor should still find the module-local pattern, even if the absolute
  instruction address changed

If these fail, stop and fix the reader baseline before trusting any
owner/source/camera artifact.

## 1. Build the repo

```powershell
dotnet build C:\RIFT MODDING\RiftReader\RiftReader.slnx
```

## 2. For actor yaw / pitch recovery, probe the addon/API layer first

Use the addon path before returning to the old owner/source recovery chain:

```powershell
C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd
C:\RIFT MODDING\RiftReader\scripts\sync-addon.cmd
```

Then, in-game:

- `/rap orientation`
- optionally `/rbx export`, then inspect `ReaderBridgeExport.lua`

Then, out-of-game, summarize the latest exported orientation candidates:

```powershell
C:\RIFT MODDING\RiftReader\scripts\inspect-readerbridge-orientation.cmd
```

If you capture a before/after pair around a live turn or pitch stimulus,
compare them directly:

```powershell
C:\RIFT MODDING\RiftReader\scripts\compare-readerbridge-orientation-probes.cmd `
  C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-orientation-probe-baseline.json `
  C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-orientation-probe-after.json
```

Resume criteria:

- if the addon/API layer exposes a usable heading / pitch / facing signal, keep
  the actor-orientation recovery focused there first
- only if the addon layer yields no strong orientation candidate should the
  workflow drop back to external rediscovery

Reference:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-actor-orientation-stop-point-and-resume-plan.md`

## 2.5 Reintegrate CE in scan / inspection mode before debugger-trace mode

Bring CE back as the interactive discovery workbench first, not as the default
debugger-attach lane.

Use this mode for:

- grouped family inspection
- changed/unchanged narrowing
- address-list validation
- quick manual structure inspection

Reference:

- `C:\RIFT MODDING\RiftReader\docs\cheat-engine-workflow.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-cheat-engine-reintegration-and-attach-failure-plan.md`

## 3. Attempt to rebuild the owner/source chain

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1 -Json -RefreshCluster
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1 -Json -RefreshSelectorTrace
```

Healthy result:

- `player-source-chain.json`
- `player-selector-owner-trace.json`
- `player-owner-components.json`

Current post-update warning:

- if `capture-player-source-chain.ps1` cannot locate the required
  source-container load, stop and mark the actor/camera chain stale
- if `trace-player-selector-owner.ps1` remains `armed` without a hit, stop and
  mark the actor/camera chain stale
- if CE throws `Error attaching the windows debugger: 87`, stop the
  debugger-trace attempt, log the run, and do **not** patch the Lua attach
  guards until that failure is repeated across multiple fresh runs

Current trace scripts append that attach failure to
`C:\RIFT MODDING\RiftReader\scripts\captures\ce-debugger-attach-failures.csv`
by default unless `-SkipAttachFailureLedger` is used.

Do not promote stale owner/source artifacts as current truth.

## 4. Refresh the core graph artifacts

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1 -Json -RefreshSelectorTrace
C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1 -Json -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1 -Json
```

Run this step only after step 3 succeeds on the current game build.

## 5. Verify the live camera read path

```powershell
C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1 -Json
```

Expected:
- yaw = direct
- pitch = derived
- distance = derived

Current post-update note:

- the active live camera scripts currently live on
  `feature/camera-orientation-discovery`, not on the `main` worktree
- do not treat older camera outputs as current until this step succeeds on the
  updated client

## 6. Rebuild controller-search helpers if needed

```powershell
C:\RIFT MODDING\RiftReader_camera_feature\scripts\search-camera-global.ps1 -Json -RefreshOwnerGraph -RefreshHubGraph -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader_camera_feature\scripts\generate-camera-probe.ps1 -Json
C:\RIFT MODDING\RiftReader_camera_feature\scripts\capture-camera-memory-dump.ps1 -Json
```

## Missing-file shortcuts

- missing actor yaw / pitch direction after an update -> do step 2
- missing `player-owner-components.json` -> do step 3
- missing `player-owner-graph.json` or `player-stat-hub-graph.json` -> do step 4
- missing camera helper outputs -> do steps 5 and 6
- missing old notes -> rebuild the current state first, then compare history later

## Operator note

`refresh-readerbridge-export.ps1` may use UI-intrusive chat/reload helper
behavior. Prefer an already-fresh ReaderBridge export when possible, and do not
use chat/reload helpers for unattended live camera probing unless that
disruption is explicitly acceptable.
