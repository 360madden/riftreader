# 2026-06-12 - Phase 1C-B0 tracked repo context MCP tools

## Current lane

MCP / local repo automation maintenance lane. This is not a live RIFT, CE, x64dbg, or desktop-input lane.

## Local implementation result

| Item | Current truth |
|---|---|
| Branch | `main...origin/main` before this slice is committed. |
| Base HEAD | `5bcd13d Align MCP tool surface expectations`. |
| MCP surface | Full profile now expects 19 tools locally. |
| New tools | `repo_tree_tracked`, `repo_search_tracked`, `repo_read_tracked_file`, `repo_read_many_tracked_files`, `repo_context_pack`. |
| Backing helper | `tools/riftreader_workflow/tracked_repo_context.py`; helper self-test already existed and still passes in focused validation. |
| Safety | Read-only, git-tracked files only, no arbitrary filesystem root, no ignored/untracked/local artifacts, no shell endpoint, no Git mutation, no live RIFT input, no CE/x64dbg. |
| MCP caps | Tree default/max `200/500`; search `25/50`; single file `64 KiB/256 KiB`; multi-file total `256 KiB/512 KiB`; context-pack files `8/12`; read-many files `20`. |

## Files changed by this slice

- `tools/riftreader_workflow/riftreader_chatgpt_mcp.py`
- `tools/riftreader_workflow/mcp_tool_surface.py`
- `scripts/test_riftreader_chatgpt_mcp.py`
- `docs/workflow/tracked-repo-context-tools.md`
- `docs/workflow/tracked-repo-context-workflow.md`
- `docs/workflow/RIFTREADER_CHATGPT_SOURCE_PACK.md`
- `docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md`
- `docs/workflow/non-codex-desktop-chatgpt-workflow.md`
- `docs/workflow/riftreader-chatgpt-mcp.md`
- `docs/workflow/riftreader-chatgpt-mcp-live-control-design.md`
- `docs/workflow/riftreader-mcp-phase1c-operator-automation-design.md`
- `docs/HANDOFF.md`
- `docs/handoffs/2026-06-12-phase1c-b0-tracked-repo-context-mcp-tools.md`

## Validation evidence

| Check | Result |
|---|---|
| Adapter py_compile | Passed before handoff write. |
| Local adapter smoke | Passed for all five new `repo_*` tools, including blocked `.riftreader-local` read. |
| Focused unit suite | Passed before docs/handoff update: `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_tracked_repo_context scripts.test_mcp_phase1_completion` (`88 tests`, `32.467s`). |
| Final py_compile | Passed: adapter, surface constants, helper, and focused tests. |
| Final unit suite | Passed: `python -m unittest scripts.test_tracked_repo_context scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_phase1_completion scripts.test_chatgpt_trial_recorder scripts.test_mcp_final_readiness` (`145 tests`, `27.260s`). |
| Helper self-test | Passed: `scripts\riftreader-tracked-repo-context.cmd self-test --json`. |
| SDK registration | Passed: `scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json`; registered 19 tools with no blockers. |
| Diff check | Passed: `git --no-pager diff --check` with line-ending warnings only. |
| Final readiness status | Blocked as expected: dirty worktree plus stale 14-tool actual-client proof/template for the new 19-tool surface. |

## Remaining blockers / gates

| Gate | State |
|---|---|
| Actual ChatGPT proof | Stale 14-tool proof now fails against the new 19-tool surface; refresh connector/schema and record actual-client proof before claiming final readiness. |
| Final readiness | Blocked until worktree is clean and 19-tool proof/readiness/proposal-smoke artifacts are fresh. |
| Git push | Not authorized by this handoff. |
| Live RIFT / movement / desktop input | Not authorized by this handoff. |
| CE / x64dbg | Not authorized by this handoff. |
| Provider writes | Not authorized by this handoff. |

## Exact next action

Run final local validation, then create a local commit with explicit paths only if validation passes. Do not push without explicit approval.

```cmd
python -m py_compile tools\riftreader_workflow\tracked_repo_context.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\mcp_tool_surface.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_tracked_repo_context.py
python -m unittest scripts.test_tracked_repo_context scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_phase1_completion scripts.test_chatgpt_trial_recorder scripts.test_mcp_final_readiness
scripts\riftreader-tracked-repo-context.cmd self-test --json
scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json
git --no-pager diff --check
```

## After local commit

Refresh actual ChatGPT Web/Desktop connector/schema and record a new 19-tool actual-client proof through the Cloudflare named Tunnel route before treating final readiness as passed.
