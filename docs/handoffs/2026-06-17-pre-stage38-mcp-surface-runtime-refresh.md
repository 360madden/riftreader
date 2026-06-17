# 2026-06-17 - Pre-Stage-38 surface/runtime refresh

## Current truth

| Item | Evidence |
|---|---|
| Scope | Safe pre-Stage-38 cleanup only; Stage 38 was not started. |
| Commits pushed | `d734640` refreshed stale proof-surface wording. `657bba5` added `latestMcpHandoffPath` to readiness/mission-control status. `0ee43ba`/`1f17f3b` refreshed and discovery-aligned this handoff. |
| CI | Current head `1f17f3be16d54238e389e6582517ffc2799bd25c` passed `.NET build and test` run `27711471918` and `RiftReader Policy` run `27711471903`. |
| Runtime | Guarded exact-PID restart replaced stale PID `134792` with PID `132248`; `mcp_server_status.py --json` reports `running-current`, source-fresh, full profile, 33/33 tools, and no stdio counterparts. |
| Public route | Stage 38 consideration reports Cloudflare named Tunnel route `https://mcp.360madden.com/mcp` passed. |
| Client transport | Direct `mcp__riftreader.health` probe from this session returned `Transport closed`; refresh/reconnect the ChatGPT MCP app before recording proof. |
| Final readiness | Still blocked: latest actual-client proof is 20-tool evidence and lacks `clientTransportStatus=tool-call-succeeded` plus `healthCallSucceeded=true`. |
| Stage 38 | Still blocked/inactive: `stage38Started=false`, `stage38Active=false`, and explicit live-boundary approval remains gated behind final readiness. |
| Latest proof template | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-174546Z\proof-input.json`. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\mcp_dashboard.py scripts\test_mcp_dashboard.py scripts\test_chatgpt_mcp_workflow_docs.py` | Passed |
| `python -m unittest scripts.test_mcp_dashboard scripts.test_chatgpt_mcp_workflow_docs` | 14 tests passed |
| `pre-commit run --files tools\riftreader_workflow\mcp_dashboard.py scripts\test_mcp_dashboard.py docs\workflow\riftreader-chatgpt-mcp-live-control-design.md docs\workflow\riftreader-chatgpt-mcp-50-stage-plan.md scripts\test_chatgpt_mcp_workflow_docs.py` | Passed |
| `python -m py_compile tools\riftreader_workflow\mcp_final_readiness.py tools\riftreader_workflow\mcp_mission_control.py scripts\test_mcp_final_readiness.py scripts\test_mcp_mission_control.py` | Passed |
| `python -m unittest scripts.test_mcp_final_readiness scripts.test_mcp_mission_control` | 37 tests passed |
| `pre-commit run --files tools\riftreader_workflow\mcp_final_readiness.py tools\riftreader_workflow\mcp_mission_control.py scripts\test_mcp_final_readiness.py scripts\test_mcp_mission_control.py` | Passed |
| `python tools\riftreader_workflow\mcp_ci_status.py --status --json` | Passed for current head `1f17f3b` |
| `python tools\riftreader_workflow\mcp_server_status.py --json` | Passed: PID `132248`, 33/33, source-fresh |
| `scripts\riftreader-stage38-consideration.cmd --status --compact-json` | Blocked as intended on final-readiness/proof and live-boundary approval |

## Next required proof step

Fill the latest proof template with actual ChatGPT Web/Desktop observations and check it read-only before recording:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-174546Z\proof-input.json --json
```

Do not advance Stage 38 until this actual-client proof passes, final readiness passes, and the explicit `STAGE38-LIVE-BOUNDARY-APPROVED` token is intentionally supplied.
