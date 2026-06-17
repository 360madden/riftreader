# 2026-06-17 - MCP runtime-recovery tool bundle complete-local

## Summary

Implemented the next 5-tool non-Codex ChatGPT MCP runtime-recovery bundle on top of the operational proof tools. The full MCP profile is now 33 tools and the public read-only profile is now 13 tools.

## What changed

| Area | Current truth |
|---|---|
| New tools | `get_tool_surface_diff`, `run_mcp_restart_preflight`, `restart_mcp_runtime`, `get_tunnel_status`, `get_chatgpt_connector_setup_packet`. |
| Runtime restart | Restart is split into read-only exact-PID preflight and approval-token gated scheduling; it verifies PID and command-line SHA-256 before stopping anything. |
| Runtime status | `mcp_server_status` now treats `mcp_runtime_control.py`, proof replay, final readiness, and trial recorder code as runtime-freshness dependencies. |
| Tunnel status | `get_tunnel_status` performs a real public MCP `initialize` POST to `https://mcp.360madden.com/mcp`; it does not start or mutate Cloudflare. |
| Connector setup | `get_chatgpt_connector_setup_packet` returns the non-Codex setup facts: Server URL `https://mcp.360madden.com/mcp`, Authentication `No Authentication`, expected 33 tools, and proof checklist. |
| Root launcher | `START_RIFTREADER_CHATGPT_MCP.cmd` banner now says full 33-tool profile. |

## Validation run

| Check | Result |
|---|---|
| Python syntax | Passed for touched MCP/runtime modules and tests. |
| Focused MCP suite | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_server_status scripts.test_bounded_repo_commands scripts.test_chatgpt_mcp_workflow_docs scripts.test_mcp_final_readiness scripts.test_mcp_workflow_state scripts.test_mcp_phase2_status scripts.test_mcp_phase1_completion scripts.test_mcp_proof_replay scripts.test_mcp_mission_control scripts.test_mcp_control_center` -> 216 tests OK. |
| SDK full profile | Passed: 33 tools. |
| SDK public read-only profile | Passed: 13 tools. |
| Guarded restart | Passed after fixing Windows PowerShell SHA and launcher quoting issues; stale 23-tool runtime was replaced and then restarted again through `restart_mcp_runtime`. |
| Public tunnel status | Passed: Cloudflare service is present and public MCP `initialize` succeeds through `https://mcp.360madden.com/mcp`. |
| `git diff --check` | Passed after trimming EOF blank lines. |

## Current blockers

| Blocker | Meaning |
|---|---|
| Actual-client proof stale | Latest proof artifact is still a 20-tool ChatGPT observation; current expected full surface is 33 tools. |
| Final readiness | Cannot pass until a fresh actual ChatGPT Web/Desktop proof records 33 tool names and 33 output schemas. |

## Safety

No live RIFT input, movement, `/reloadui`, screenshot-key input, CE/x64dbg, provider repo writes, proof/current-truth promotion, branch rewrite, force push, or destructive cleanup was performed. The only process mutation was the operator-authorized guarded restart of the verified current MCP backend PID.

## Next actions

1. Refresh/reconnect the ChatGPT Web/Desktop `rift-mcp` app after the pushed commit.
2. Confirm ChatGPT sees exactly 33 tools and output schemas.
3. Submit a fresh actual-client proof using `submit_actual_client_observation`.
4. Rerun `get_tool_surface_diff` and `get_final_readiness_status`.
5. Continue to Stage 38 only after explicit live-boundary approval.
