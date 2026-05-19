# RiftReader ChatGPT MCP adapter

Status: MVP, narrow tool-only adapter.

Final-product readiness contract: `docs\workflow\riftreader-chatgpt-mcp-final-readiness.md`.

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
| `health` | Read-only | Returns server status, redacted repo identity, version, tool manifest, and safety flags. |
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
- Public-facing health output reports the repo as `.` plus a repo name; it does
  not expose the absolute local repository path.

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
and `health` through the MCP streamable HTTP client, writes a local summary
under `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`, then stops
the server. It does **not** start a tunnel or register anything in ChatGPT.

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --transport-smoke --json
```

To prove the guarded write-shaped MCP tool over the same real SDK/client
transport before using ChatGPT, run the proposal transport smoke. It submits a
synthetic `package-proposal` through `submit_package_proposal`, confirms
`list_inbox` can see the result, writes only ignored `.riftreader-local`
inbox/audit/smoke artifacts, and stops the temporary loopback server.

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json
```

For a single compact local go/no-go gate before any public tunnel or ChatGPT
registration, run trial readiness. This runs the handler self-test, SDK
metadata validation, loopback transport smoke including a synthetic
`submit_package_proposal` call, and optional `cloudflared`/`curl` availability
checks. It writes a compact summary under
`.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`.

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --trial-readiness --json
```

The same gate is exposed through Operator Lite:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
```

This may create ignored `.riftreader-local` self-test/audit/smoke/inbox
artifacts and may start a temporary loopback-only server for transport
validation, including one synthetic package proposal. It does not start a
public tunnel, register ChatGPT, serve persistently, apply package content,
mutate Git, send RIFT input, or attach CE/x64dbg.

Optional explicit public-tunnel smoke:

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --cloudflare-tunnel-smoke --json
```

This starts a temporary Cloudflare quick tunnel and a temporary loopback MCP
server, calls `initialize`, `tools/list`, and `tools/call` for `health` through
the public HTTPS `/mcp` URL with an `Origin: https://chatgpt.com` header, writes a local summary under
`.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`, then stops both
processes. It is opt-in only and does not register the app in ChatGPT. To test
a different ChatGPT web origin, pass `--cloudflare-smoke-origin <exact-origin>`.
The smoke helper records any curl DNS override IP it had to use under
`curlResolveIp` because quick-tunnel DNS can take a few seconds to propagate.
The transport/public smoke verifier also fails closed if `health` no longer
redacts the repo root as `.` or if `absoluteRepoRootExposed` is not `false`.

Optional bounded ChatGPT registration session:

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 900 --json
```

This starts a temporary Cloudflare quick tunnel and a temporary loopback MCP
server, verifies the public HTTPS `/mcp` endpoint, writes a ready packet under
`.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`, keeps the endpoint
alive for the requested bounded duration, then stops both processes. Use the
printed `publicMcpUrl` in ChatGPT Developer Mode while the command is still
running. Pass `--chatgpt-session-seconds 0` to verify setup and stop
immediately. The helper does **not** register the app in ChatGPT and does not
expose shell, Git mutation, RIFT input, CE, x64dbg, or arbitrary filesystem
tools.


## MCP Workflow Suite helpers

The local helper suite gives one place to find the latest MCP proof artifacts,
choose the next safe action, record actual ChatGPT-side proof facts, and prepare
an explicit-path commit checklist. Defaults are local-first and read-only except
for ignored `.riftreader-local` proof records created by the trial recorder.

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-mcp-mission-control.cmd --json
.\scripts\riftreader-mcp-artifacts.cmd --latest --json
.\scripts\riftreader-workflow-router.cmd --mcp --json
.\scripts\riftreader-chatgpt-trial-recorder.cmd --template --json
.\scripts\riftreader-safe-commit-packager.cmd --plan --json
```

| Helper | Command | Default behavior |
|---|---|---|
| MCP Mission Control | `scripts\riftreader-mcp-mission-control.cmd --json` | Shows readiness, latest artifacts, Git dirty summary, ranked next actions, paste-safe commands, `--summary-md`, and `--checklist-md`. |
| Final Readiness Gate | `scripts\riftreader-mcp-final.cmd --status --compact-json` | Authoritative final-product gate covering Phase 2 proof/CI/freshness, clean tree, upstream sync, dependency checks, environment preflight, tool-surface safety, and public-session state. |
| Proof Artifact Browser | `scripts\riftreader-mcp-artifacts.cmd --latest --json` | Lists latest readiness/smoke/trial/inbox/draft/dry-run/proof artifacts; `--timeline`, `--kind <kind>`, and read-only `--open-latest` are supported. |
| Workflow Router | `scripts\riftreader-workflow-router.cmd --mcp --json` | Emits one recommended next action plus ranked alternatives from local artifacts and dirty state. |
| ChatGPT Trial Recorder | `scripts\riftreader-chatgpt-trial-recorder.cmd --record --input proof.json --json` | Records operator-supplied actual ChatGPT facts under `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof`; fails closed on tool count, repo-root redaction, inbox, draft, or dry-run proof gaps. |
| Safe Commit Packager | `scripts\riftreader-safe-commit-packager.cmd --plan --json` | Generates explicit `git add -- <path>` checklist and commit-message draft only; `--markdown` prints a review packet; it never stages, commits, or pushes. |
| Phase 1 Completion Gate | `scripts\riftreader-mcp-phase1.cmd --status --json` | Evaluates repo-side readiness plus actual ChatGPT client proof and reports whether Phase 1 is complete or externally blocked. |

The shared state layer marks self-test inbox/draft artifacts, adds artifact age
fields, warns on stale proof budgets, and labels stopped ephemeral public URLs
as expected-expired. The final gate also checks loopback port allocation,
default serve-port availability, and whether `.riftreader-local` remains
Git-ignored for local MCP artifacts. `MCP Mission Control --trial-command`
prints the bounded public trial command without running it. Only
`--run-readiness` and `--run-proposal-smoke` execute local-only validation. No
helper starts a public tunnel by default. The Phase 1 gate intentionally reports
`blocked` until an actual ChatGPT Developer Mode proof packet is recorded with a
passing `actual-client-proof` artifact.

## Running the MCP server locally

The server path uses the official Python MCP SDK when `--serve` is requested.
Install the SDK before serving if it is not already available:

RUN THIS:

```powershell
python -m pip install "mcp[cli]"
```

For an isolated repo-local validation install that does not modify the global
Python environment, use an ignored target directory. The MCP validation helpers
auto-detect `.riftreader-local\mcp-sdk-validation` when present:

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
python -m pip install --target .riftreader-local\mcp-sdk-validation "mcp[cli]"
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

ChatGPT Developer Mode requires an HTTPS-reachable MCP endpoint. The adapter
does not start a public tunnel by default; use the bounded
`--chatgpt-trial-session` helper above or expose the local server with a
manually started tunnel such as Cloudflare Tunnel or ngrok.

For Cloudflare quick tunnels, the public hostname is random and must be
allowlisted on the MCP server. Start the tunnel first, copy the bare hostname
from the generated URL, then start the server with `--allowed-host`.

Terminal 1:

RUN THIS:

```powershell
cloudflared tunnel --url http://127.0.0.1:8770 --no-autoupdate
```

If Cloudflare prints:

```text
https://example.trycloudflare.com
```

Terminal 2:

RUN THIS:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --serve --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host example.trycloudflare.com --allowed-origin https://chatgpt.com
```

Use the generated HTTPS URL plus `/mcp` as the ChatGPT connector URL, for
example:

```text
https://example.trycloudflare.com/mcp
```

Do not pass a full URL to `--allowed-host`; pass only the exact Host header
value, such as `example.trycloudflare.com`. Pass only an exact origin to
`--allowed-origin`, such as `https://chatgpt.com`; do not include a path,
query, fragment, credentials, or wildcard. If `--allowed-host` is omitted for a
public tunnel, the Python MCP SDK's DNS-rebinding protection can reject the
request with HTTP `421 Misdirected Request`. If an `Origin` header is present
and not allowlisted, it can reject the request with HTTP `403 Forbidden`.

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

- ChatGPT Developer Mode creates apps from remote MCP servers and supports SSE
  and streaming HTTP.
- ChatGPT Developer Mode supports OAuth, No Authentication, and Mixed
  Authentication. The current RiftReader trial session uses No Authentication.
- ChatGPT Developer Mode supports MCP tools, including read and write tools, but
  write actions require careful review; read-only detection respects
  `readOnlyHint`.
- ChatGPT local development needs an HTTPS-reachable MCP endpoint, commonly via
  ngrok or Cloudflare Tunnel.
- Current Python MCP SDK examples use `from mcp.server.fastmcp import FastMCP`
  and `mcp.run(transport="streamable-http")`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `MCP_PYTHON_SDK_MISSING` | Python `mcp` package is not installed. | Install `mcp[cli]` before `--serve`. |
| HTTP `421 Misdirected Request` through a tunnel | The tunnel Host header is not allowlisted. | Restart `--serve` with `--allowed-host <bare-public-host>` and, for ChatGPT, `--allowed-origin https://chatgpt.com`. |
| HTTP `403 Forbidden` through a tunnel | The request has an `Origin` header not in `allowed_origins`. | Restart `--serve` with `--allowed-origin https://chatgpt.com` or the exact origin being tested. |
| ChatGPT cannot connect | Tunnel URL is missing `/mcp`, expired, or not HTTPS. | Restart local server/tunnel and re-register/refresh tools. |
| Write tool prompts for confirmation | Expected for action tools. | Review JSON payload before approving. |
| `PACKAGE_DRAFT_OPERATOR_EMPTY` | Only self-test drafts exist or no operator draft exists. | Submit/review a real operator-approved proposal first. |
| `INBOX_EMPTY` | No proposal is stored yet. | Submit a valid package proposal first. |
