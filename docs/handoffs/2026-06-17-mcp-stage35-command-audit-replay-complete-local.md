# 2026-06-17 - MCP Stage 35 command audit/replay complete-local

| Item | Current truth |
|---|---|
| Stage 35 | Complete-local: bounded command run summaries can now be listed and replayed without rerunning child commands. |
| Helper | `tools/riftreader_workflow/bounded_repo_commands.py` now supports `--list-runs`, `--latest-run [COMMAND_KEY]`, and `--replay-summary <path>`. |
| Audit root | `.riftreader-local\riftreader-chatgpt-mcp\bounded-commands\*\run-summary.json`. |
| Replay boundary | Replay validates the saved envelope, SHA-256, registry key/argv, output caps, safety flags, and path confinement under the audit root; it does not execute the child command. |
| MCP surface | Unchanged at 23 tools; no new arbitrary shell, filesystem, provider, live-RIFT, debugger, proof-promotion, or Git-mutation endpoint was added. |
| Runtime dependency | Source changes made the old backend stale; verified stale PID `126908` was stopped and fresh PID `115656` now reports `running-current`. |
| Stage 34 CI | Passed for pushed HEAD `f4071d1dbbb241bc95ee8b78db9f2d9a1172f558`. |
| Remaining final-gate blocker | Actual-client proof replay is still stale 20-tool evidence; refresh ChatGPT Web/Desktop proof for the current 23-tool surface after this slice is committed/pushed/CI-passed. |

## Validation run

```cmd
python -m py_compile tools\riftreader_workflow\bounded_repo_commands.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_bounded_repo_commands.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py
python -m unittest scripts.test_bounded_repo_commands scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs
python tools\riftreader_workflow\bounded_repo_commands.py --self-test --json
python tools\riftreader_workflow\bounded_repo_commands.py --list-runs --json
python tools\riftreader_workflow\bounded_repo_commands.py --latest-run mcp_server_status --json
python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json
scripts\riftreader-mcp-server-status.cmd --json
python tools\riftreader_workflow\bounded_repo_commands.py --run mcp_server_status --json
python tools\riftreader_workflow\mcp_ci_status.py --status --json
scripts\riftreader-mcp-final.cmd --status --compact-json
```

Validation results:

- Syntax validation passed.
- Focused unit/docs tests passed: `99` tests.
- Registry self-test passed.
- Audit index and latest replay passed; latest replay summary SHA-256 was reported from the saved envelope.
- SDK registration validation passed for the 23-tool full profile.
- Server status initially blocked as `running-stale-runtime` because PID `126908` started before current source changes; after verified restart, PID `115656` passed `running-current`.
- Bounded command `mcp_server_status` passed and wrote `.riftreader-local\riftreader-chatgpt-mcp\bounded-commands\20260617-121643Z-mcp_server_status\run-summary.json`.
- Current-head CI passed for Stage 34 HEAD `f4071d1dbbb241bc95ee8b78db9f2d9a1172f558`.
- Final readiness remains blocked while this Stage 35 slice is dirty and because actual-client proof is still stale 20-tool evidence.

## Fast resume commands

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
git --no-pager status --short --branch
python -m unittest scripts.test_bounded_repo_commands scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs
python tools\riftreader_workflow\bounded_repo_commands.py --latest-run mcp_server_status --json
scripts\riftreader-mcp-server-status.cmd --json
scripts\riftreader-mcp-final.cmd --status --compact-json
```

## Next stage

Stage 36 is provider repo write planning only. Do not write to ChromaLink,
RiftScan, or any external provider repo; only design separate roots,
authorization, labels, and fail-closed boundaries.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Run pre-commit for the explicit Stage 35 paths. | Keeps the local commit gate deterministic. |
| 2 | Commit Stage 35 with explicit paths only. | Makes audit/replay evidence durable. |
| 3 | Push the normal current branch after commit. | Authorized non-force push publishes the coherent safe slice. |
| 4 | Wait for current-head CI to pass. | Push success is not CI success. |
| 5 | Rerun final readiness after CI. | Confirms only actual-client proof remains blocked. |
| 6 | Implement Stage 36 provider-write planning as docs/contract only. | Provider writes remain prohibited through this stage. |
| 7 | Implement Stage 37 provider-safe proposal labels without writes. | Prevents silent mixing of RiftReader and provider repo mutations. |
| 8 | Refresh actual ChatGPT Web/Desktop proof for the 23-tool surface when ready. | Final gate requires current actual-client observations. |
| 9 | Keep `scripts\riftreader-mcp-server-status.cmd --json` before MCP proof attempts. | Prevents wasting proof work against stale/missing backend. |
| 10 | Stop before Stage 38 unless explicitly approved. | Stage 38 is the first live-RIFT boundary. |
