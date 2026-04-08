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

Latest CE-confirmed player sample base:

- `0x144A849A8C0`

Current confirmed relative layout:

- `+0` = `coord.x`
- `+4` = `coord.y`
- `+8` = `coord.z`
- `-144` = `level`
- `-136` = `health[1]`
- `-128` = `health[2]`
- `-120` = `health[3]`

Use `ReClass.NET` to model the structure around that base address, and use `x64dbg` to trace what reads/writes those fields.
