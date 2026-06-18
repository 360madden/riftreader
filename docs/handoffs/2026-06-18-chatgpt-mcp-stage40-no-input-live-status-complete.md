# 2026-06-18 - ChatGPT MCP Stage 38-40 no-input live status complete-local

## Result

Stages 38-40 of the non-Codex ChatGPT MCP plan are implemented locally as a
safe read-only/no-input live RIFT status surface. No live game input, movement,
focus, capture, ProofOnly run, proof promotion, provider write, CE, or x64dbg
action was performed during implementation or validation.

| Item | Current truth |
|---|---|
| Tool surface | Full profile is now `36` tools. Added `get_live_rift_readonly_state`, `get_live_target_identity_gate`, and `get_live_no_input_proof_status`. |
| Stage 38 | `get_live_rift_readonly_state` exposes read-only target/status facts only after the exact target identity gate passes. |
| Stage 39 | `get_live_target_identity_gate` checks fresh proof-anchor status, PID, HWND, process start, module base, and duplicate RIFT window detection. |
| Stage 40 | `get_live_no_input_proof_status` exposes proof/readback summaries only after the identity gate passes. |
| Live target smoke | Read-only discovery found PID `130540`, HWND `0x9310EA`, process `rift_x64`, title `RIFT`, module base `0x7FF778CD0000`. |
| Proof freshness | `docs\recovery\current-proof-anchor-readback.json` was accepted as fresh under the 24-hour no-input status budget; latest ProofOnly status is `passed-proof-only` with `movementSent=false`. |
| Runtime | HTTP MCP runtime refreshed to full profile PID `157156`; `scripts\riftreader-mcp-server-status.cmd --json` reports `running-current`, source-fresh, and `36/36` observed tools. |
| Stdio counterpart | One stale local/Codex stdio counterpart remains a warning only; it is not the Cloudflare HTTP runtime. |
| Final readiness | Blocked as expected until a new actual ChatGPT Web/Desktop proof observes the 36-tool surface. Pre-commit final status also reported `git:dirty-worktree`. |

## Files changed

| Path | Purpose |
|---|---|
| `tools\riftreader_workflow\live_rift_state.py` | New read-only Stage 38-40 helper module. |
| `tools\riftreader_workflow\riftreader_chatgpt_mcp.py` | MCP tool specs, dispatch, SDK wrappers, control-plan status, and Stage 41 next-state updates. |
| `tools\riftreader_workflow\mcp_tool_surface.py` | Canonical 36-tool surface constants. |
| `scripts\get-rift-window-targets.ps1` | Adds read-only `ModuleBaseAddressHex` and `ModulePath` to target discovery output. |
| `scripts\test_live_rift_state.py` | New focused tests for fresh/stale/mismatched gates and no-input proof withholding. |
| `scripts\test_riftreader_chatgpt_mcp.py` | Manifest, annotation, dispatch, schema, and plan tests updated for 36 tools. |
| `docs\workflow\*.md` | Stage plan, final-readiness, live-control design, and MCP adapter docs updated to Stage 40 complete-local / 36-tool contract. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\live_rift_state.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\mcp_tool_surface.py tools\riftreader_workflow\stage38_consideration.py scripts\test_live_rift_state.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_stage38_consideration.py scripts\test_chatgpt_mcp_workflow_docs.py` | Passed. |
| `python -m unittest scripts.test_live_rift_state scripts.test_riftreader_chatgpt_mcp scripts.test_stage38_consideration scripts.test_chatgpt_mcp_workflow_docs` | Passed: `112` tests. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json` | Passed: `36` registered tools. |
| `cmd /c scripts\get-rift-window-targets.cmd -Json` | Passed read-only target discovery; no focus/click/key input. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_live_target_identity_gate --json` | Passed; exact target gate ok. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_live_no_input_proof_status --json` | Passed; proof summary exposed behind gate. |
| `cmd /c scripts\riftreader-mcp-server-status.cmd --json` | Passed after runtime refresh: full profile `36/36`, source-fresh. |
| `cmd /c scripts\riftreader-mcp-final.cmd --status --compact-json` | Blocked as expected by dirty worktree and stale actual-client proof/tool-surface mismatch (`33` observed vs `36` expected). |
| `git diff --check` | Passed; only line-ending warnings from Windows autocrlf. |

## Remaining blocker

Actual-client proof must be refreshed from non-Codex ChatGPT Web/Desktop against
`https://mcp.360madden.com/mcp` using No Authentication. The proof must record
36 tool names, 36 output schemas, `clientTransportStatus=tool-call-succeeded`,
and `healthCallSucceeded=true`. Do not treat local SDK/server status or a Codex
stdio wrapper as a substitute.
