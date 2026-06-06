# ChatGPT Web/Desktop MCP via OpenAI Secure MCP Tunnel

Use this as the preferred ChatGPT Web/Desktop path for local RiftReader repo
access:

```text
ChatGPT Web/Desktop
  -> OpenAI Secure MCP Tunnel
  -> tunnel-client on this Windows PC
  -> http://127.0.0.1:8765/mcp
  -> C:\RIFT MODDING\RiftReader
```

This is preferred over the public Cloudflare hostname when available because the
local MCP server does not need to be directly exposed to the public internet.
The existing `https://mcp.360madden.com/mcp` route remains a public fallback and
diagnostic path.

Official documentation checked:

| Source | Relevant point |
|---|---|
| OpenAI Developer mode docs | ChatGPT developer mode creates apps from remote MCP servers, supports SSE and streaming HTTP, and no longer requires `search`/`fetch` for developer-mode tools. |
| OpenAI Secure MCP Tunnel docs | For a developer machine/private network MCP server, use Secure MCP Tunnel so ChatGPT connects through an outbound tunnel instead of a public listener. |
| MCP 2025-06-18 spec | Tool definitions can include `outputSchema`; tool results can include `structuredContent` plus `content` for compatibility. |
| MCP 2025-06-18 transport spec | Streamable HTTP clients should send `MCP-Protocol-Version`; local servers should validate `Origin` to defend against DNS rebinding. |

## Local tools exposed

Only these read-only tools are exposed by default:

| Tool | Purpose |
|---|---|
| `health` | Verify server health and safety boundaries. |
| `get_repo_status` | Read branch, HEAD, dirty state, and changed-file names. |
| `get_latest_handoff` | Read the newest bounded handoff/status packet from known locations only. |

No arbitrary file read, write, shell, stage, commit, push, RIFT input,
x64dbg/Cheat Engine, or Cloudflare mutation tool is exposed.

## Transport hardening

The local server is intentionally conservative:

| Control | Behavior |
|---|---|
| Bind address | `127.0.0.1` only by default. |
| Auth | Bearer token required for `/health` and `/mcp`. |
| Origin validation | Requests with an `Origin` header are allowed only from ChatGPT/OpenAI origins or loopback origins. |
| DNS rebinding defense | Unknown browser origins are rejected with `origin_rejected`. |
| MCP protocol header | Responses include `MCP-Protocol-Version: 2025-06-18`; unsupported request versions are rejected. |
| CORS | No wildcard `Access-Control-Allow-Origin`; allowed origins are echoed only when trusted. |
| Adapter identity | `health` and `initialize` identify this lane as `chatgpt-web-desktop-http`, not the Codex/stdio adapter. |
| Output shape | Tool calls return both `structuredContent` and text `content`. |

## Prerequisites

| Requirement | Source |
|---|---|
| Local MCP server running | `scripts\start_mcp_local_background.cmd` |
| `tunnel-client` installed | OpenAI Platform Tunnels page or `openai/tunnel-client` release |
| `CONTROL_PLANE_TUNNEL_ID` | OpenAI Platform Tunnels management |
| `CONTROL_PLANE_API_KEY` | Runtime API key with Tunnels Read + Use |

Do not use an admin key for the long-running tunnel daemon. Admin keys are only
for tunnel CRUD workflows.

## RUN THIS — readiness flow

From `C:\RIFT MODDING\RiftReader`:

```cmd
scripts\start_mcp_local_background.cmd
scripts\prepare_chatgpt_mcp_tunnel_profile.cmd
scripts\check_chatgpt_mcp_tunnel_readiness.cmd
```

Expected when credentials/binary are not configured yet:

```text
BLOCKED: ChatGPT MCP tunnel setup is missing one or more prerequisites
END_RIFTREADER_CHATGPT_MCP_TUNNEL_READINESS_CMD
```

That is safe: it means the local repo/server slice is prepared, but the OpenAI
tunnel runtime inputs still need to be provided.

## RUN THIS — once tunnel credentials exist

Use a fresh operator shell:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
set CONTROL_PLANE_TUNNEL_ID=tunnel_0123456789abcdef0123456789abcdef
set CONTROL_PLANE_API_KEY=<runtime key with Tunnels Read + Use>
scripts\prepare_chatgpt_mcp_tunnel_profile.cmd
tunnel-client doctor --profile-file ".riftreader-local\mcp\openai-tunnel\riftreader-chatgpt.yaml" --explain
tunnel-client run --profile-file ".riftreader-local\mcp\openai-tunnel\riftreader-chatgpt.yaml"
```

Alternatively, after setting the two environment variables:

```cmd
scripts\start_chatgpt_mcp_tunnel.cmd
```

Keep the tunnel-client window running while ChatGPT scans tools and while
ChatGPT uses the MCP tools.

## What the repo writes locally

| Path | Purpose |
|---|---|
| `.riftreader-local\mcp\openai-tunnel\riftreader-chatgpt.yaml` | Local tunnel-client profile. |
| `.riftreader-local\mcp\openai-tunnel\mcp-authorization-header.txt` | Local auth header consumed by tunnel-client. |
| `.riftreader-local\mcp\openai-tunnel\status.json` | Readiness summary. |
| `.riftreader-local\mcp\openai-tunnel\tunnel-client-health.url` | tunnel-client health/admin URL if the daemon writes one. |

These files are ignored by Git and must stay local.

The profile uses `file:` references for the local MCP auth header so the bearer
token is not placed on the command line. The helper never prints the token.

The generated profile follows the current tunnel-client YAML shape for HTTP MCP
servers: `mcp.server_urls` binds channel `main`, while `mcp.extra_headers` and
`mcp.discovery_extra_headers` provide the local bearer-token header from a file.

## ChatGPT setup

In ChatGPT Web:

1. Open Settings > Apps.
2. Enable Developer mode if required for your plan/workspace.
3. Create a custom app.
4. Choose **Tunnel** under Connection.
5. Select the tunnel or paste the matching `CONTROL_PLANE_TUNNEL_ID`.
6. Scan tools while `tunnel-client run ...` is healthy.
7. Start a new chat, choose Developer mode/tools, and select the RiftReader app.

Use prompts like:

```text
Use the RiftReader app only. First call health, then get_repo_status, then get_latest_handoff.
Do not use Codex, browser, built-in web search, or any other connector for repo status.
```

## Failure triage

| Failure | Meaning | Fix |
|---|---|---|
| `tunnel-client` not found | Binary is not installed or not on PATH. | Install it or set `TUNNEL_CLIENT_EXE` to the full path. |
| Missing `CONTROL_PLANE_TUNNEL_ID` | No OpenAI tunnel selected. | Create/select a tunnel in OpenAI Platform and set the env var. |
| Missing `CONTROL_PLANE_API_KEY` | Runtime key is not available to the daemon. | Create a runtime key with Tunnels Read + Use and set it in the shell. |
| Local MCP unreachable | `scripts\start_mcp_local_background.cmd` is not running. | Start the local server and retry. |
| `origin_rejected` | A browser-origin request is not from an allowed OpenAI/loopback origin. | Use ChatGPT/tunnel-client or add only a trusted origin in local config. |
| Unsupported `MCP-Protocol-Version` | Client sent an unsupported MCP transport version. | Use a current ChatGPT/tunnel-client client. |
| Tool scan shows old tools | ChatGPT uses a frozen snapshot. | Refresh/rescan the app tools in ChatGPT settings. |
| ChatGPT app not visible | Workspace/plan/developer-mode gate. | Check Settings > Apps and workspace app permissions. |
