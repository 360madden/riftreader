# Reverse-engineering tool staging

This folder contains repo-local staging for the free external tools that currently add the most value to the `RiftReader` workflow:

- `ReClass.NET`
- `x64dbg`

## Install / refresh

```powershell
C:\RIFT MODDING\RiftReader\tools\reverse-engineering\install-tools.ps1
```

That script downloads the latest official releases from the upstream GitHub repositories and extracts them here.

## Launch

```powershell
C:\RIFT MODDING\RiftReader\scripts\open-reclass.cmd
```

```powershell
C:\RIFT MODDING\RiftReader\scripts\open-x64dbg.cmd
```

## Current useful starting point

Do **not** assume any hardcoded sample base address in this repo is still valid.
The player-family and coord-write addresses are session-specific and can drift
between launches or even between refresh passes.

Use the live artifacts first:

- `C:\RIFT MODDING\RiftReader\scripts\captures\ce-smart-player-family.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-source-chain.json`

Recommended workflow:

1. Refresh the latest ReaderBridge export.
2. Regenerate the coord trace / source-chain artifacts for the current process.
3. Open the resulting live base addresses in `ReClass.NET`.
4. Use `x64dbg` or Cheat Engine only after confirming the current process still
   matches the generated artifacts.
