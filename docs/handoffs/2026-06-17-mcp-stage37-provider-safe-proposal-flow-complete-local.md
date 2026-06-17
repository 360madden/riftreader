# MCP Stage 37 provider-safe proposal flow complete-local

Date: 2026-06-17

## Summary

Stage 37 is complete-local. The non-Codex ChatGPT MCP package-proposal flow now
preserves provider-write intent as explicit blocked-by-default metadata instead
of silently mixing external/provider repo work into the RiftReader apply path.

## What changed

| Area | Result |
|---|---|
| Proposal labels | `providerWriteIntent`, `providerKey`, `providerRoot`, and `providerFiles` metadata is normalized into a `riftreader-provider-write-intent-label`. |
| Submit response | `submit_package_proposal` returns the provider label and warning when provider intent is present. |
| Draft response | `create_package_draft_from_inbox` writes the provider label into the inert local draft summary and manifest metadata. |
| Review/dry-run/apply | Provider-intent drafts block review readiness, dry-run, and apply preflight through RiftReader package tools. |
| Provider safety | Provider writes remain disabled, no provider-write MCP tool was exposed, and absolute provider roots are not echoed back to ChatGPT-facing payloads. |
| Stage plan | The 50-stage plan now marks Stage 37 complete-local and moves the current stage to Stage 38. |

## Validation evidence

| Check | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\local_artifact_bridge.py tools\riftreader_workflow\package_draft_review.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py` | Passed |
| `python -m unittest scripts.test_chatgpt_mcp_workflow_docs scripts.test_riftreader_chatgpt_mcp scripts.test_bounded_repo_commands scripts.test_mcp_server_status` | Passed, 107 tests |
| `python tools\riftreader_workflow\package_draft_review.py --self-test --json` | Passed |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json` | Passed |
| `git diff --check -- ...` on the changed tracked files | Passed |
| `python tools\riftreader_workflow\mcp_ci_status.py --status --json` on Stage 36 HEAD `f4bc908029352b6bb9cde9a5323c2ec97fde175d` | Passed |
| `scripts\riftreader-mcp-server-status.cmd --json` after restart | Passed, `running-current`, 23 tools |

## Runtime note

Stage 37 source edits made the previously running MCP backend stale. The stale
process was verified by command line before termination:

| Runtime | PID |
|---|---:|
| Stopped stale MCP process | `26524` |
| Fresh current MCP process | `114284` |

The fresh process reports the expected 23-tool full profile and source
freshness. A saved ChatGPT connector entry still does not start the local
backend; the local backend must be running before ChatGPT can reach it.

## Current boundary

Stage 38 is the first live-RIFT stage. Do not enter Stage 38 implementation
without explicit approval for the live boundary. Stage 37 did **not** send RIFT
input, use `/reloadui`, attach CE/x64dbg, write provider repos, stage/commit/push
provider files, or promote proof/current truth.

## Remaining blocker

Final readiness is still expected to block until actual ChatGPT connector proof
is refreshed for the current 23-tool surface. Local backend status is necessary
but is not a substitute for actual-client proof.
