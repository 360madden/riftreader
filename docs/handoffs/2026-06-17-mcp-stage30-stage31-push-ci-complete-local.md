# 2026-06-17 - MCP Stage 30 push exposure and Stage 31 CI monitor complete-local

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Active lane | Non-Codex ChatGPT Web/Desktop Developer Mode MCP workflow. |
| Pre-slice HEAD | `9862ce38e989bc5204bbb66a9335bff1dd521aa4` |
| Stage 30 | Complete-local: approval-gated push helper and MCP wrapper added. |
| Stage 31 | Complete-local: read-only current-head CI monitor MCP tool added. |
| MCP surface | Full profile changes from 20 to 22 tools. |
| Next stage | Stage 32 bounded command design spec. |

## Stage 30/31 deliverables

| Deliverable | Path / status |
|---|---|
| Push execution helper | `tools/riftreader_workflow/push_current_branch.py --push` reruns preflight, requires token, pushes normally, verifies remote HEAD. |
| Push MCP wrapper | `push_current_branch` in `tools/riftreader_workflow/riftreader_chatgpt_mcp.py`. |
| CI MCP wrapper | `get_current_head_ci_status` wraps `tools/riftreader_workflow/mcp_ci_status.py` read-only status. |
| Canonical tool surface | `tools/riftreader_workflow/mcp_tool_surface.py` now includes 22 tools. |
| Tests | `scripts/test_push_current_branch.py` and `scripts/test_riftreader_chatgpt_mcp.py` cover push denial, approved temp-remote push, and CI read-only wrapper. |
| Roadmap/handoff | `docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md`, `docs/HANDOFF.md`, and this compact handoff. |

## Safety boundaries observed

This implementation keeps remote push separate from commit. It does not expose or perform:

- force push, branch rewrite, reset, clean, stash/drop, checkout/restore discard, or destructive cleanup;
- arbitrary shell or broad filesystem MCP endpoint;
- provider repo writes outside RiftReader;
- RIFT input, movement, target selection, `/reloadui`, screenshot key input, ProofOnly, CE, or x64dbg.

## Validation to run for this slice

| Command / gate | Purpose |
|---|---|
| `python -m py_compile tools/riftreader_workflow/push_current_branch.py tools/riftreader_workflow/riftreader_chatgpt_mcp.py tools/riftreader_workflow/mcp_tool_surface.py` | Syntax check updated helper/surface. |
| `python -m unittest scripts.test_push_current_branch scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_ci_status` | Focused push, MCP, and CI regression. |
| `scripts\riftreader-push-current-branch.cmd --self-test --json` | Temp-repo preflight and approved-push self-test. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --tool-profile full --json` | Verify FastMCP metadata for new tools. |
| `git --no-pager diff --check -- ...` | Diff hygiene for explicit paths. |
| `scripts\riftreader-mcp-server-status.cmd --json` | Required before actual MCP connector proof. |
| `scripts\riftreader-mcp-final.cmd --status --compact-json` | Final readiness after commit/push/CI/proof refresh. |

## Next action

Commit/push this slice, restart the MCP backend so the 22-tool surface is loaded,
then prove the current server is `running-current` before attempting actual MCP
connector calls. After Stage 30/31 proof, continue to Stage 32 bounded command
design; do not enter live-RIFT Stage 38.

Generated UTC: `2026-06-17T11:09:03Z`.
