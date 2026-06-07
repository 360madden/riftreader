# ChatGPT Web/Desktop MCP domain prerequisite/context handoff

Generated: `2026-06-07T16:55:00-04:00` (`2026-06-07T20:55:00Z`)

## Current objective

Reach a real ChatGPT Web/Desktop Developer Mode proof path:

```text
ChatGPT Web/Desktop Developer Mode
-> https://mcp.360madden.com/mcp
-> DNS / Cloudflare / router / firewall
-> operator-owned Caddy or equivalent HTTPS reverse proxy on this PC
-> http://127.0.0.1:8770/mcp
-> operator-owned RiftReader ChatGPT MCP server
-> C:\RIFT MODDING\RiftReader
```

A saved ChatGPT app does not start the local repo MCP server, does not start
Caddy/nginx, does not configure Cloudflare/router/firewall, and does not prove
actual local-repo access by itself.

## Repo context recovered

| Context | Current truth |
|---|---|
| Canonical adapter | `scripts\riftreader-chatgpt-mcp.cmd`; do not create a duplicate adapter. |
| Runtime proof boundary | Final non-Codex proof requires operator-owned MCP/proxy processes outside Codex. Codex-started processes are useful diagnostics only. |
| Current target URL | `https://mcp.360madden.com/mcp`. |
| Auth | `No Authentication` for Phase 0. |
| Phase 0 profile | `--tool-profile public-read-only` exposes only `health`, `get_repo_status`, `get_latest_handoff`, `get_workflow_control_summary`, and `get_workflow_control_plan`. |
| Full final path | Default `--tool-profile full` remains the 12-tool final-proof path. |
| Retired paths | OpenAI Secure MCP Tunnel and `trycloudflare.com` quick tunnels are not backups for this lane. |

## Prerequisite chain now encoded in helper output

`tools/riftreader_workflow/riftreader_chatgpt_mcp.py` now makes the operator
launch plan default to `mcp.360madden.com` and emits the full prerequisite chain:

1. operator-owned local MCP server process;
2. operator-owned HTTPS reverse proxy process such as Caddy/nginx on TCP 443;
3. DNS/public-host route for `mcp.360madden.com` reaches the reverse proxy;
4. router/firewall forwards TCP 443, plus TCP 80 if Caddy ACME HTTP-01 is used;
5. Cloudflare or any edge proxy does not block `/mcp`, MCP initialize, or certificate challenges;
6. ChatGPT Web/Desktop app uses `https://mcp.360madden.com/mcp` with `No Authentication`.

Useful plan commands:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json
scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json
```

## Current diagnostic state

| Check | Result |
|---|---|
| Local MCP backend | Running during Codex diagnostics on `127.0.0.1:8770`, but not final proof because operator-owned runtime is required. |
| Local dashboard | Running during Codex diagnostics on `http://127.0.0.1:8788`, status-only. |
| Local Caddy | Running during Codex diagnostics on TCP `80/443`, using `.riftreader-local\riftreader-chatgpt-mcp\caddy\Caddyfile`. |
| Public domain smoke | Blocked by Cloudflare `403 Error 1010` / `browser_signature_banned`. |
| Caddy ACME | Blocked while Cloudflare intercepts/challenges; logs show HTTP-01 `502` and TLS-ALPN negotiation failures. |
| Actual ChatGPT proof | Not complete; must wait for public domain route to pass MCP initialize and for real ChatGPT tool calls. |

## Safe next action

Fix the external route first: Cloudflare/DNS/router/firewall/Caddy must allow
`https://mcp.360madden.com/mcp` to reach `http://127.0.0.1:8770/mcp` without
Cloudflare `403`, `502`, or non-MCP JSON. Then run:

```cmd
scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json
```

Only after that passes should the operator create/refresh the ChatGPT app and
record the Phase 0 `domain-read-only` proof packet.

## Validation in this slice

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\mcp_domain_diagnostics.py tools\riftreader_workflow\mcp_dashboard.py tools\riftreader_workflow\chatgpt_trial_recorder.py` | Passed. |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_domain_diagnostics scripts.test_mcp_dashboard` | Passed: 103 tests. |
| `scripts\riftreader-chatgpt-mcp.cmd --operator-launch-plan --json` | Passed; includes `mcp.360madden.com` and prerequisite chain. |
| `scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json` | Passed; classifies host as `domain-or-ddns-host` and lists Cloudflare/Caddy prerequisites. |

## Boundaries

No ChatGPT app registration was performed, no public route was changed, no
Cloudflare/router/firewall setting was modified, no RIFT input was sent, no
CE/x64dbg was used, and no provider repo was written.
