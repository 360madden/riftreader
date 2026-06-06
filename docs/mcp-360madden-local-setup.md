# RiftReader MCP 360madden Local Setup

This is the local-only first step for:

`ChatGPT Web -> https://mcp.360madden.com -> Cloudflare Tunnel -> local RiftReader MCP server -> C:\RIFT MODDING\RiftReader`

The server is Python-first, binds to `127.0.0.1`, and exposes only these read-only tools by default:

| Tool | Purpose |
|---|---|
| `health` | Safe server/repo metadata and tool count. |
| `get_repo_status` | Fixed read-only Git status/HEAD summary. |
| `get_latest_handoff` | Latest known repo-local handoff/status packet, with missing-file handling. |

## Local commands

If `360madden.com` was only purchased and not configured yet, first run:

```cmd
scripts\check_mcp_domain_readiness.cmd
```

This writes a no-secrets readiness summary under `.riftreader-local\mcp\domain-preflight\`.

Run from the repo root:

```cmd
scripts\test_mcp_local.cmd
```

Expected markers:

```text
PASS
END_RIFTREADER_MCP_HTTP_SMOKE
END_RIFTREADER_MCP_LOCAL_TEST
```

Start the local server:

```cmd
scripts\start_mcp_local.cmd
```

Expected startup fields:

| Field | Expected value |
|---|---|
| `status` | `listening` |
| `healthUrl` | `http://127.0.0.1:8765/health` |
| `mcpUrl` | `http://127.0.0.1:8765/mcp` |
| `authRequired` | `true` |
| `tokenConfigured` | `true` |

The first start creates `.riftreader-local\mcp\config.json` with a generated token. That file is ignored by Git and must not be committed.

## Safety boundaries

- No RIFT process attach.
- No game memory reads.
- No x64dbg or Cheat Engine.
- No router port forwarding.
- No write tools are implemented for this HTTP endpoint.
- No real token is committed; only `tools\riftreader_mcp\mcp-http-config.example.json` is tracked.

## Logs and runtime state

| Location | Purpose |
|---|---|
| `.riftreader-local\mcp\config.json` | Local untracked auth/config. |
| `.riftreader-local\mcp\logs\` | JSONL server logs with token redaction. |
| `.riftreader-local\mcp\smoke\` | Smoke-test summaries. |
| `.riftreader-local\mcp\latest\` | Operator handoff/status packet. |
