# ChatGPT Web/Desktop MCP domain read-only dashboard handoff

Generated: `2026-06-07T15:25:00-04:00` (`2026-06-07T19:25:00Z`)

## ✅ Current result

The ChatGPT Web/Desktop MCP lane now has a safe **Phase 0 domain read-only proof** path and a localhost-only MCP activity dashboard, built on the existing canonical adapter rather than replacing it.

| Area | Current truth |
|---|---|
| Canonical adapter | `scripts\riftreader-chatgpt-mcp.cmd` remains the only ChatGPT Web/Desktop adapter launcher. |
| Full final path | Default `--tool-profile full` still exposes the existing 12-tool final-proof surface. |
| Phase 0 public proof path | `--tool-profile public-read-only` exposes only `health`, `get_repo_status`, `get_latest_handoff`, `get_workflow_control_summary`, and `get_workflow_control_plan`. |
| ChatGPT target | Server URL `https://mcp.360madden.com/mcp`, Authentication `No Authentication`, expected app name `rift-mcp`. |
| Dashboard | `scripts\riftreader-mcp-dashboard.cmd` serves a status-only local dashboard at `http://127.0.0.1:8788/`. |
| Domain diagnostics | `scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json` writes diagnostics under `.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics`. |
| Latest Phase 0 proof template | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-192205Z\proof-input.json`. |

## What changed in this slice

| File | Change |
|---|---|
| `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` | Added `--tool-profile full/public-read-only`, profile-aware manifest, SDK registration, serving, direct calls, and health output. |
| `tools/riftreader_workflow/chatgpt_trial_recorder.py` | Added `domain-read-only` proof templates and validation without weakening the existing 12-tool proof mode. |
| `tools/riftreader_workflow/mcp_domain_diagnostics.py` | Added Python-first status-only Caddy/domain/backend/public MCP initialize diagnostics using protocol/header `2025-06-18`. |
| `scripts/riftreader-mcp-domain-diagnostics.cmd` | Thin CMD launcher for the domain diagnostic helper. |
| `tools/riftreader_workflow/mcp_dashboard.py` | Added localhost-only status dashboard with redacted JSON, domain/backend/proof/safety/audit cards, and auto-refresh HTML. |
| `scripts/riftreader-mcp-dashboard.cmd` | Thin CMD launcher for the dashboard. |
| `scripts/test_riftreader_chatgpt_mcp.py` | Added read-only profile and profile-enforcement coverage. |
| `scripts/test_chatgpt_trial_recorder.py` | Added Phase 0 proof-template and validation coverage. |
| `scripts/test_mcp_domain_diagnostics.py` | Added domain smoke/Caddyfile protocol failure coverage. |
| `scripts/test_mcp_dashboard.py` | Added dashboard redaction/status-only coverage. |
| `docs/workflow/riftreader-chatgpt-mcp.md` | Documented Phase 0 read-only profile, domain diagnostics, dashboard, and proof workflow. |

## Current route status

| Check | Result |
|---|---|
| DNS for `mcp.360madden.com` | Passed; Cloudflare IPs resolve. |
| TCP 443 to `mcp.360madden.com` | Passed. |
| Local backend `127.0.0.1:8770` | Blocked during diagnostic: listener missing/not running. |
| Public MCP initialize | Blocked during diagnostic: Cloudflare `403 Error 1010` access denial. |
| Latest diagnostic artifact | `.riftreader-local\riftreader-chatgpt-mcp\domain-diagnostics\20260607-191604Z\summary.json`. |

## Validation performed

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\chatgpt_trial_recorder.py tools\riftreader_workflow\mcp_domain_diagnostics.py tools\riftreader_workflow\mcp_dashboard.py` | Passed. |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_domain_diagnostics scripts.test_mcp_dashboard` | Passed: 103 tests. |
| `scripts\riftreader-chatgpt-mcp.cmd --tool-manifest --tool-profile public-read-only --json` | Passed: exactly 5 read-only tools. |
| `scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --tool-profile public-read-only --json` | Passed: exactly 5 registered tools. |
| `scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json` | Passed: full profile still has 12 tools. |
| `scripts\riftreader-chatgpt-mcp.cmd --call health --tool-profile public-read-only --json` | Passed: health reports profile `public-read-only`, tool count 5. |
| `scripts\riftreader-chatgpt-mcp.cmd --call submit_package_proposal --tool-profile public-read-only --json` | Correctly blocked with `TOOL_NOT_EXPOSED_IN_PROFILE`. |
| `scripts\riftreader-chatgpt-trial-recorder.cmd --self-test --json` | Passed. |
| `scripts\riftreader-mcp-dashboard.cmd --self-test --json` | Passed. |
| Dashboard HTML smoke on loopback port `8790` | Passed. |
| `git --no-pager diff --check` | Passed; only LF-to-CRLF warnings from Git. |

## Official docs alignment

OpenAI Developer Mode docs currently confirm this lane is valid for ChatGPT Web/Desktop: Developer Mode apps can be created from remote MCP servers, supported protocols include SSE and streaming HTTP, Authentication can be `No Authentication`, app details can refresh tool descriptors, and ChatGPT respects the MCP `readOnlyHint` annotation for read-only detection.

Docs used: `https://developers.openai.com/api/docs/guides/developer-mode#how-to-use`.

## Safe next action

1. Start the read-only MCP server outside Codex:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-mcp.cmd --serve --tool-profile public-read-only --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com
```

2. Fix/verify Caddy + router/Cloudflare so `https://mcp.360madden.com/mcp` forwards to `http://127.0.0.1:8770/mcp` without Cloudflare 403/502.
3. Re-run:

```cmd
scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json
```

4. In ChatGPT Web/Desktop Developer Mode, create/update app `rift-mcp` with Server URL `https://mcp.360madden.com/mcp`, Authentication `No Authentication`.
5. Fill and record the Phase 0 proof template after ChatGPT confirms the 5 read-only tools and successfully calls `health`, `get_repo_status`, and either `get_latest_handoff` or `get_workflow_control_summary`.

## Boundaries

No public route was fixed from Codex, no ChatGPT app was registered, no RIFT input was sent, no CE/x64dbg was used, no provider repos were written, and no push was performed.
