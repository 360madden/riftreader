# RiftReader ChatGPT MCP adapter

Status: MVP, narrow tool-only adapter.

## Purpose

`riftreader_chatgpt_mcp` is a narrow MCP server for Desktop ChatGPT Developer
Mode. It exposes only allowlisted RiftReader workflow surfaces and deliberately
does **not** proxy broad local MCPs such as `rift_game` or `windows-mcp`.

The adapter is designed for this safe loop:

1. ChatGPT reads repo status and latest handoff context.
2. ChatGPT fetches the package-proposal template.
3. ChatGPT submits an operator-approved `package-proposal`.
4. The proposal is stored only under `.riftreader-local`.
5. Operator/Codex reviews inbox and inert package drafts before any separate
   dry-run/apply decision.

## Tool surface

| Tool | Access | Behavior |
|---|---|---|
| `health` | Read-only | Returns server status, repo root, version, tool manifest, and safety flags. |
| `get_repo_status` | Read-only | Returns compact repo/workflow truth using existing status helper logic. |
| `get_latest_handoff` | Read-only | Reads only the newest Markdown file under `docs/handoffs`. |
| `get_package_proposal_template` | Read-only | Returns the existing Local Artifact Bridge package proposal template/schema. |
| `submit_package_proposal` | Guarded write | Stores a valid `package-proposal` only under `.riftreader-local\artifact-bridge-inbox`. |
| `list_inbox` | Read-only | Lists Local Artifact Bridge inbox metadata only. |
| `review_latest_package_draft` | Read-only | Returns latest inert package draft review status; defaults to non-self-test operator drafts. |
| `dry_run_latest_package_draft` | Explicit action | Runs package-draft intake dry-run only; never passes `--apply`. |

## Hard boundaries

- No arbitrary filesystem read tool.
- No arbitrary filesystem write tool.
- No shell execution endpoint.
- No Git stage/commit/push/reset/clean endpoint.
- No RIFT input, movement, target control, CE, or x64dbg endpoint.
- No automatic persistent bridge/tunnel startup.
- No proxying `rift_game`, `windows-mcp`, or other broad MCPs.
- All ChatGPT-originated writes stay under `.riftreader-local`.
- Server audit events are sanitized and written under
  `.riftreader-local\riftreader-chatgpt-mcp\audit`.

## Local checks

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --tool-manifest --json
.\scripts\riftreader-chatgpt-mcp.cmd --self-test --json
```

The self-test runs local handlers without ChatGPT and without a public tunnel.
It may create ignored `.riftreader-local` inbox, draft, package-intake, and audit
artifacts. It must not apply files, mutate Git, start a server, start a tunnel,
send RIFT input, or attach CE/x64dbg.

If the Python MCP SDK is installed, validate actual FastMCP import, tool
registration, descriptions, and annotations without starting a server:

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json
```

After SDK validation passes, run a bounded loopback transport smoke test. This
starts a temporary `127.0.0.1` server on an ephemeral port, calls `list_tools`
and `health` through the MCP streamable HTTP client, then stops the server. It
does **not** start a tunnel or register anything in ChatGPT.

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --transport-smoke --json
```

## Running the MCP server locally

The server path uses the official Python MCP SDK when `--serve` is requested.
Install the SDK before serving if it is not already available:

RUN THIS:

```powershell
python -m pip install "mcp[cli]"
```

For an isolated repo-local validation install that does not modify the global
Python environment, use an ignored target directory and prepend it to
`PYTHONPATH` only for validation commands:

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
python -m pip install --target .riftreader-local\mcp-sdk-validation "mcp[cli]"
$env:PYTHONPATH = (Resolve-Path .riftreader-local\mcp-sdk-validation).Path + [System.IO.Path]::PathSeparator + (Resolve-Path tools).Path
.\scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json
.\scripts\riftreader-chatgpt-mcp.cmd --transport-smoke --json
```

Then start the local server manually:

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --serve --host 127.0.0.1 --port 8770 --transport streamable-http
```

Local MCP endpoint:

```text
http://127.0.0.1:8770/mcp
```

## Manual HTTPS exposure for ChatGPT Developer Mode

ChatGPT Developer Mode requires an HTTPS-reachable MCP endpoint. Do not start a
tunnel automatically from the MCP adapter. When you intentionally test, expose
the local server with a manually started tunnel such as Cloudflare Tunnel or
ngrok.

Example with Cloudflare Tunnel:

RUN THIS:

```powershell
cloudflared tunnel --url http://127.0.0.1:8770
```

Use the generated HTTPS URL plus `/mcp` as the ChatGPT connector URL, for
example:

```text
https://example.trycloudflare.com/mcp
```

## Registering in ChatGPT Developer Mode

In ChatGPT web:

1. Enable Developer Mode under Settings -> Apps -> Advanced settings.
2. Open Apps/Connectors settings.
3. Create an app/connector for the tunnel URL ending in `/mcp`.
4. Confirm the tool list contains only the eight tools in this document.
5. In the conversation, explicitly select Developer Mode and this app.

Suggested first prompt:

```text
Use only the RiftReader ChatGPT MCP app. First call health, then get_repo_status,
then get_latest_handoff. Do not call write/action tools unless I explicitly ask
in this turn.
```

## Notes from current OpenAI/MCP docs

- ChatGPT Developer Mode supports MCP tools, including read and write tools, but
  write actions require careful review.
- ChatGPT local development needs an HTTPS-reachable MCP endpoint, commonly via
  ngrok or Cloudflare Tunnel.
- Current Python MCP SDK examples use `from mcp.server.fastmcp import FastMCP`
  and `mcp.run(transport="streamable-http")`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `MCP_PYTHON_SDK_MISSING` | Python `mcp` package is not installed. | Install `mcp[cli]` before `--serve`. |
| ChatGPT cannot connect | Tunnel URL is missing `/mcp`, expired, or not HTTPS. | Restart local server/tunnel and re-register/refresh tools. |
| Write tool prompts for confirmation | Expected for action tools. | Review JSON payload before approving. |
| `PACKAGE_DRAFT_OPERATOR_EMPTY` | Only self-test drafts exist or no operator draft exists. | Submit/review a real operator-approved proposal first. |
| `INBOX_EMPTY` | No proposal is stored yet. | Submit a valid package proposal first. |
