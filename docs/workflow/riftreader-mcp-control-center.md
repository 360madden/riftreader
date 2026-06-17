# RiftReader MCP Control Center

Status: localhost-only GUI for the non-Codex ChatGPT Web/Desktop MCP lane.

## Purpose

The Control Center is the polished browser GUI for operating the safe local
parts of the RiftReader ChatGPT MCP workflow:

- local MCP adapter run state;
- final-readiness and trial-readiness checks;
- Cloudflare named Tunnel/domain diagnostics;
- ChatGPT connector setup values;
- actual-client proof template helpers;
- recent allowlisted action results;
- managed adapter stdout/stderr tails.

It complements, but does not replace, ChatGPT Web/Desktop Developer Mode. The
actual ChatGPT connector still uses:

| Field | Value |
|---|---|
| Server URL | `https://mcp.360madden.com/mcp` |
| Authentication | `No Authentication` |
| Local backend | `http://127.0.0.1:8770/mcp` |

## Start the GUI

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-mcp-control-center.cmd --open
```

Default URL:

```text
http://127.0.0.1:8790/
```

Useful non-GUI checks:

```cmd
scripts\riftreader-mcp-control-center.cmd --self-test --json
scripts\riftreader-mcp-control-center.cmd --once-json
scripts\riftreader-mcp-server-status.cmd --json
```

Use `scripts\riftreader-mcp-server-status.cmd --json` before ChatGPT connector
debugging or proof collection. It distinguishes the current
`riftreader_chatgpt_mcp.py --serve` backend from a missing server, a foreign
listener, or the legacy tokenized HTTP MCP server. Only `status=running-current`
counts as the local backend dependency for this ChatGPT Web/Desktop lane.

## Layout

The GUI is organized into tabs:

| Tab | Role |
|---|---|
| Overview | One-screen backend, route, ChatGPT, proof, and recommended-action summary. |
| Server | Current backend dependency status, start/stop only for the local adapter process started by this GUI, plus copy-ready terminal commands. |
| Readiness | Final-gate, MCP trial-readiness, and Mission Control status. |
| Route & ChatGPT | Public URL, named tunnel, Cloudflare status, domain diagnostics, and connector checklist. |
| Proof | Current proof/template paths and final expected tool surface. |
| Validation | Local self-test, SDK validation, transport smoke, proposal smoke, and action history. |
| Logs & JSON | Managed adapter log tails and full status JSON. |
| Safety | Disabled endpoint model and allowlisted action registry. |

## Safety model

The Control Center is intentionally bounded:

- binds only to `127.0.0.1`;
- exposes no arbitrary shell endpoint;
- exposes no arbitrary filesystem endpoint;
- exposes no Git stage/commit/push/reset/clean endpoint;
- exposes no ChatGPT registration endpoint;
- exposes no Cloudflare mutation endpoint;
- exposes no RIFT input, movement, `/reloadui`, screenshot key, CE, or x64dbg endpoint;
- requires browser confirmation for start/stop actions;
- can stop only a tracked process whose command line is verified as
  `riftreader_chatgpt_mcp.py`.

The GUI can start the local Python MCP adapter on `127.0.0.1:8770`. It does not
start Cloudflared or edit the saved ChatGPT connector.

## Allowlisted action families

The backend accepts only fixed action keys. Unknown keys fail closed.

| Family | Examples |
|---|---|
| Server | `start_full_server`, `start_readonly_server`, `stop_managed_server` |
| Readiness | `final_gate`, `mcp_trial_readiness` |
| Route | `cloudflared_status`, `domain_diagnostics`, `route_plan` |
| Proof | `write_proof_template`, `check_latest_proof_template` |
| Validation | `local_self_test`, `sdk_validate`, `transport_smoke`, `proposal_smoke` |

Some actions write ignored local artifacts under `.riftreader-local` for
diagnostics/proof workflow continuity. They do not mutate Git.
