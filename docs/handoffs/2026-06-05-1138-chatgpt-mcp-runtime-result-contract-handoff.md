# ChatGPT MCP runtime result-contract handoff — 2026-06-05 11:38 UTC

## Result

The RiftReader ChatGPT Web/Desktop MCP adapter now validates every tool handler
result against the minimum structuredContent contract before returning it to the
client or writing the sanitized audit event. Malformed handler payloads fail
closed as `TOOL_RESULT_CONTRACT_INVALID` instead of leaking ambiguous structured
content to ChatGPT.

## Root cause

The tool manifest and SDK/transport checks now require output schemas, but the
runtime adapter did not centrally verify that each local handler result included
the common required fields (`schemaVersion`, `kind`, `status`, and boolean
`ok`). A future handler edit could accidentally return malformed
structuredContent while still passing registration checks.

## Changed files

| Path | Change |
|---|---|
| `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` | Added `validate_tool_result_payload()` and fail-closed runtime enforcement in `call_tool()`. |
| `scripts/test_riftreader_chatgpt_mcp.py` | Added regression tests for malformed handler payload blocking and current health payload acceptance. |
| `docs/workflow/riftreader-chatgpt-mcp.md` | Documents runtime result-contract enforcement. |
| `docs/HANDOFF.md` | Adds this handoff to the top re-entry index. |

## Validation

| Command | Result |
|---|---|
| `python -m unittest scripts.test_riftreader_chatgpt_mcp` | Passed 58 tests in 3.080s. |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_local_artifact_bridge scripts.test_package_draft_review` | Passed 179 tests in 43.731s. |
| `python tools\riftreader_workflow\validation_ledger.py --tier targeted --command "python -m unittest ..."` | Passed at `.riftreader-local/validation-runs/20260605-114220-809119/summary.md` in 43.023s. |
| `scripts\riftreader-chatgpt-mcp.cmd --self-test --json` | Passed; `ok=true`, no blockers. |
| `scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json` | Passed; 10 registered tools. |

## Boundaries

No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider
writes, proof promotion, push, or remote mutation was performed.
