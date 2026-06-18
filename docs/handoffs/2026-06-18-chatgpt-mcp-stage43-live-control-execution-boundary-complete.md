# ChatGPT MCP Stage 43 live-control execution boundary complete-local

Date: 2026-06-18
Repo: `C:\RIFT MODDING\RiftReader`

## Verdict

Stage 43 is complete-local as a fail-closed live-control execution-boundary slice.
The new MCP tool is `execute_live_control_action`.

## What changed

- Added `tools/riftreader_workflow/live_control_execute.py`.
- Added `execute_live_control_action` to the full ChatGPT MCP tool surface.
- The tool reads one Stage 42 `plan_live_control_action` artifact, verifies target/approval binding, writes ignored run artifacts under `.riftreader-local\riftreader-chatgpt-mcp\live-control-runs\`, and fails closed before input while the live input backend remains unavailable.
- Updated tool annotations: `readOnlyHint=false`, `destructiveHint=true`, `openWorldHint=true`.
- Kept `execute_live_control_action` out of the public-read-only profile.
- Updated Stage 43 docs and stage plan metadata so Stage 44 is now the next safe stage.

## Safety

No live RIFT input was sent.

Required safety truth from validation:

- `inputSent=false`
- `movementSent=false`
- `reloaduiSent=false`
- `screenshotKeySent=false`
- `targetMemoryBytesWritten=false`
- `providerWrites=false`
- `x64dbgAttach=false`
- `noCheatEngine=true`
- `savedVariablesUsedAsLiveTruth=false`
- `liveInputBackendCalled=false`

The live input backend remains unavailable by design in this slice. Any future backend that can focus/capture/send/release/read back requires a separate reviewed local backend slice and must still respect the repo hard-stop policy for actual live input.

## Validation run

Passed:

```text
python -m py_compile tools\riftreader_workflow\live_control_execute.py tools\riftreader_workflow\live_control_plan.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_live_control_plan.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py
python -m unittest scripts.test_live_control_plan scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json
python -m unittest scripts.test_chatgpt_mcp_workflow_docs scripts.test_live_rift_state scripts.test_live_control_plan scripts.test_riftreader_chatgpt_mcp scripts.test_stage38_consideration
python -c "... execute_live_control_action missing-plan fail-closed assertion ..."
git diff --check
```

The direct CLI call `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call execute_live_control_action --json` returned `ok=false` and exit code 1 as expected for missing plan, with blocker `LIVE_PLAN_REQUIRED`, while `inputSent=false` and `movementSent=false`.

## Expected post-commit operational follow-up

After this slice is committed and pushed, the existing HTTP runtime at `127.0.0.1:8770` will be stale until restarted because the expected full tool surface changes from 37 to 38 tools. Refresh sequence:

1. `scripts\riftreader-mcp-server-status.cmd --json`
2. `run_mcp_restart_preflight`
3. `restart_mcp_runtime` with exact preflight facts/token
4. Confirm runtime reports 38 tools.
5. Refresh actual-client/public-route proof for the 38-tool surface.
6. Rerun `scripts\riftreader-mcp-final.cmd --status --compact-json`.

## Next stage

Stage 44: Debugger/CE static-first design.

Safe next work should remain docs/design/plan-only unless separately approved. Do not attach x64dbg, use Cheat Engine, set breakpoints/watchpoints, send live RIFT input, write providers, or promote proof/current-truth from Stage 44.
