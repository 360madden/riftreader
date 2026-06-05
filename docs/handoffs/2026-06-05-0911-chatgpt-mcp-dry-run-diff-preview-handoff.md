# RiftReader Handoff — ChatGPT MCP dry-run diff preview — 2026-06-05 09:11 UTC

## Summary

The RiftReader ChatGPT Web/Desktop MCP path now returns a bounded, ChatGPT-safe
package-intake diff preview from the existing `dry_run_latest_package_draft`
tool. This improves bidirectional review/control without adding a new MCP tool
or changing the current 10-tool proof contract.

| Evidence | Result |
|---|---|
| Active adapter | `tools\riftreader_workflow\riftreader_chatgpt_mcp.py`. |
| Tool surface | 10 allowlisted tools; no 11th tool was added. |
| New review surface | `dryRun.diffPreview` in `dry_run_latest_package_draft` responses. |
| Diff source | Only `.riftreader-local\package-intake\*\package.diff`. |
| Bound | `MAX_DRY_RUN_DIFF_PREVIEW_BYTES = 16384`; large diffs are marked `truncated=true`. |
| Unsafe paths | Artifact paths outside package-intake are blocked and redacted as `<outside-package-intake>`. |
| Repo mutation | None. Dry-run still never sends `--apply`, and no Git/live/tunnel action is exposed. |
| Focused validation | `python -m unittest scripts.test_riftreader_chatgpt_mcp` passed 54 tests in 3.368s. |
| Broader MCP validation | `python -m unittest scripts.test_local_artifact_bridge scripts.test_package_draft_review scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_final_readiness scripts.test_mcp_proof_replay` passed 134 tests in 36.049s. |
| Final ledger | `.riftreader-local\validation-runs\20260605-092746-535699\summary.md` passed in 34.756s. |

## Safety

No live RIFT input, movement, `/reloadui`, screenshot key, x64dbg/CE attach,
target memory write, provider repo write, proof/current-truth promotion, tunnel
initialization/run, ChatGPT connector registration, Git push, or remote
mutation was performed.

## Resume notes

Continue safe local MCP work only. The best next local slice is to refresh the
MCP final readiness packet/current proof status, then decide whether to proceed
with operator-approved Secure MCP Tunnel setup. Actual ChatGPT Secure MCP Tunnel
setup remains gated on operator approval and credentials.
