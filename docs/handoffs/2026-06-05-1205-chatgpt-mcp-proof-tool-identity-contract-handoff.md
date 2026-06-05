# ChatGPT MCP proof tool-identity contract handoff — 2026-06-05 12:05 UTC

## Result

The actual ChatGPT Web/Desktop MCP proof contract now validates exact tool
identity, not only tool counts. Fresh proof packets must include both observed
tool names and observed output-schema tool names, and both lists must match the
canonical 10-tool allowlist.

## What changed

| Area | Change |
|---|---|
| Proof recorder | `tools/riftreader_workflow/chatgpt_trial_recorder.py` now requires `toolNames` and `toolOutputSchemaToolNames`. |
| Fail-closed validation | Duplicate, missing, unexpected, non-list, or non-string tool-name entries block proof replay. |
| Proof replay | `tools/riftreader_workflow/mcp_proof_replay.py` includes both tool-name lists in replay summaries and self-test fixtures. |
| Artifact state | `tools/riftreader_workflow/mcp_workflow_state.py` surfaces the tool-name proof fields in latest-artifact summaries. |
| Mission Control | Final-product progress requires exact tool-name and output-schema tool-name matches before treating actual-client proof as completed. |
| Docs/tests | MCP workflow docs and proof/phase/state/Mission Control tests were updated for the stronger proof contract. |

## Validation so far

| Check | Result |
|---|---|
| Focused proof/state tests | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase1_completion scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control` passed 46 tests in 12.203s. |
| Broad MCP validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_local_artifact_bridge scripts.test_package_draft_review scripts.test_mcp_phase1_completion` passed 189 tests in 46.533s. |
| Targeted ledger | `.riftreader-local\validation-runs\20260605-121300-915646\summary.md` passed in 45.276s. |

## Current boundary

No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider
writes, proof promotion, push, or remote mutation was performed. Final readiness
still requires a fresh actual ChatGPT Secure Tunnel proof and current-head CI
after explicit push approval.

## Safe resume

1. Run `scripts\riftreader-chatgpt-trial-recorder.cmd --template --json` before
   the actual ChatGPT proof.
2. Confirm `toolNames` and `toolOutputSchemaToolNames` match the observed
   ChatGPT tool surface exactly.
3. Re-run the final readiness gate after fresh proof and current-head CI exist.
