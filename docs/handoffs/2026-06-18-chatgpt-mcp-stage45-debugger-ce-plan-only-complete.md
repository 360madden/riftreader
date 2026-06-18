# ChatGPT MCP Stage 45 debugger/CE plan-only complete

Date: 2026-06-18
Branch: `main`
Base before slice: `e018a3f`

## Result

Stage 45 is complete-local. The full ChatGPT MCP surface is now expected to be
39 tools with `plan_debugger_ce_action` added after the Stage 43 live-control
execution boundary.

## What changed

- Added `tools/riftreader_workflow/debugger_ce_plan.py`.
- Exposed `plan_debugger_ce_action` through
  `tools/riftreader_workflow/riftreader_chatgpt_mcp.py`.
- Updated canonical tool surface in `tools/riftreader_workflow/mcp_tool_surface.py`.
- Updated docs for the 39-tool contract, Stage 45 status, final-readiness rules,
  and debugger/CE static-first boundaries.
- Added `scripts/test_debugger_ce_plan.py` and updated MCP/doc tests.

## Safety boundary

The new tool is plan-only and writes ignored artifacts under:

```text
.riftreader-local\riftreader-chatgpt-mcp\debugger-ce-plans\*
```

It must not and did not launch or attach x64dbg, start Cheat Engine, set
breakpoints/watchpoints, read or write target memory, send RIFT input, promote
truth, write providers, or expose generic shell/file tools.

Required safety truth remains:

```yaml
movementSent: false
inputSent: false
noCheatEngine: true
x64dbgAttach: false
debuggerAttached: false
breakpointsSet: false
watchpointsSet: false
targetMemoryBytesWritten: false
providerWrites: false
savedVariablesUsedAsLiveTruth: false
```

## Validation run before commit

```text
python -m py_compile tools\riftreader_workflow\debugger_ce_plan.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\mcp_tool_surface.py scripts\test_debugger_ce_plan.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py
python -m unittest scripts.test_debugger_ce_plan scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs
python -m unittest scripts.test_debugger_ce_plan scripts.test_live_control_plan scripts.test_chatgpt_mcp_workflow_docs scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_final_readiness scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_stage38_consideration
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call plan_debugger_ce_action --arguments-json {"actionKind":"static-review","question":"Review tracked static notes only","staticEvidence":{"source":"unit-smoke"},"dryRun":true} --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json
git --no-pager diff --check
```

Observed results:

- Targeted Stage45/MCP/doc tests: 108 tests passed.
- Broader MCP regression set: 177 tests passed.
- SDK registration validation: passed, 39 registered tools, `plan_debugger_ce_action` has `readOnlyHint=false`, `destructiveHint=false`, `openWorldHint=true`.
- Direct `plan_debugger_ce_action` smoke wrote an ignored plan artifact and reported `inputSent=false`, `movementSent=false`, `noCheatEngine=true`, and `x64dbgAttach=false`.
- `git diff --check`: passed; CRLF normalization warnings only.

## Post-commit refresh required

After committing/pushing this slice, restart the local HTTP MCP runtime so the
loaded tool surface changes from 38 to 39, then refresh actual-client proof for
`https://mcp.360madden.com/mcp` and rerun final readiness.

## Next stage

Stage 46 is next: a debugger/CE gated-assist boundary. It should remain
fail-closed before attach unless a separate current-turn explicit approval and
crash-risk gate are present. No CE/x64dbg attach is authorized by this handoff.
