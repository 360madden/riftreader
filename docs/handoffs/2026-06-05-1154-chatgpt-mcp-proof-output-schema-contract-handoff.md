# ChatGPT MCP proof output-schema contract handoff — 2026-06-05 11:54 UTC

## Result

The actual ChatGPT Web/Desktop MCP proof contract now fails closed unless the
operator-supplied Secure Tunnel proof confirms ChatGPT saw per-tool
`outputSchema` contracts for the allowlisted tool surface.

## What changed

| Area | Change |
|---|---|
| Proof recorder | `tools/riftreader_workflow/chatgpt_trial_recorder.py` now requires `toolOutputSchemasPresent=true` and `toolOutputSchemaCount=10`. |
| Proof template | `scripts\riftreader-chatgpt-trial-recorder.cmd --template --json` includes the new fields with safe defaults. |
| Proof replay | `tools/riftreader_workflow/mcp_proof_replay.py` includes output-schema proof fields in replay summaries and self-test fixtures. |
| Artifact state | `tools/riftreader_workflow/mcp_workflow_state.py` surfaces output-schema proof facts in latest-artifact summaries. |
| Mission Control | Final-product progress now requires output-schema proof facts before treating actual-client proof as completed. |
| Docs/tests | MCP workflow docs and proof/phase/state/Mission Control tests were updated for the stronger proof contract. |

## Validation

| Check | Result |
|---|---|
| Focused proof/state tests | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase1_completion scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control` passed 43 tests in 12.325s. |
| Broad MCP validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_local_artifact_bridge scripts.test_package_draft_review scripts.test_mcp_phase1_completion` passed 186 tests in 46.540s. |
| Targeted ledger | `.riftreader-local\validation-runs\20260605-115535-540313\summary.md` passed in 46.027s. |

## Current boundary

No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider
writes, proof promotion, push, or remote mutation was performed. Final readiness
still requires a fresh actual ChatGPT Secure Tunnel proof and current-head CI
after an explicit push approval.

## Safe resume

1. Run `scripts\riftreader-chatgpt-trial-recorder.cmd --template --json` to get
   the current proof template.
2. During the explicit actual ChatGPT Secure Tunnel proof, record
   `toolOutputSchemasPresent=true` and `toolOutputSchemaCount=10` only if
   ChatGPT observed all allowlisted tools with output schemas.
3. Re-run `scripts\riftreader-mcp-final.cmd --status --compact-json` after the
   proof is recorded and current-head CI exists.
