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

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
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

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json
```

After SDK validation passes, run a bounded loopback transport smoke test. This
starts a temporary `127.0.0.1` server on an ephemeral port, calls `list_tools`
and `health` through the MCP streamable HTTP client, writes a local summary
under `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`, then stops
the server. It does **not** start a tunnel or register anything in ChatGPT.

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --transport-smoke --json
```

To prove the guarded write-shaped MCP tool over the same real SDK/client
transport before using ChatGPT, run the proposal transport smoke. It submits a
synthetic `package-proposal` through `submit_package_proposal`, confirms
`list_inbox` can see the result, writes only ignored `.riftreader-local`
inbox/audit/smoke artifacts, and stops the temporary loopback server.

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json
```

For a single compact local go/no-go gate before any public tunnel or ChatGPT
registration, run trial readiness. This runs the handler self-test, SDK
metadata validation, loopback transport smoke including a synthetic
`submit_package_proposal` call, optional OpenAI `tunnel-client`/`curl`
readiness checks, and records Cloudflare only as a deprecated fallback. It
writes a compact summary under
`.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`.

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --trial-readiness --json
```

The same gate is exposed through Operator Lite:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
```

This may create ignored `.riftreader-local` self-test/audit/smoke/inbox
artifacts and may start a temporary loopback-only server for transport
validation, including one synthetic package proposal. It does not start a
public tunnel, register ChatGPT, serve persistently, apply package content,
mutate Git, send RIFT input, or attach CE/x64dbg.

OpenAI Secure MCP Tunnel command plan:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json
```

This prints the repo-specific OpenAI Secure MCP Tunnel plan for the local
RiftReader MCP adapter. It does not start a tunnel, create credentials, register
ChatGPT, mutate Git, send RIFT input, or expose broad local tools. Use this plan
to configure `tunnel-client` with a local stdio MCP command. The JSON includes
both argument arrays and copyable command-line strings, plus the exact first
ChatGPT smoke order: `health`, `get_repo_status`, then `get_latest_handoff`.

Deprecated Cloudflare fallback smoke:

RUN THIS ONLY AS FALLBACK:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --cloudflare-tunnel-smoke --json
```

This starts a temporary Cloudflare quick tunnel and a temporary loopback MCP
server, verifies the public HTTPS `/mcp` endpoint, writes a local summary under
`.riftreader-local\riftreader-chatgpt-mcp\transport-smoke`, then stops both
processes. It is fallback/dev-only and planned for full deprecation. Do not use
it as the primary ChatGPT Web/Desktop route.

Deprecated bounded Cloudflare ChatGPT registration session:

RUN THIS ONLY AS FALLBACK:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --chatgpt-trial-session --chatgpt-session-seconds 900 --json
```

This keeps the old Cloudflare quick-tunnel registration window available only
for fallback debugging while OpenAI Secure MCP Tunnel becomes the primary path.


## MCP Workflow Suite helpers

The local helper suite gives one place to find the latest MCP proof artifacts,
choose the next safe action, record actual ChatGPT-side proof facts, and prepare
an explicit-path commit checklist. Defaults are local-first and read-only except
for ignored `.riftreader-local` proof records created by the trial recorder.

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-mcp-mission-control.cmd --json
.\scripts\riftreader-mcp-artifacts.cmd --latest --json
.\scripts\riftreader-workflow-router.cmd --mcp --json
.\scripts\riftreader-chatgpt-trial-recorder.cmd --template --json
.\scripts\riftreader-safe-commit-packager.cmd --plan --json
```

| Helper | Command | Default behavior |
|---|---|---|
| MCP Mission Control | `scripts\riftreader-mcp-mission-control.cmd --json` | Shows readiness, latest artifacts, Git dirty summary, ranked next actions, paste-safe commands, `--summary-md`, and `--checklist-md`. |
| Secure Tunnel Plan | `scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json` | Writes an ignored local plan artifact, verifies the `tunnel-client` binary SHA256 plus `--version` probe, and prints `init`, `doctor`, and `run` command lines; returns blocked until the binary is installed/found and executable. |
| Final Readiness Gate | `scripts\riftreader-mcp-final.cmd --status --compact-json` | Authoritative final-product gate covering Phase 2 proof/CI/freshness, clean tree, upstream sync, `tunnel-client` dependency checks, environment preflight, tool-surface safety, and public-session state. |
| Proof Artifact Browser | `scripts\riftreader-mcp-artifacts.cmd --latest --json` | Lists latest readiness/smoke/trial/inbox/draft/dry-run/proof artifacts; `--timeline`, `--kind <kind>`, and read-only `--open-latest` are supported. |
| Workflow Router | `scripts\riftreader-workflow-router.cmd --mcp --json` | Emits one recommended next action plus ranked alternatives from local artifacts and dirty state. |
| ChatGPT Trial Recorder | `scripts\riftreader-chatgpt-trial-recorder.cmd --record --input proof.json --json` | Records operator-supplied actual ChatGPT facts under `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof`; fails closed on tool count, repo-root redaction, inbox, draft, or dry-run proof gaps. |
| Safe Commit Packager | `scripts\riftreader-safe-commit-packager.cmd --plan --json` | Generates explicit `git add -- <path>` checklist and commit-message draft only; `--markdown` prints a review packet; it never stages, commits, or pushes. |
| Phase 1 Completion Gate | `scripts\riftreader-mcp-phase1.cmd --status --json` | Evaluates repo-side readiness plus actual ChatGPT client proof and reports whether Phase 1 is complete or externally blocked. |

The shared state layer marks self-test inbox/draft artifacts, adds artifact age
fields, indexes Secure Tunnel plan artifacts, warns on stale proof budgets, and
labels stopped or aged-out ephemeral public URLs as expected-expired. The final
gate also checks loopback port allocation, default serve-port availability,
primary-path `tunnel-client` dependency presence plus SHA256/`--version`
binary diagnostics, and whether `.riftreader-local` remains Git-ignored for
local MCP artifacts. The compact final status exposes these checks under
`secureTunnelClient` so CI logs and Mission Control summaries show the binary
status without requiring operators to inspect the full dependency payload.
`MCP Mission Control --secure-tunnel-plan` prints the Secure Tunnel plan command
without running `tunnel-client`; `--trial-command` remains a deprecated
fallback-only Cloudflare public trial command. Only `--run-readiness` and
`--run-proposal-smoke` execute local-only validation. No helper starts a public
tunnel by default. The Phase 1 gate intentionally reports `blocked` until an
actual ChatGPT Developer Mode proof packet is recorded with a passing
`actual-client-proof` artifact.

## Final-product Mission Control flow

Phase 5 makes Mission Control the default operator entrypoint for the MCP final
product lane. Use it before public exposure:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-mcp-mission-control.cmd --summary-md
.\scripts\riftreader-mcp-mission-control.cmd --checklist-md
.\scripts\riftreader-mcp-final.cmd --status --compact-json
```

Mission Control now emits:

| Field / mode | Purpose |
|---|---|
| `finalStatus` | Compact final gate result with CI, proof, dependency, environment, tool-surface, and public-session status. |
| `finalProductProgress` | Phase 1-8 progress table with completed phases, next phase, and explicit public-trial boundary state. |
| `operatorNextAction` | One dashboard-selected next operator action. |
| `--summary-md` | Human-readable progress and latest-artifact summary suitable for handoff context. |
| `--checklist-md` | Paste-safe proof checklist covering final gate, optional local refreshes, explicit public trial, package review, proof recording, and final gate rerun. |
| `--trial-command --json` | Prints the bounded public-trial command without running it. |

Mission Control remains safe by default: it does not start a public tunnel,
register ChatGPT, mutate Git, apply packages, send RIFT input, attach CE/x64dbg,
or write provider repos. Only `--run-readiness` and `--run-proposal-smoke`
execute local-only validation helpers; the public trial command is display-only
unless the operator explicitly runs the printed command.

## Running the MCP server locally

The server path uses the official Python MCP SDK when `--serve` is requested.
Install the SDK before serving if it is not already available:

RUN THIS:

```cmd
python -m pip install "mcp[cli]"
```

For an isolated repo-local validation install that does not modify the global
Python environment, use an ignored target directory. The MCP validation helpers
auto-detect `.riftreader-local\mcp-sdk-validation` when present:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
python -m pip install --target .riftreader-local\mcp-sdk-validation "mcp[cli]"
.\scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json
.\scripts\riftreader-chatgpt-mcp.cmd --transport-smoke --json
```

Then start the local server manually:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --serve --host 127.0.0.1 --port 8770 --transport streamable-http
```

Local MCP endpoint:

```text
http://127.0.0.1:8770/mcp
```

## ChatGPT Web/Desktop route: OpenAI Secure MCP Tunnel

ChatGPT Developer Mode needs an HTTPS-reachable MCP endpoint, but the preferred
RiftReader path is now **OpenAI Secure MCP Tunnel**, not a public Cloudflare
quick tunnel. OpenAI Secure MCP Tunnel keeps the MCP server private: a local
`tunnel-client` opens outbound HTTPS to OpenAI and forwards MCP requests to the
local RiftReader adapter.

Primary local plan command:

RUN THIS:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-mcp.cmd --secure-tunnel-plan --json
```

The plan prints the exact local stdio MCP command for `tunnel-client`. If the
plan reports `TUNNEL_CLIENT_NOT_FOUND`, install/download `tunnel-client` from
OpenAI Platform tunnel settings or the latest `openai/tunnel-client` release,
then rerun with either PATH discovery or `--tunnel-client-path <path>`. If the
plan reports a `tunnel-client-version-probe-failed` blocker, replace the binary
or fix local execution before configuring a tunnel profile.
If you pass `--secure-tunnel-id`, it must be a `tunnel_...` identifier. The
plan blocks and redacts the input when the value is malformed or resembles an
OpenAI API key; generated plan artifacts should keep
`secretLeakCheck.status=passed` and `safety.credentialPlaceholderOnly=true`
until the operator intentionally runs `tunnel-client` outside this planning
helper.
RiftReader also checks these adminless paths before the Program Files fallback:

- `TUNNEL_CLIENT_PATH`, `OPENAI_TUNNEL_CLIENT_PATH`, `TUNNEL_CLIENT`, or
  `OPENAI_TUNNEL_CLIENT` environment variables.
- `C:\RIFT MODDING\Tools\OpenAI\tunnel-client\tunnel-client.exe`.
- `.riftreader-local\tools\openai\tunnel-client\tunnel-client.exe`.

Current local shared-tools install:

| Field | Value |
|---|---|
| Version | `0.0.9+62b9b42f698ec5319d2115e0c0ff1dcf6557d7ae` |
| Release tag | `v0.0.9--context-conduit-topaz` |
| Installed binary | `C:\RIFT MODDING\Tools\OpenAI\tunnel-client\tunnel-client.exe` |
| Source ZIP | `tunnel-client-v0.0.9--context-conduit-topaz-windows-amd64.zip` |
| Source ZIP SHA-256 | `570fe871cb1f8911653433a04e2905488e3316994054b49b34e9219aaa61fd92` |

Note: this installed CLI advertises `tunnel-client help quickstart` in `--help`,
but that topic currently returns an unknown-topic error. Do not depend on it in
automation; use the generated `init`, `doctor`, and `run` commands instead.

Before connecting ChatGPT, create or choose a tunnel in OpenAI Platform tunnel
settings and obtain a runtime API key whose principal has Tunnels Read + Use for
that tunnel. Creating or editing tunnel metadata additionally requires Tunnels
Read + Manage. The `tunnel-client` host needs outbound HTTPS to OpenAI and local
reachability to the stdio MCP command printed by the plan.

Command shape:

```cmd
set "CONTROL_PLANE_API_KEY=<runtime API key with Tunnels Read + Use>"
tunnel-client init --sample sample_mcp_stdio_local --profile riftreader-local-stdio --tunnel-id <tunnel_id> --mcp-command "<printed MCP command>"
tunnel-client doctor --profile riftreader-local-stdio --explain
tunnel-client run --profile riftreader-local-stdio
```

Keep `tunnel-client run` healthy while creating or testing the ChatGPT app. In
ChatGPT connector settings, create a custom connector, choose **Tunnel** under
Connection, then select the available tunnel or paste its `tunnel_id`. Use
`tunnel-client doctor --profile riftreader-local-stdio --explain`, the local
admin UI, `/healthz`, and `/readyz` to confirm the client is healthy and ready
before ChatGPT smoke testing. Do not paste a `trycloudflare.com` URL for the
primary path.

## Deprecated manual public HTTPS exposure

Cloudflare quick tunnels and ngrok-style public URLs are now fallback/dev-only.
They expose a local server through a public HTTPS URL and are planned for full
Cloudflare deprecation in this repo. Use them only when Secure MCP Tunnel is
unavailable and the operator explicitly selects the fallback lane.

For fallback public tunnels, the public hostname must still be allowlisted on
the MCP server. Do not pass a full URL to `--allowed-host`; pass only the exact
Host header value, such as `example.trycloudflare.com`. Pass only an exact
origin to `--allowed-origin`, such as `https://chatgpt.com`; do not include a
path, query, fragment, credentials, or wildcard.

## Registering in ChatGPT Developer Mode

In ChatGPT web:

1. Enable Developer Mode under Settings -> Apps -> Advanced settings.
2. Open Apps/Connectors settings.
3. Create an app/connector using the OpenAI Secure MCP Tunnel connection path.
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
- ChatGPT local development needs an HTTPS-reachable MCP endpoint. The preferred
  RiftReader route is OpenAI Secure MCP Tunnel; Cloudflare quick tunnel is
  fallback/dev-only.
- Secure MCP Tunnel uses `tunnel-client` inside the private/local network. The
  client opens outbound HTTPS to OpenAI, forwards MCP work to a local stdio or
  HTTP MCP server, and keeps the private MCP server off the public internet.
- ChatGPT connector setup should choose **Tunnel** under Connection and use the
  OpenAI-hosted tunnel endpoint or `tunnel_id`; if the tunnel is not visible,
  check workspace association and Tunnels Read + Use permission.
- Current Python MCP SDK examples use `from mcp.server.fastmcp import FastMCP`
  and `mcp.run(transport="streamable-http")`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `MCP_PYTHON_SDK_MISSING` | Python `mcp` package is not installed. | Install `mcp[cli]` before `--serve`. |
| `TUNNEL_CLIENT_NOT_FOUND` | OpenAI `tunnel-client` is not installed, not on PATH, or not passed explicitly. | Install/download it from OpenAI Platform tunnel settings or latest `openai/tunnel-client` release; rerun `--secure-tunnel-plan --tunnel-client-path <path>` if needed. |
| `secure-tunnel-id-looks-like-secret` | A value passed as `--secure-tunnel-id` resembles a credential instead of a tunnel id. | Do not paste API keys into `--secure-tunnel-id`; use the generated `CONTROL_PLANE_API_KEY` environment placeholder only when manually running `tunnel-client`. |
| `secure-tunnel-id-invalid-format` | A supplied tunnel id was not in the expected `tunnel_...` form. | Re-run with a valid Platform tunnel id or omit the flag to keep the placeholder. |
| Tunnel not visible in ChatGPT | Tunnel is not associated with the target workspace, or the connector operator lacks Tunnels Read + Use. | Fix workspace/permission scope in Platform, then refresh ChatGPT connector settings. |
| Connector discovery/tool calls fail through Secure MCP Tunnel | `tunnel-client run` is not healthy or not connected. | Rerun `tunnel-client doctor --profile riftreader-local-stdio --explain` and check `/ui`, `/healthz`, and `/readyz`. |
| HTTP `421 Misdirected Request` through a tunnel | The tunnel Host header is not allowlisted. | Restart `--serve` with `--allowed-host <bare-public-host>` and, for ChatGPT, `--allowed-origin https://chatgpt.com`. |
| HTTP `403 Forbidden` through a tunnel | The request has an `Origin` header not in `allowed_origins`. | Restart `--serve` with `--allowed-origin https://chatgpt.com` or the exact origin being tested. |
| ChatGPT cannot connect | Tunnel URL is missing `/mcp`, expired, or not HTTPS. | Restart local server/tunnel and re-register/refresh tools. |
| Write tool prompts for confirmation | Expected for action tools. | Review JSON payload before approving. |
| `PACKAGE_DRAFT_OPERATOR_EMPTY` | Only self-test drafts exist or no operator draft exists. | Submit/review a real operator-approved proposal first. |
| `INBOX_EMPTY` | No proposal is stored yet. | Submit a valid package proposal first. |
