# Compact handoff — Non-Codex ChatGPT MCP development resume

Generated: `2026-06-07T18:42:13-04:00` (`2026-06-07T22:42:13Z`)
Refreshed: `2026-06-07T19:02:42-04:00` (`2026-06-07T23:02:42Z`)

## Resume objective

Continue RiftReader **non-Codex ChatGPT Web/Desktop MCP** development from the
current canonical route and proof state. This handoff is for a new ChatGPT
Web/Desktop chat, not for ChatGPT Codex.

## Current canonical route

```text
ChatGPT Web/Desktop Developer Mode
-> https://mcp.360madden.com/mcp
-> Cloudflare proxied DNS
-> Cloudflare Tunnel riftreader-mcp-360madden
-> cloudflared Windows service on this PC
-> http://127.0.0.1:8770/mcp
-> scripts\riftreader-chatgpt-mcp.cmd
-> C:\RIFT MODDING\RiftReader
```

## Hard route policy

| Path | Status |
|---|---|
| Persistent Cloudflare named Tunnel `riftreader-mcp-360madden` | **Canonical** |
| ChatGPT Server URL `https://mcp.360madden.com/mcp` | **Canonical** |
| ChatGPT auth | **No Authentication** |
| Local adapter port | `127.0.0.1:8770` |
| Caddy/router/direct-public-IP route | **Deprecated legacy; do not recreate as fallback** |
| `trycloudflare.com` quick tunnel | Retired; not a backup |
| OpenAI Secure MCP Tunnel | Retired for this lane unless explicitly reauthorized |
| ChatGPT Codex | Out of scope for this MCP proof lane |

## Current repo state

| Item | Current value |
|---|---|
| Branch | `main` |
| HEAD | `bf47e7e Deprecate Caddy route for canonical Cloudflare tunnel` |
| Worktree before this handoff | Clean before creating this file; this file should be committed to make the handoff durable. |
| New handoff file | This file |
| Canonical docs | `docs\workflow\riftreader-chatgpt-mcp.md`, `docs\workflow\non-codex-desktop-chatgpt-workflow.md`, `docs\cloudflare-tunnel-360madden.md` |
| Canonical adapter wrapper | `scripts\riftreader-chatgpt-mcp.cmd` |
| Domain diagnostics wrapper | `scripts\riftreader-mcp-domain-diagnostics.cmd` |

## Last known validated state

| Check | Result |
|---|---|
| Public MCP domain smoke | Passed at `2026-06-07T23:02:12Z` |
| Public HTTP status | `200` |
| MCP server identity | `serverInfo.name=riftreader_chatgpt_mcp`, version `1.27.1` |
| Latest public diagnostic artifact | `.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics\20260607-230211Z\summary.json` |
| Adapter self-test | Passed |
| SDK validation | Passed |
| Targeted unit docs/diagnostics/adapter tests | Passed: 76 tests |
| Fresh Phase 0 proof template | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-230242Z\proof-input.json` |
| Cloudflared Windows service | Running. |
| Legacy Caddy listener | Present on local TCP 443 as `caddy.exe`, but diagnostics report `activeRouteUsesCaddy=false`; do not use it for this lane. |

## Exact safe resume commands

Use CMD/Python-first commands. Run from a normal operator-owned terminal, not a
Codex terminal, when proving non-Codex operation.

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
git status --short --branch
scripts\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json
scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json
scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json
```

Operator-owned serve command for actual ChatGPT Web/Desktop proof:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-mcp.cmd --serve --tool-profile public-read-only --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com
```

ChatGPT app setup:

| Field | Value |
|---|---|
| App name | `rift-mcp` |
| Server URL | `https://mcp.360madden.com/mcp` |
| Authentication | `No Authentication` |

## Legacy Caddy/router note

Current diagnostics may still show a local `caddy.exe` listener on TCP 443 from
the retired route. That is **not** the active MCP path. Treat Caddy/Caddyfile
outputs as legacy compatibility evidence only unless a future cleanup task
explicitly removes or disables the old service after dependency review.

## Phase 0 read-only proof still needed

Record an actual ChatGPT Web/Desktop proof only after ChatGPT itself confirms:

1. app exists in Developer Mode;
2. Server URL is `https://mcp.360madden.com/mcp`;
3. Authentication is `No Authentication`;
4. visible tool list is read-only proof surface only;
5. `health` call succeeds;
6. `get_repo_status` call succeeds;
7. `get_latest_handoff` or `get_workflow_control_summary` succeeds;
8. output redacts absolute repo root.

Proof template command:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --proof-mode domain-read-only --json
```

## Safety boundaries

Do not expose or add MCP tools for shell, arbitrary filesystem, Git mutation,
RIFT input, target control, Cheat Engine, x64dbg, tunnel control, or broad local
MCP proxying. The public first proof remains read-only and narrow.

## Recommended next action

Create/refresh the actual ChatGPT Web/Desktop Developer Mode app using
`https://mcp.360madden.com/mcp`, call the read-only proof tools from ChatGPT,
then record the Phase 0 domain read-only proof packet.
