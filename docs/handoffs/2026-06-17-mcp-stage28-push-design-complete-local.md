# 2026-06-17 - MCP Stage 28 push design complete-local

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Active lane | Non-Codex ChatGPT Web/Desktop Developer Mode MCP workflow. |
| Pre-slice HEAD | `16db82af1d97cc86f9be73e7b1df0370bc1e7675` |
| MCP surface | Existing 20-tool full profile remains unchanged; `push_current_branch` is not exposed. |
| Server status | `running-current` before this design slice. |
| Final gate baseline | Passed for the existing 20-tool surface before this design slice. |
| Stage 21 | Complete: approved apply proof passed. |
| Stage 27 | Complete: approved local commit proof passed. |
| Stage 28 | Complete-local: push tool design and MCP control-plan contract added. |
| Stage 29 next | Implement read-only push preflight helper. |

## Stage 28 deliverables

| Deliverable | Path / status |
|---|---|
| Push design spec | `docs/workflow/riftreader-chatgpt-mcp-push-tool-design.md` |
| 50-stage plan refresh | `docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md` marks Stage 28 complete-local and Stage 29 next. |
| MCP control-plan metadata | `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` surfaces `push_current_branch` as designed-not-exposed in `futureToolContracts`. |
| Current handoff | `docs/HANDOFF.md` prepended with this Stage 28 truth. |

## Safety boundaries observed

No action in this Stage 28 slice performed or exposed:

- `push_current_branch` MCP tool exposure;
- Git remote mutation through MCP;
- force push, branch rewrite, reset, clean, stash/drop, checkout/restore discard, or destructive cleanup;
- arbitrary shell or broad filesystem MCP endpoint;
- provider repo writes outside RiftReader;
- RIFT input, movement, target selection, `/reloadui`, screenshot key input, ProofOnly, CE, or x64dbg.

## Validation to run for this slice

| Command / gate | Purpose |
|---|---|
| `python -m py_compile tools/riftreader_workflow/riftreader_chatgpt_mcp.py` | Syntax check updated control-plan code. |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp` | Focused MCP surface/control-plan regression. |
| `git --no-pager diff --check -- ...` | Whitespace/diff hygiene for explicit paths. |
| `scripts\riftreader-mcp-server-status.cmd --json` | Confirm MCP runtime dependency before any actual-client proof. |

## Next action

Implement Stage 29: a Python-first, read-only `push_current_branch.py --preflight`
helper plus a thin `.cmd` wrapper and unit tests. The helper must return
branch/upstream/ahead-behind facts and an approval token only when a normal
non-force push is safe.

Generated UTC: `2026-06-17T10:44:32Z`.
