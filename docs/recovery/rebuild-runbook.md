# Rebuild Runbook

Use this order when you need to reconstruct the active state.

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

## 2. Attempt to rebuild the owner/source chain

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

Do not promote stale owner/source artifacts as current truth.

## 3. Refresh the core graph artifacts

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1 -Json -RefreshSelectorTrace
C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1 -Json -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1 -Json
```

Run this step only after step 2 succeeds on the current game build.

## 4. Verify the live camera read path

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

## 5. Rebuild controller-search helpers if needed

```powershell
C:\RIFT MODDING\RiftReader_camera_feature\scripts\search-camera-global.ps1 -Json -RefreshOwnerGraph -RefreshHubGraph -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader_camera_feature\scripts\generate-camera-probe.ps1 -Json
C:\RIFT MODDING\RiftReader_camera_feature\scripts\capture-camera-memory-dump.ps1 -Json
```

## Missing-file shortcuts

- missing `player-owner-components.json` -> do step 2
- missing `player-owner-graph.json` or `player-stat-hub-graph.json` -> do step 3
- missing camera helper outputs -> do steps 4 and 5
- missing old notes -> rebuild the current state first, then compare history later

## Operator note

`refresh-readerbridge-export.ps1` may use UI-intrusive chat/reload helper
behavior. Prefer an already-fresh ReaderBridge export when possible, and do not
use chat/reload helpers for unattended live camera probing unless that
disruption is explicitly acceptable.
