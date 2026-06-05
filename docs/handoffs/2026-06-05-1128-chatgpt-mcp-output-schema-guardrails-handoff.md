# ChatGPT MCP output-schema guardrails handoff — 2026-06-05 11:28 UTC

## Result

The RiftReader ChatGPT Web/Desktop MCP tool surface now carries and validates an
explicit output-schema contract in local manifests and transport/SDK verification
summaries. This aligns the local MCP proof path with the ChatGPT Apps guidance
that tool descriptors include a schema for returned structuredContent.

## Root cause

The FastMCP registration already emitted an SDK-level object output schema when
`structured_output=True` was accepted, but RiftReader's own tool manifest and
transport-smoke verifier did not surface or require output schemas. A future SDK
or adapter regression could remove descriptor output schemas without the local
MCP gates noticing before an actual ChatGPT proof run.

## Changed files

| Path | Change |
|---|---|
| `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` | Added `tool_output_schema()`, includes `outputSchema` in the manifest, captures SDK/transport output schemas, and blocks missing/non-object output schemas. |
| `scripts/test_riftreader_chatgpt_mcp.py` | Added manifest output-schema assertions and a regression that transport-smoke verification blocks a missing output schema. |
| `docs/workflow/riftreader-chatgpt-mcp.md` | Documents that the manifest and verifier require outputSchema for each allowlisted tool. |
| `docs/HANDOFF.md` | Adds this handoff to the top re-entry index. |

## Validation

| Command | Result |
|---|---|
| `python -m unittest scripts.test_riftreader_chatgpt_mcp` | Passed 56 tests in 3.048s. |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_local_artifact_bridge scripts.test_package_draft_review` | Passed 177 tests in 44.610s. |
| `python tools\riftreader_workflow\validation_ledger.py --tier targeted --command "python -m unittest ..."` | Passed at `.riftreader-local/validation-runs/20260605-113233-975976/summary.md` in 42.770s. |

## Boundaries

No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider
writes, proof promotion, push, or remote mutation was performed.
