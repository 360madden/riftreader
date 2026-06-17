# 2026-06-17 - MCP Stage 29 push preflight complete-local

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Active lane | Non-Codex ChatGPT Web/Desktop Developer Mode MCP workflow. |
| Pre-slice HEAD | `acf6086e390564923fef987c0c3643f68f301d4d` |
| Stage 28 | Complete-local, committed and pushed as `acf6086`. |
| Stage 29 | Complete-local: read-only push preflight helper and tests added. |
| MCP surface | Existing 20-tool full profile remains unchanged; `push_current_branch` is not exposed. |
| Next stage | Stage 30 approval-gated push execution and MCP wrapper. |

## Stage 29 deliverables

| Deliverable | Path / status |
|---|---|
| Push preflight helper | `tools/riftreader_workflow/push_current_branch.py --preflight --json` |
| Thin launcher | `scripts/riftreader-push-current-branch.cmd` |
| Unit tests | `scripts/test_push_current_branch.py` |
| MCP control-plan metadata | `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` reports Stage 30 next and push preflight implemented-not-exposed. |
| 50-stage plan refresh | `docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md` marks Stage 29 complete-local. |

## Safety boundaries observed

The helper is read-only and does not run `git push`. This Stage 29 slice did not perform or expose:

- `push_current_branch` MCP tool exposure;
- Git remote mutation through MCP;
- force push, branch rewrite, reset, clean, stash/drop, checkout/restore discard, or destructive cleanup;
- arbitrary shell or broad filesystem MCP endpoint;
- provider repo writes outside RiftReader;
- RIFT input, movement, target selection, `/reloadui`, screenshot key input, ProofOnly, CE, or x64dbg.

## Validation to run for this slice

| Command / gate | Purpose |
|---|---|
| `python -m py_compile tools/riftreader_workflow/push_current_branch.py tools/riftreader_workflow/riftreader_chatgpt_mcp.py` | Syntax check helper and control-plan code. |
| `python -m unittest scripts.test_push_current_branch scripts.test_riftreader_chatgpt_mcp` | Focused preflight and MCP metadata regression. |
| `scripts\riftreader-push-current-branch.cmd --self-test --json` | Helper self-test in a temp repo. |
| `git --no-pager diff --check -- ...` | Whitespace/diff hygiene for explicit paths. |
| `scripts\riftreader-mcp-final.cmd --status --compact-json` | Final gate after commit/push/CI. |

## Next action

Implement Stage 30 only after Stage 29 validation passes: add approval-gated
`--push` execution that reruns preflight, requires `expectedHead`, `branch`,
`upstream`, and `approvalToken`, performs one normal `git push origin HEAD:<branch>`,
then verifies remote HEAD and directs CI follow-up.

Generated UTC: `2026-06-17T10:54:10Z`.
