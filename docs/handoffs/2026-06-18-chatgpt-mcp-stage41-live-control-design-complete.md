# 2026-06-18 - ChatGPT MCP Stage 41 live-control design complete-local

## Result

Stage 41 is complete-local as a design-only live-control boundary. No new MCP
tool was exposed, the full non-Codex ChatGPT MCP proof contract remains `36`
tools, and no live game input, movement, focus, capture, ProofOnly run, proof
promotion, provider write, CE, or x64dbg action was performed.

| Item | Current truth |
|---|---|
| Stage 41 | Complete-local: `docs\workflow\riftreader-chatgpt-mcp-live-control-design.md` now defines the non-executing live-control design contract. |
| Tool surface | Still `36` tools; Stage 41 intentionally did not add `plan_live_control_action` or any execution endpoint. |
| Next stage | Stage 42: plan-only live-control planning/dry-run tool that still sends no input. |
| Design separation | The contract separates `no-input-read`, `ui-action`, `displacement-stimulus`, `movement-control`, and `proof-only` risk classes. |
| Safety invariant | Stage 41 requires `inputSent=false`, `movementSent=false`, `reloaduiSent=false`, `screenshotKeySent=false`, `targetMemoryBytesWritten=false`, `x64dbgAttach=false`, `noCheatEngine=true`, `providerWrites=false`, `truthPromotionPerformed=false`, and `savedVariablesUsedAsLiveTruth=false`. |
| Control-plan metadata | `get_workflow_control_plan` now reports current stage `42`, next stage `43`, and `futureCapabilityPolicy.status=live-control-dry-run-plan-next`. |
| Runtime | HTTP MCP runtime remains the full 36-tool local backend; actual-client proof still must be refreshed separately from ChatGPT Web/Desktop. |

## Files changed

| Path | Purpose |
|---|---|
| `docs\workflow\riftreader-chatgpt-mcp-live-control-design.md` | Promotes Stage 41 from draft to complete-local design contract and documents action taxonomy / future plan envelope. |
| `docs\workflow\riftreader-chatgpt-mcp-50-stage-plan.md` | Marks Stage 41 complete-local and Stage 42 as the next implementation boundary. |
| `tools\riftreader_workflow\riftreader_chatgpt_mcp.py` | Updates full-product control-plan metadata to Stage 42 current / Stage 43 next. |
| `scripts\test_chatgpt_mcp_workflow_docs.py` | Adds regression coverage for the non-executing Stage 41 design contract. |
| `scripts\test_riftreader_chatgpt_mcp.py` | Updates control-plan metadata expectations. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py` | Passed. |
| `python -m unittest scripts.test_chatgpt_mcp_workflow_docs scripts.test_riftreader_chatgpt_mcp` | Passed: `100` tests. |
| `python -m unittest scripts.test_live_rift_state scripts.test_riftreader_chatgpt_mcp scripts.test_stage38_consideration scripts.test_chatgpt_mcp_workflow_docs` | Passed: `114` tests. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json` | Passed. |
| `git diff --check` | Passed; only Windows CRLF warnings. |

## Remaining blocker

Final readiness still requires a fresh non-Codex ChatGPT Web/Desktop actual-client
proof against `https://mcp.360madden.com/mcp` using No Authentication. The proof
must observe the current 36-tool surface, include output schemas, and record
`clientTransportStatus=tool-call-succeeded` plus `healthCallSucceeded=true`.
