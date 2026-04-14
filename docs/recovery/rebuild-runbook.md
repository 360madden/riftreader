# Rebuild Runbook

Use this when a key artifact, helper script, or workflow note is corrupted and you need to reconstruct the active state.

## Goal

Rebuild the smallest trustworthy state in this order:
1. reader works
2. owner/source chain is current
3. graph artifacts are current
4. camera read path is current
5. controller-search evidence is current

## Step 0 - Verify the codebase

```powershell
dotnet build C:\RIFT MODDING\RiftReader\RiftReader.slnx
```

If build fails, stop and fix the reader before trusting any downstream artifacts.

## Step 1 - Verify the low-level reader quickly

Use at least one harmless reader smoke check:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --list-modules --json
```

Optional targeted read if you already have a current trusted address:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --address 0x1 --length 1 --json
```

The point is to confirm the reader can attach and report cleanly, not to decode anything yet.

## Step 2 - Rebuild the current owner/source chain

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1 -Json -RefreshSelectorTrace
```

This should regenerate:
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json`

If this step fails, stop. The rest of the rebuild depends on a current owner/source chain.

## Step 3 - Rebuild the current graph artifacts

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1 -Json -RefreshSelectorTrace
C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1 -Json -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1 -Json
```

This should give you the minimum current graph set:
- `player-owner-graph.json`
- `player-stat-hub-graph.json`
- a consistency report that tells you whether the chain is aligned

If consistency is bad, refresh again before moving on.

## Step 4 - Rebuild the current camera read state

```powershell
C:\RIFT MODDING\RiftReader\scripts\read-live-camera-yaw-pitch.ps1 -Json
```

Expected state:
- yaw is direct
- pitch is derived
- distance is derived

If this fails, do not trust older camera docs or stale captures. Re-check Step 2 and Step 3 first.

## Step 5 - Rebuild controller-search evidence

```powershell
C:\RIFT MODDING\RiftReader\scripts\search-camera-global.ps1 -Json -RefreshOwnerGraph -RefreshHubGraph -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader\scripts\generate-camera-probe.ps1 -Json
C:\RIFT MODDING\RiftReader\scripts\capture-camera-memory-dump.ps1 -Json
```

This regenerates the current search summary plus the current watch/probe helpers around the live anchors.

## Step 6 - Optional preservation pass

If the rebuild produced a good state, freeze it into repo-owned artifacts:

```powershell
C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.ps1
```

And update these docs if the truth changed materially:
- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\camera-orientation-discovery.md`

## If a specific artifact is missing

### Missing `player-owner-components.json`
Rebuild from Step 2.

### Missing `player-owner-graph.json`
Rebuild Step 3 after Step 2 succeeds.

### Missing `player-stat-hub-graph.json`
Rebuild Step 3 after Step 2 succeeds.

### Missing camera helper outputs
Re-run Step 4 and Step 5.

### Missing historical docs
Do not guess. Rebuild current truth from this runbook and regenerate the active state first.
