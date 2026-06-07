# 2026-06-07 23:35 UTC - Cloudflare proof-flow alignment handoff

## Verdict

The non-Codex ChatGPT MCP lane is now aligned around the canonical Cloudflare named Tunnel route in code, tests, docs, and operator-facing status text.

Current route:

```text
ChatGPT Web/Desktop
-> https://mcp.360madden.com/mcp
-> Cloudflare named Tunnel riftreader-mcp-360madden
-> Cloudflared Windows service / connector
-> http://127.0.0.1:8770/mcp
-> RiftReader ChatGPT MCP adapter
```

## Current repo state

| Item | Value |
|---|---|
| Current commit | `2a17a8f99ab552fc54937464125010cdf0ac4914` |
| Branch | `main` |
| Upstream | `origin/main` |
| Git status after push | Clean and synced |
| Route proof template mode | `cloudflare-named-tunnel` |
| Route proof URL | `https://mcp.360madden.com/mcp` |
| Legacy CLI alias retained | `--manual-public-ip-plan` |
| Caddy/router | Deprecated legacy context only; not active route |

## What changed in the latest slice

| Area | Change |
|---|---|
| Trial recorder | Current proof template now emits `connectionMode=cloudflare-named-tunnel` and `publicMcpUrl=https://mcp.360madden.com/mcp`. |
| Proof validation | Current proof replay fails closed on retired tunnel hosts and non-domain-route proof URLs. |
| Workflow state | Fresh proof-input template detection now expects `cloudflare-named-tunnel`. |
| Mission Control / router text | Operator-facing recommendations now say Cloudflare named Tunnel, not manual external-IP/Caddy/router. |
| Docs | Current workflow, final readiness, and 50-stage plan now match Cloudflare named Tunnel as the canonical route. |
| Tests | MCP proof, phase, mission-control, workflow-state, and docs tests were updated for the Cloudflare proof contract. |

## Validation and CI

| Check | Result |
|---|---|
| `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_workflow_state scripts.test_mcp_final_readiness scripts.test_mcp_phase1_completion scripts.test_mcp_phase2_status scripts.test_mcp_proof_replay scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_chatgpt_mcp_workflow_docs` | Passed: 100 tests |
| `cmd /c scripts\riftreader-chatgpt-trial-recorder.cmd --self-test --json` | Passed |
| `cmd /c scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json` | Wrote current template |
| `cmd /c scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json` | Passed, activePath `cloudflare-named-tunnel` |
| `cmd /c scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json` | Passed, public MCP initialize HTTP 200 |
| `pre-commit run --all-files --show-diff-on-failure` | Passed |
| GitHub `.NET build and test` for `2a17a8f` | Passed on rerun attempt 2; attempt 1 had a transient `PowerShellMovementBackendTests` timeout that passed locally and on rerun |
| GitHub `RiftReader Policy` for `2a17a8f` | Passed |

Latest generated local proof template:

```text
.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json
```

It contains:

```json
{
  "connectionMode": "cloudflare-named-tunnel",
  "publicMcpUrl": "https://mcp.360madden.com/mcp"
}
```

## Current blockers

`cmd /c scripts\riftreader-mcp-final.cmd --status --compact-json` is still expected to be blocked because actual ChatGPT-side proof has not been refreshed under the new Cloudflare proof contract.

Primary blockers:

| Blocker | Meaning |
|---|---|
| `phase2:not-ready` | Phase 2 cannot pass until actual-client proof replays under current rules. |
| `proof:replay-failed:connection-mode-invalid:None` | Latest historical proof is too old/legacy and does not contain the new current connection mode. |
| `proof:replay-failed:proof-url-uses-retired-tunnel-host` | Historical proof references a retired `trycloudflare.com` URL. |
| `proof:replay-failed:public-mcp-url-not-domain-route:'https://...trycloudflare.com/mcp'` | Current proof must use `https://mcp.360madden.com/mcp`. |
| `proof:stale` | Actual-client proof is outside the 24-hour freshness budget. |

## Safe next command

Use the already-generated template, fill it with actual ChatGPT Web/Desktop Developer Mode observations, then check it read-only before recording:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input ".riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json" --json
```

If the check passes, record it:

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-chatgpt-trial-recorder.cmd --record --input ".riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json" --json
```

## Hard boundaries still in force

- Do not start OpenAI Secure MCP Tunnel or `trycloudflare.com` quick tunnels for this lane.
- Do not recreate Caddy/router/direct-public-IP forwarding.
- Do not count Codex-side local calls as final non-Codex ChatGPT proof.
- Do not expose shell, Git mutation, RIFT input, CE/x64dbg, provider writes, or broad filesystem tools through the public no-auth MCP app.
- Do not stop Caddy from Codex unless the operator explicitly approves cleanup; it is currently legacy noise, not the active route.
