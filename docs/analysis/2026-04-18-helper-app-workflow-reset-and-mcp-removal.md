---
state: current
as_of: 2026-04-18
---

# Helper-App Movement Workflow Reset and MCP Removal (2026-04-18)

## Decision

The active live-movement workflow has been reset back to the original **helper-app/script lane** and the repo-local `rift_game` MCP path is being removed.

## Why

| Reason | Evidence |
|---|---|
| The previously established movement path in this repo was helper-app driven | `C:\RIFT MODDING\RiftReader\scripts\smart-capture-player-family.ps1` already uses `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1` as its movement stimulus |
| The MCP path was a process drift from that baseline | `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1` had been expanded to try `WindowTools` before the existing helper scripts |
| The MCP path did not produce real in-game motion | live probes through `tools\rift-game-mcp\helpers\window-tools.ps1` produced zero coord delta for key-send and click probes |
| Keeping both lanes active made results harder to interpret | failures could no longer be attributed cleanly to the original helper-app workflow |

## Operational change

| Area | New state |
|---|---|
| Authoritative live stimulus lane | helper-app scripts only (`post-rift-key.ps1`, `send-rift-key.ps1`) |
| `trace-player-coord-write.ps1` auto stimulus order | `PostMessage`, then `SendInput` |
| Repo-local `rift_game` MCP package | removed |
| Repo-local Codex MCP registration for `rift_game` | removed |

## Removed path

The deleted non-working MCP path was:

- `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp`
- `C:\RIFT MODDING\RiftReader\.codex\config.toml` entry for `mcp_servers.rift_game`

## Scope note

This removal is a workflow simplification, not a claim that every MCP-style game integration is impossible in general. It is specifically a removal of the repo-local `rift_game` MCP path because it was not the established movement lane and did not produce reliable live motion in this investigation.
