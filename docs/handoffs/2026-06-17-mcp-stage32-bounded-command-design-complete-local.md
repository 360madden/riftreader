# 2026-06-17 - MCP Stage 32 bounded command design complete-local

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Pre-slice HEAD | `ddb3a91f3a33c60aa753b15024093f02c93ea10d` (`ddb3a91`) |
| Active lane | Non-Codex ChatGPT Web/Desktop Developer Mode MCP workflow. |
| Stage 32 | Complete-local: bounded repo command design spec added. |
| Design path | `docs/workflow/riftreader-chatgpt-mcp-bounded-command-design.md` |
| MCP exposure | `run_bounded_repo_command` remains **not exposed**. |
| Current roadmap stage | Stage 33 command allowlist registry next. |
| Local backend status | `scripts\riftreader-mcp-server-status.cmd --json` passed with live 22-tool runtime after the runtime-surface guard. |
| Current-head CI | Queued for `ddb3a91f3a33c60aa753b15024093f02c93ea10d` at Stage 32 start; must be polled again before final readiness claims. |
| Final gate | Still blocked until fresh actual-client proof replay records the 22-tool surface. |

## Stage 32 deliverables

| Deliverable | Status |
|---|---|
| Bounded command product intent | Done: validation/status helpers only, not a terminal. |
| Planned tool arguments | Done: `commandKey`, typed `parameters`, registry version binding, optional approval token, timeout override. |
| Registry entry contract | Done: fixed argv template, fixed repo cwd, typed params, exit codes, timeout/output caps, safety flags. |
| Initial command-family proposal | Done: small read-only/status-focused starter set for Stage 33. |
| Forbidden command classes | Done: arbitrary shell, arbitrary filesystem, hidden Git mutation, live RIFT, CE/x64dbg, provider writes, proof promotion, secret dumps. |
| Audit envelope contract | Done: durable JSON summary with timestamps, argv, cwd, exit code, previews, hashes, safety. |
| Stage 33-35 definition of done | Done. |

## Validation to run for this slice

| Command / gate | Purpose |
|---|---|
| `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py` | Syntax check metadata/tests. |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs` | Focused MCP metadata and docs regression. |
| `git --no-pager diff --check -- ...` | Diff hygiene for explicit paths. |
| `scripts\riftreader-mcp-server-status.cmd --json` | Verify local MCP backend remains running-current and 22-tool. |
| `python tools\riftreader_workflow\mcp_ci_status.py --status --json` | Poll current-head CI after push. |

## Safety boundaries observed

No command execution MCP tool was exposed. No arbitrary shell, broad filesystem,
Git mutation, provider repo write, RIFT input/movement, `/reloadui`, screenshot
key input, ProofOnly, CE, x64dbg, proof promotion, branch rewrite, reset, clean,
or destructive cleanup was added or run by Stage 32.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Validate and commit the Stage 32 design slice with explicit paths. | Makes the command boundary durable before registry code. |
| 2 | Poll CI for `ddb3a91` and fix if it fails. | Current-head CI was queued when Stage 32 began. |
| 3 | Implement Stage 33 versioned command registry in Python. | Registry must exist before any command exposure. |
| 4 | Add registry tests for accepted safe keys and denied destructive/live/provider/debugger classes. | Prevents arbitrary shell drift. |
| 5 | Keep initial allowed keys tiny and status-focused. | Reduces blast radius for Stage 34. |
| 6 | Add preflight/approval token flow only where needed. | Keeps long-running/resource-heavy commands operator-bound. |
| 7 | Expose Stage 34 MCP tool only after registry tests pass. | Tool exposure must follow proven local gates. |
| 8 | Implement Stage 35 audit/replay before broader command use. | Every command call must be explainable and replayable. |
| 9 | Keep Stage 36/37 provider work planning/labeling only. | No external repo writes are authorized through Stage 37. |
| 10 | Stop before Stage 38 unless explicitly approved. | Stage 38 is the first live-RIFT boundary. |

Generated UTC: `2026-06-17T11:34:16Z`.
