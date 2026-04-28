# Cheat Engine table note - 2026-04-22 22:05 America/New_York

| Item | Value |
|---|---|
| Table file | `C:\RIFT MODDING\RiftReader\artifacts\cheat-engine\tables\2026-04-22-2205-ce-live-proof-recheck.ct` |
| Branch | `navigation` |
| Commit | `c565339` |
| Target process | `rift_x64.exe` |
| Target PID | `63012` |
| Capture purpose | Preserve the live CE state after confirming the repo's preferred coord-proof path was working again with debugger-backed breakpoints |

## What this table proves

- Cheat Engine was reachable through the `RiftReader` Lua pipe on this session.
- The repo-owned probe/bootstrap path was working again.
- A focused coord-trace health check succeeded on the current process using:
  - `BreakpointMethod=debug-register`
  - `WatchMode=access`
  - `BreakpointSize=12`
- The live health-check trace hit the current coord region and produced:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\ce-health-check-trace.json`
  - `C:\RIFT MODDING\RiftReader\scripts\captures\ce-health-check-trace.status.txt`

## What is still tentative

- Manual VEH/page-exception debugging is not promoted by this snapshot; that
  path previously raised a `VEH Debug error` access-violation popup.
- The full `resolve-proof-coord-anchor.ps1` reacquisition path was still less
  stable than the direct/narrow CE health-check trace in this pass.
- Any actor-facing candidate records in the CE session remain exploratory unless
  they are revalidated through the current repo workflows.

## Dependent repo artifacts / scripts

- `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\export-proof-polling-watchset.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\captures\ce-health-check-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\proof-polling-watchset.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`
