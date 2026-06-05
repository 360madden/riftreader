# RiftReader Handoff — ChatGPT MCP actual-client diff-preview proof contract — 2026-06-05 10:00 UTC

## Summary

The RiftReader ChatGPT Web/Desktop MCP actual-client proof recorder now matches the stronger local transport smoke contract. A fresh external ChatGPT Web/Desktop proof must confirm draft review and bounded dry-run diff-preview facts before Phase 2/final readiness can pass.

| Evidence | Result |
|---|---|
| Active proof recorder | `tools/riftreader_workflow/chatgpt_trial_recorder.py`. |
| Active proof replay | `tools/riftreader_workflow/mcp_proof_replay.py`. |
| New required review proof | `reviewLatestPackageDraftSucceeded=true` and `reviewLatestPackageDraftReadOnly=true`. |
| New required diff-preview proof | `dryRunDiffPreviewOk=true`, `dryRunDiffPreviewArtifactUnderPackageIntake=true`, `dryRunDiffPreviewBoundedBytes=true`, positive `dryRunDiffPreviewTextLength`, and boolean `dryRunDiffPreviewTruncated`. |
| Defensive artifact replay | If a local dry-run diff artifact path is present, replay blocks paths outside `.riftreader-local/package-intake`. |
| Focused validation | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_final_readiness` passed 42 tests in 3.958s. |
| Broader MCP validation | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_phase1_completion scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 173 tests in 49.331s. |
| Final validation ledger | `.riftreader-local/validation-runs/20260605-100236-265736/summary.md` passed in 48.033s. |

## Safety

This is a local proof-contract hardening slice only. No public tunnel, ChatGPT registration, `tunnel-client init/doctor/run`, package apply, Git push, live RIFT input, movement, `/reloadui`, screenshot key, CE/x64dbg attach, proof/current-truth promotion, or provider repo write was performed.

## Resume notes

Fresh actual-client proof now needs the same full package-review loop that local proposal transport smoke already proves: submit, list inbox, create inert draft, review draft, dry-run draft, and inspect bounded `dryRun.diffPreview`. The next non-local blockers remain explicit approval for push/current-head CI and actual Secure MCP Tunnel/ChatGPT proof refresh.
