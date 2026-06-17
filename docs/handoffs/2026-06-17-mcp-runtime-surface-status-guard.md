# 2026-06-17 - MCP runtime surface status guard

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Pre-slice HEAD | `ffcdc1858ab2df2efa890ad0af50564f773f43fc` (`ffcdc18`) |
| Active lane | Non-Codex ChatGPT Web/Desktop Developer Mode MCP workflow. |
| Root cause fixed | `scripts\riftreader-mcp-server-status.cmd --json` previously trusted PID/port/command-line identity but did not prove the loaded MCP runtime surface. |
| Fix | `tools\riftreader_workflow\mcp_server_status.py` now performs a read-only streamable-HTTP `list_tools` + `health` probe and requires the live runtime to match the expected 22-tool surface. |
| Regression test | `scripts\test_mcp_server_status.py` now blocks a matching command line with stale 20-tool runtime metadata. |
| Server action | Stale PID `116780` was verified as `riftreader_chatgpt_mcp.py --serve --port 8770`, stopped, and restarted as PID `124328` full-profile. |
| Local backend status | Hardened status passed: `status=running-current`, runtime `observedToolCount=22`, health `toolCount=22`. |
| Actual connector caveat | The already-loaded Codex `mcp__riftreader` tool facade in this thread still returned cached 20-tool health after restart; treat that as connector/app cache refresh, not local backend source truth. |
| Final gate | Still blocked until a fresh actual-client proof replay records the 22-tool surface; current-head CI for `ffcdc18` was passed before this local slice. |
| Next stage | Stage 32 bounded command design spec, while actual-client proof refresh remains a parallel proof blocker. |

## Validation

| Command / gate | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\mcp_server_status.py scripts\test_mcp_server_status.py` | Passed |
| `python -m unittest scripts.test_mcp_server_status` | Passed, 5 tests |
| `python -m unittest scripts.test_mcp_server_status scripts.test_mcp_dashboard scripts.test_mcp_control_center` | Passed, 17 tests |
| `scripts\riftreader-mcp-server-status.cmd --json` | Passed with runtime surface 22/22 |
| `scripts\riftreader-mcp-final.cmd --status --compact-json` | Blocked as expected: dirty worktree plus stale 20-tool actual-client proof replay |

## Safety boundaries observed

No RIFT input/movement, `/reloadui`, screenshot key input, CE, x64dbg, provider repo writes, branch rewrite, reset, clean, destructive cleanup, arbitrary shell MCP endpoint, or force push was performed. The only process mutation was stopping the verified stale local MCP adapter process after explicit user approval and starting the same repo-owned adapter with the current full profile.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit and push the runtime-surface status guard. | Prevents future stale MCP runtime misclassification. |
| 2 | Refresh ChatGPT/Codex connector tool discovery outside the local backend if it still reports 20 tools. | The backend is 22, but the loaded connector facade can stay cached. |
| 3 | Record fresh actual-client proof for the 22-tool surface. | Final gate still replays the old 20-tool proof. |
| 4 | Rerun `scripts\riftreader-mcp-final.cmd --status --compact-json` after proof refresh. | Confirms proof, CI, Git, and safety gates together. |
| 5 | Continue Stage 32 bounded command design. | This is the next non-live roadmap stage. |
| 6 | Implement Stage 33 allowlist registry only after the design is reviewed in repo docs. | Avoids arbitrary shell drift. |
| 7 | Expose Stage 34 bounded command subset only from the allowlist. | Keeps command execution deterministic and reviewable. |
| 8 | Add Stage 35 command audit/replay before broad use. | Makes command proof reproducible. |
| 9 | Keep Stages 36-37 provider work as planning/labeling only. | External provider writes remain out of scope. |
| 10 | Stop before Stage 38 unless explicitly approved. | Stage 38 is the first live-RIFT boundary. |

Generated UTC: `2026-06-17T11:28:59Z`.
