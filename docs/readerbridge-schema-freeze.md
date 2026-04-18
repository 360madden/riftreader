# ReaderBridge export schema freeze

## Status

| Item | Value |
|---|---|
| Schema version | `1` |
| Frozen in addon | `C:\RIFT MODDING\RiftReader\addon\ReaderBridgeExport\main.lua` |
| Golden fixture | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\AddonSnapshots\Fixtures\ReaderBridgeExport.frozen.lua` |
| Thin real export fixture | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\AddonSnapshots\Fixtures\ReaderBridgeExport.thin-live.lua` |
| Loader regression tests | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\AddonSnapshots\ReaderBridgeSnapshotLoaderTests.cs` |
| Parse smoke command | `C:\RIFT MODDING\RiftReader\scripts\smoke-readerbridge-export.ps1` |

## Freeze rule

| Rule | Why |
|---|---|
| Do not change the ReaderBridge export shape casually | loader and formatter stability now depend on the frozen contract |
| Any schema change must update the fixture and tests in the same patch | prevents silent drift |
| Keep list-like exports as tables, not `nil` | avoids brittle consumer behavior |
| Validate with the smoke script after addon-side edits | catches parse breakage quickly |

## Minimum validation

| Step | Command |
|---|---|
| Lua syntax | `cmd /c "C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd"` |
| Build | `dotnet build "C:\RIFT MODDING\RiftReader\RiftReader.slnx"` |
| Tests | `dotnet test "C:\RIFT MODDING\RiftReader\RiftReader.slnx" --no-build` |
| Frozen fixture parse | `pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\smoke-readerbridge-export.ps1" -SnapshotFile "C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\AddonSnapshots\Fixtures\ReaderBridgeExport.frozen.lua" -Json -NoBuild` |
| Current export parse | `pwsh -NoProfile -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\smoke-readerbridge-export.ps1" -Json -NoBuild` |
