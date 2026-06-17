# 2026-06-17 - Pre-Stage-38 proof refresh gate started

# **⚠️ BLOCKED-SAFE — STAGE 38 IS NOT ACTIVE**

This handoff records the safe pre-Stage-38 work completed before live RIFT
read-only tooling is considered. The local MCP/runtime side is current; the
remaining hard blocker is a fresh actual ChatGPT Web/Desktop observation for
the current 33-tool surface.

## Current truth

| Area | Evidence |
|---|---|
| Git | `main` is synced with `origin/main` at `15349ce126f55a90a6c8fd6185e0c08df6cd05dd` (`Add MCP runtime recovery tools`). |
| CI | Current-head `.NET build and test` and `RiftReader Policy` workflows passed for `15349ce126f55a90a6c8fd6185e0c08df6cd05dd`. |
| Runtime | `get_mcp_runtime_status` reported `status=running-current` for PID `53740`, full profile, source freshness passed. |
| Tunnel | `get_tunnel_status` reported Cloudflared service running and public MCP initialize passed at `https://mcp.360madden.com/mcp`. |
| Tool surface | Source/runtime expected 33 tools; latest actual-client proof still records 20 tools. |
| Local trial readiness | Fresh artifact: `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260617T155223Z-trial-readiness.json`. |
| Public route plan | Refreshed artifact: `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260617T155406Z-manual-public-ip-plan.json`. |
| Proof template | Fresh final-33-tool template: `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json`. |
| Final readiness | Still blocked: `phase2:not-ready` plus proof replay failures because the latest proof is 20-tool evidence, not 33-tool evidence. |

## Root cause / blocker

| Blocker | Plain meaning | Owner |
|---|---|---|
| Actual-client proof mismatch | ChatGPT's latest saved proof saw only 20 tools. The MCP server now exposes 33 tools, so final readiness correctly refuses to trust the old proof. | Actual ChatGPT Web/Desktop operator proof refresh |

This is not an MCP-server-running problem right now: the local server and
Cloudflare route are running and current. The blocker is that the actual
ChatGPT client has not yet produced a fresh 33-tool observation.

## Commands run in this pre-Stage-38 pass

```cmd
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_mcp_runtime_status --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_tunnel_status --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_tool_surface_diff --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_actual_client_proof_status --json
scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
scripts\riftreader-mcp-phase2.cmd --status --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_final_readiness_status --json
scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json
scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host mcp.360madden.com --json
```

## Actual-client proof refresh packet

| Item | Value |
|---|---|
| ChatGPT Server URL | `https://mcp.360madden.com/mcp` |
| Auth | `No Authentication` |
| Expected profile | Full final proof surface |
| Expected tool count | `33` |
| First ChatGPT-side calls | `health`, `get_mcp_runtime_status`, `get_tool_surface_diff`, `get_tunnel_status`, `get_actual_client_proof_status` |
| Fillable proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json` |
| Read-only check command | `scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json --json` |
| Record command after the file is filled with real ChatGPT observations | `scripts\riftreader-chatgpt-trial-recorder.cmd --record --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json --json` |

## Do not do these before Stage 38

| Do not | Why |
|---|---|
| Do not treat the saved ChatGPT app/connector entry as the running backend. | The saved entry is only configuration; it does not start the local MCP server or Cloudflared. |
| Do not substitute local `list_tools`, SDK validation, or tunnel initialize for actual-client proof. | Final readiness requires evidence from ChatGPT Web/Desktop. |
| Do not move into Stage 38 live RIFT read-only tooling yet. | Final readiness and explicit live-boundary approval are both still required. |
| Do not send RIFT input, attach CE/x64dbg, write provider repos, or promote proof/current truth. | These are separate hard gates. |

## Criteria before Stage 38 can even be considered

| # | Required evidence | Current state |
|---:|---|---|
| 1 | Git clean and synced with origin. | Passed at this handoff. |
| 2 | Current-head CI green. | Passed at this handoff. |
| 3 | Local MCP runtime is `running-current` and source-fresh. | Passed at this handoff. |
| 4 | Public Cloudflare named Tunnel route initializes at `https://mcp.360madden.com/mcp`. | Passed at this handoff. |
| 5 | Trial readiness/proposal smoke artifacts are fresh. | Passed at this handoff. |
| 6 | Actual ChatGPT Web/Desktop observes exactly 33 tools and output schemas. | **Blocked — latest proof is 20-tool evidence.** |
| 7 | Filled proof input passes `--check-input`. | **Blocked until actual ChatGPT facts are filled.** |
| 8 | Fresh proof is recorded and replay passes. | **Blocked until actual ChatGPT proof is recorded.** |
| 9 | `scripts\riftreader-mcp-phase2.cmd --status --json` passes. | **Blocked by proof replay.** |
| 10 | `get_final_readiness_status` passes. | **Blocked by Phase 2/proof replay.** |

Only after all ten items pass should the workflow draft a Stage 38 approval
packet. Stage 38 implementation still requires explicit live-boundary approval.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Refresh/reconnect the ChatGPT Web/Desktop MCP app for `https://mcp.360madden.com/mcp`. | Forces ChatGPT to rescan the current 33-tool surface. |
| 2 | From ChatGPT, call `get_mcp_runtime_status`. | Confirms the actual client sees the current local backend. |
| 3 | From ChatGPT, call `get_tool_surface_diff`. | Confirms source/runtime/client proof drift is visible from the client side. |
| 4 | From ChatGPT, confirm exactly 33 tools and output schemas. | This is the missing final-readiness fact. |
| 5 | From ChatGPT, run the harmless proposal/draft/review/dry-run proof flow. | Preserves the repo-write safety proof for the current tool surface. |
| 6 | Fill the fresh proof template with only the observed ChatGPT facts. | Avoids inventing proof and keeps replay trustworthy. |
| 7 | Run the proof `--check-input` command. | Catches missing booleans/IDs before recording. |
| 8 | Record the checked proof with `--record`. | Creates the replayable actual-client proof artifact. |
| 9 | Rerun Phase 2 and final readiness. | Verifies the gate is truly ready before any Stage 38 discussion. |
| 10 | Write the final pre-Stage-38 approval packet only after gates pass. | Keeps live RIFT work separated from local MCP readiness. |
