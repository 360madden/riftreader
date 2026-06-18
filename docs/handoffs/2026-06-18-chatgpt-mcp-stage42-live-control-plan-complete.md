# 2026-06-18 - ChatGPT MCP Stage 42 live-control plan-only tool complete-local

## Result

Stage 42 is complete-local as a plan-only live-control MCP surface. The full
non-Codex ChatGPT MCP proof contract is now `37` tools after adding
`plan_live_control_action`.

No live game input, movement, focus, capture, click, ProofOnly run, proof
promotion, provider write, CE, or x64dbg action was performed.

| Item | Current truth |
|---|---|
| Stage 42 | Complete-local: `plan_live_control_action` returns a bounded dry-run plan and writes ignored local plan artifacts. |
| Tool surface | Full profile intentionally moves from `36` to `37` tools. Public read-only profile does not expose `plan_live_control_action` because it writes ignored local artifacts. |
| Next stage | Stage 43: minimal live action tool, still gated on explicit execution approval and fresh exact-target proof before any input can be sent. |
| Plan artifacts | `.riftreader-local\riftreader-chatgpt-mcp\live-control-plans\*\plan.json` and `plan.md`. |
| Safety invariant | Stage 42 records `inputSent=false`, `movementSent=false`, `reloaduiSent=false`, `screenshotKeySent=false`, `targetMemoryBytesWritten=false`, `x64dbgAttach=false`, `noCheatEngine=true`, `providerWrites=false`, `truthPromotionPerformed=false`, and `savedVariablesUsedAsLiveTruth=false`. |

## Files changed

| Path | Purpose |
|---|---|
| `tools\riftreader_workflow\live_control_plan.py` | New Stage 42 classifier/planner that writes ignored local plan artifacts and never executes input. |
| `tools\riftreader_workflow\mcp_tool_surface.py` | Adds `plan_live_control_action` to the full 37-tool surface only. |
| `tools\riftreader_workflow\riftreader_chatgpt_mcp.py` | Wires the Stage 42 MCP tool, metadata, workflow-control plan, and FastMCP registration. |
| `scripts\test_live_control_plan.py` | Adds focused Stage 42 classification/artifact/safety tests. |
| `scripts\test_riftreader_chatgpt_mcp.py` | Updates manifest, annotations, workflow-control metadata, and SDK expectations for the 37-tool surface. |
| `scripts\test_chatgpt_mcp_workflow_docs.py` | Updates documentation regression tests for Stage 42 / 37 tools. |
| `docs\workflow\riftreader-chatgpt-mcp-50-stage-plan.md` | Marks Stage 42 complete-local and Stage 43 as the next implementation boundary. |
| `docs\workflow\riftreader-chatgpt-mcp-live-control-design.md` | Documents Stage 42 as implemented plan-only and keeps execution blocked. |
| `docs\workflow\riftreader-chatgpt-mcp.md` | Adds the new tool to the adapter docs and updates proof contract counts. |
| `docs\workflow\riftreader-chatgpt-mcp-final-readiness.md` | Updates final-readiness dependency text for the 37-tool contract. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\live_control_plan.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_live_control_plan.py scripts\test_riftreader_chatgpt_mcp.py` | Passed. |
| `python -m unittest scripts.test_live_control_plan scripts.test_riftreader_chatgpt_mcp` | Passed: `95` tests. |
| `python -m unittest scripts.test_chatgpt_mcp_workflow_docs scripts.test_live_control_plan scripts.test_riftreader_chatgpt_mcp` | Passed: `104` tests. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json` | Passed; FastMCP registered `37` tools with annotations and schemas. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call plan_live_control_action --arguments-json .riftreader-local\stage42-plan-args.json --json` | Passed; wrote ignored plan artifact and recorded no input/movement. |

## Remaining blockers before final readiness can be green

| Blocker | Required next safe action |
|---|---|
| Running HTTP MCP runtime still serves the old `36`-tool surface until restarted. | Restart only the verified current MCP runtime so `list_tools` and `health` report `37` tools. |
| Latest actual-client proof still replays the old `36`-tool surface. | Record fresh actual-client proof for the `37`-tool surface after runtime refresh. |
| Worktree is dirty until this slice is committed. | Commit this validated Stage 42 slice locally before final readiness proof. |

