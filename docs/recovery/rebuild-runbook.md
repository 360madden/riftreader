# Rebuild Runbook

Use this order when you need to reconstruct the active state.

## 1. Build the repo

```powershell
dotnet build C:\RIFT MODDING\RiftReader\RiftReader.slnx
```

## 2. Refresh the owner/source chain

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1 -Json -RefreshSelectorTrace
```

This should refresh:
- `player-selector-owner-trace.json`
- `player-owner-components.json`

## 3. Refresh the core graph artifacts

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1 -Json -RefreshSelectorTrace
C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1 -Json -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1 -Json
```

## 4. Verify the live camera read path

```powershell
C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1 -Json
```

Expected:
- yaw = direct
- pitch = derived
- distance = derived

## 5. Rebuild controller-search helpers if needed

```powershell
C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1 -Json -RefreshOwnerGraph -RefreshHubGraph -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader\scripts\generate-camera-probe.ps1 -Json
C:\RIFT MODDING\RiftReader\scripts\capture-camera-memory-dump.ps1 -Json
```

## Missing-file shortcuts

- missing `player-owner-components.json` -> do step 2
- missing `player-owner-graph.json` or `player-stat-hub-graph.json` -> do step 3
- missing camera helper outputs -> do steps 4 and 5
- missing old notes -> rebuild the current state first, then compare history later
