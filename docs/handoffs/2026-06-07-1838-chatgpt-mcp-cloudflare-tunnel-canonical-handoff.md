# ChatGPT MCP Cloudflare named Tunnel canonical route handoff

Generated: `2026-06-07T18:38:00-04:00` (`2026-06-07T22:38:00Z`)

## Current truth

The ChatGPT Web/Desktop MCP public route is now the persistent **Cloudflare named
Tunnel** route, not Caddy/router/direct public IP:

```text
ChatGPT Web/Desktop
-> https://mcp.360madden.com/mcp
-> Cloudflare proxied DNS
-> Cloudflare Tunnel riftreader-mcp-360madden
-> cloudflared Windows service
-> http://127.0.0.1:8770/mcp
-> RiftReader ChatGPT MCP adapter
```

## Canonical settings

| Item | Value |
|---|---|
| ChatGPT Server URL | `https://mcp.360madden.com/mcp` |
| ChatGPT auth | `No Authentication` |
| Expected app name | `rift-mcp` |
| Local adapter | `scripts\riftreader-chatgpt-mcp.cmd --serve ... --port 8770 --tool-profile public-read-only` |
| Cloudflare Tunnel | `riftreader-mcp-360madden` |
| Cloudflare published app service | `http://127.0.0.1:8770` |
| Cloudflare BIC rule | `Disable BIC for RiftReader MCP endpoint` for `/mcp*` |

## Deprecated / retired paths

| Path | Current rule |
|---|---|
| Caddy/router/direct-public-IP route | Deprecated legacy context; do not recreate as a fallback. |
| Local Caddy/nginx reverse proxy | Not part of the canonical public proof route. |
| TCP 443/80 router forwarding | Not required for the canonical Cloudflare named Tunnel route. |
| `trycloudflare.com` quick tunnels | Retired; not a ChatGPT Server URL backup. |
| OpenAI Secure MCP Tunnel | Retired for this no-OpenAI-API-key lane unless explicitly reauthorized. |

## Repo changes made in this slice

| Area | Change |
|---|---|
| Adapter plan JSON | `--operator-launch-plan` and `--manual-public-ip-plan --public-mcp-host mcp.360madden.com` now report `cloudflare-named-tunnel`, `cloudflareNamedTunnelPreferred=true`, and `caddyRouterDeprecated=true`. |
| Domain diagnostics | `mcp_domain_diagnostics.py` treats local TCP 443/Caddy ownership as legacy informational only and records `activeRoute.key=cloudflare-named-tunnel`. |
| Docs | Workflow, non-Codex policy, Cloudflare tunnel doc, AGENTS files, and current handoff text now identify Cloudflare named Tunnel as canonical and Caddy/router as deprecated. |
| Tests | Added/updated regression coverage for Cloudflare named Tunnel plan output, deprecated Caddy diagnostics, and docs propagation. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\mcp_domain_diagnostics.py tools\riftreader_mcp\domain_preflight.py tools\riftreader_mcp\operator_status.py` | Passed. |
| `python -m unittest scripts.test_chatgpt_mcp_workflow_docs scripts.test_mcp_domain_diagnostics scripts.test_riftreader_chatgpt_mcp` | Passed: 76 tests. |
| `scripts\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json` | Passed; recommended path is `cloudflare-named-tunnel`. |
| `scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json` | Passed; active path is `cloudflare-named-tunnel`. |
| `scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json` | Passed at `2026-06-07T22:37:12Z`; public HTTP 200 MCP initialize, `serverInfo.name=riftreader_chatgpt_mcp`, version `1.27.1`. |
| `scripts\riftreader-chatgpt-mcp.cmd --self-test --json` | Passed. |
| `scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json` | Passed. |
| `git --no-pager diff --check` | Passed. |

Latest public diagnostic artifact:

```text
.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics\20260607-223711Z\summary.json
```

## Safe next action

Record the actual ChatGPT Web/Desktop Phase 0 read-only proof using the
canonical Server URL, then begin a separate cleanup phase that removes remaining
Caddy/router implementation only after all route references and tests are
repointed to Cloudflare named Tunnel or explicitly marked legacy.
