# Reverse-engineering tool staging

This folder contains optional repo-local staging for the free external tools that currently add the most value to the `RiftReader` workflow:

- `ReClass.NET`
- `x64dbg`

The preferred x64dbg install for this machine is the external shared tools path:

```text
C:\RIFT MODDING\Tools\x64dbg
```

`scripts\open-x64dbg.cmd` checks that external path first, then falls back to
this repo-local ignored staging path.

## Install / refresh

```powershell
& 'C:\RIFT MODDING\RiftReader\tools\reverse-engineering\install-tools.ps1'
```

That script downloads the latest official releases from the upstream GitHub repositories and extracts them here.

Current verified local refresh:

| Tool | Version / snapshot | Local executable |
|---|---|---|
| x64dbg external | `2026.04.20` / `snapshot_2026-04-20_19-04.zip` | `C:\RIFT MODDING\Tools\x64dbg\release\x64\x64dbg.exe` |
| x64dbg repo-local fallback | `2026.04.20` / `snapshot_2026-04-20_19-04.zip` | `C:\RIFT MODDING\RiftReader\tools\reverse-engineering\x64dbg\release\x64\x64dbg.exe` |
| ReClass.NET | `v1.2` | `C:\RIFT MODDING\RiftReader\tools\reverse-engineering\ReClass.NET\x64\ReClass.NET.exe` |

## Launch

```powershell
& 'C:\RIFT MODDING\RiftReader\scripts\open-reclass.cmd'
```

```powershell
& 'C:\RIFT MODDING\RiftReader\scripts\open-x64dbg.cmd'
```

## Current useful starting point

Historical note: the address below is a stale sample-base lead, not current
movement truth. Revalidate any address against fresh API/runtime coordinates and
the current PID/HWND before using it.

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

For the current x64dbg safety and pointer-chain workflow, see:

- `docs/recovery/x64dbg-pointer-chain-workflow.md`
