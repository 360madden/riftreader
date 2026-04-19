---
name: rift-window-control
summary: Deprecated. The repo-local rift_game MCP workflow was removed on 2026-04-18 after it failed to provide reliable live movement control.
---

# Deprecated

Do not use this skill as an active workflow inside `C:\RIFT MODDING\RiftReader`.

## Why

| Reason | Detail |
|---|---|
| Removed dependency | The repo-local `rift_game` MCP package under `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp` was removed |
| Workflow correction | Live movement work was reset back to the existing helper-app/script lane |
| Current preferred path | `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`, `C:\RIFT MODDING\RiftReader\scripts\send-rift-key.ps1`, and higher-level scripts that already depend on them |

## Replacement

Prefer the existing helper-app scripts instead of MCP-mediated window tooling for live Rift movement/testing in this repo.
