# 2026-06-17 - Stage 38 consideration gate bounded command

# **⚠️ BLOCKED-SAFE — STAGE 38 IS NOT ACTIVE**

This handoff records the safe local work completed before Stage 38 can even be
considered. It intentionally does **not** start live RIFT tooling, send input,
attach CE/x64dbg, write provider repos, promote proof/current truth, or add a
new MCP tool.

## Current truth

| Area | Evidence |
|---|---|
| Stage 38 | Not active. It remains parked behind final readiness plus the explicit live-boundary token `STAGE38-LIVE-BOUNDARY-APPROVED`. |
| Gate helper | `scripts\riftreader-stage38-consideration.cmd --status --compact-json` checks runtime freshness, public route, final readiness, and live-boundary approval. |
| Bounded command | `stage38_consideration_status` is in the bounded command registry, so the existing `run_bounded_repo_command` MCP tool can run the gate without adding another MCP tool. |
| Approval packet writer | `stage38_approval_packet` writes a fail-closed approval packet under ignored `.riftreader-local` artifacts through the existing bounded-command surface. It does not start Stage 38. |
| Commits | `9132605` added the Stage 38 consideration gate. `b886e11` exposed that gate as a bounded command. `75efec9` added the fail-closed approval-packet writer. |
| Runtime restart | Stale HTTP PID `130316` was restarted through the exact-PID guarded preflight after `75efec9`. Fresh PID `129620` reports `running-current`, source-fresh, full profile, and 33/33 tools. |
| Public route | The Stage 38 gate reports the Cloudflare named route `https://mcp.360madden.com/mcp` as passed. |
| Tool surface | Source vs manifest and source vs runtime pass at 33/33 tools. Latest actual-client proof is still old 20-tool evidence. |
| Final readiness | Still blocked until current-head CI is green and actual ChatGPT Web/Desktop records/replays a fresh 33-tool proof. |
| Stage 38 gate status | `blocked`; `stage38Started=false`, `stage38Active=false`, and `stage38ToolSurfaceChanged=false`. |

## Remaining blockers before Stage 38 can be considered

| # | Blocker | Meaning | Resolution |
|---:|---|---|---|
| 1 | Actual-client proof mismatch | The latest recorded ChatGPT proof saw 20 tools, but the current source/runtime surface is 33 tools. | Refresh/reconnect the ChatGPT Web/Desktop MCP app and record a new 33-tool proof. |
| 2 | Current-head CI | CI must pass for the latest pushed commit before final readiness can pass. | Wait for `.NET build and test` and `RiftReader Policy` on current HEAD. |
| 3 | Explicit live-boundary approval | Even after final readiness passes, Stage 38 remains blocked without the exact approval token. | Only provide/use `STAGE38-LIVE-BOUNDARY-APPROVED` after reviewing the Stage 38 approval packet. |

## Commands verified

```cmd
python tools\riftreader_workflow\bounded_repo_commands.py --self-test --json
python tools\riftreader_workflow\bounded_repo_commands.py --plan stage38_consideration_status --json
python -m unittest scripts.test_bounded_repo_commands scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs scripts.test_stage38_consideration
python -m py_compile tools\riftreader_workflow\bounded_repo_commands.py tools\riftreader_workflow\stage38_consideration.py scripts\test_bounded_repo_commands.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_stage38_consideration.py
pre-commit run --files tools\riftreader_workflow\bounded_repo_commands.py scripts\test_bounded_repo_commands.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py docs\workflow\riftreader-chatgpt-mcp-bounded-command-design.md
git diff --check
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call run_mcp_restart_preflight --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call restart_mcp_runtime --arguments-json <exact preflight facts> --json
python tools\riftreader_workflow\mcp_server_status.py --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_tool_surface_diff --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_final_readiness_status --json
scripts\riftreader-stage38-consideration.cmd --status --compact-json
python tools\riftreader_workflow\bounded_repo_commands.py --run stage38_consideration_status --json
scripts\riftreader-stage38-consideration.cmd --write-approval-packet --json
python tools\riftreader_workflow\bounded_repo_commands.py --run stage38_approval_packet --json
```

## Actual-client proof refresh packet

| Item | Value |
|---|---|
| ChatGPT Server URL | `https://mcp.360madden.com/mcp` |
| Auth | `No Authentication` |
| Expected profile | Full final proof surface |
| Expected tool count | `33` |
| Fresh proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json` |
| Read-only check | `scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json --json` |
| Record after filling real ChatGPT observations | `scripts\riftreader-chatgpt-trial-recorder.cmd --record --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-155237Z\proof-input.json --json` |

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Wait for current-head CI to finish. | Final readiness cannot pass while CI is pending. |
| 2 | Refresh/reconnect the ChatGPT Web/Desktop MCP app for `https://mcp.360madden.com/mcp`. | Forces the actual client to rescan the current 33-tool surface. |
| 3 | From ChatGPT, call `health`. | Confirms the actual client sees the current server and reported tool count. |
| 4 | From ChatGPT, call `get_mcp_runtime_status`. | Confirms runtime freshness from the non-Codex client path. |
| 5 | From ChatGPT, call `get_tool_surface_diff`. | Confirms the proof mismatch is visible and not a local-only assumption. |
| 6 | Confirm ChatGPT reports all 33 tool names and output schemas. | This is the missing proof fact. |
| 7 | Run the harmless proposal/draft/review/dry-run proof flow from ChatGPT. | Keeps the package-loop safety proof current. |
| 8 | Fill and check the fresh proof input. | Prevents recording incomplete or stale facts. |
| 9 | Record the checked actual-client proof. | Creates replayable evidence for Phase 2/final readiness. |
| 10 | Rerun the Stage 38 consideration gate after final readiness passes. | Separates proof completion from the later live-boundary approval decision. |
