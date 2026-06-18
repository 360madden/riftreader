# ChatGPT MCP Stage 46 debugger/CE execution-boundary complete

Date: 2026-06-18
Branch: `main`
Base before slice: `dc5ef9b`

## Result

Stage 46 is complete-local. The full ChatGPT MCP surface is now expected to be
40 tools with `execute_debugger_ce_action` added after the Stage 45 debugger/CE
plan-only surface.

## What changed

- Added `tools/riftreader_workflow/debugger_ce_execute.py` as a Stage 46
  fail-closed execution-boundary helper.
- Exposed `execute_debugger_ce_action` through
  `tools/riftreader_workflow/riftreader_chatgpt_mcp.py`.
- Updated canonical tool surface in `tools/riftreader_workflow/mcp_tool_surface.py`.
- Added focused Stage 46 tests in `scripts/test_debugger_ce_execute.py`.
- Updated MCP workflow docs, final-readiness docs, and the root handoff pointer
  for the 40-tool contract.

## Safety boundary

The new tool writes ignored artifacts under:

```text
.riftreader-local\riftreader-chatgpt-mcp\debugger-ce-runs\*
```

It verifies one Stage 45 debugger/CE plan, one-shot approval phrase, exact target
gate when applicable, and crash-risk/static-first preconditions. In this slice
it still fails closed before attach because no debugger backend is available.

Required safety truth remains:

```yaml
movementSent: false
inputSent: false
noCheatEngine: true
x64dbgAttach: false
debuggerAttached: false
cheatEngineConnected: false
breakpointsSet: false
watchpointsSet: false
targetMemoryBytesRead: false
targetMemoryBytesWritten: false
targetMemoryScanned: false
providerWrites: false
savedVariablesUsedAsLiveTruth: false
```

## Validation to run

```text
python -m py_compile tools\riftreader_workflow\debugger_ce_execute.py tools\riftreader_workflow\debugger_ce_plan.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\mcp_tool_surface.py scripts\test_debugger_ce_execute.py scripts\test_debugger_ce_plan.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py
python -m unittest scripts.test_debugger_ce_execute scripts.test_debugger_ce_plan scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json
git --no-pager diff --check
```

## Post-commit refresh required

After committing/pushing this slice, restart or refresh the local HTTP MCP
runtime so the loaded tool surface changes from 39 to 40, then refresh actual
ChatGPT Web/Desktop proof for `https://mcp.360madden.com/mcp` and rerun final
readiness. Local SDK/server status is not a substitute for that actual-client
proof.

## Next stage

Stage 47 is next: role/auth hardening while preserving the current personal No
Authentication flow. No CE/x64dbg attach is authorized by this handoff.
