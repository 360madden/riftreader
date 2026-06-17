# 2026-06-17 - MCP source-freshness runtime guard

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Pre-slice HEAD | `f4c4efcbfe1c5aed55c816015e7e64a365a5ec44` (`f4c4efc`) |
| Root cause closed | A server can expose the expected 22-tool surface while still running stale Python code if the source changed after process start. |
| Fix | `scripts\riftreader-mcp-server-status.cmd --json` now includes process `creationDate` and blocks when current adapter source files are newer than the MCP adapter process. |
| Regression test | `scripts\test_mcp_server_status.py` covers matching command line + matching tool surface + stale process start. |
| Restart evidence | PID `124328` was correctly blocked as `running-stale-runtime`; after verified restart, PID `124052` passed `runtimeSourceFreshness`. |
| Local backend status | `status=running-current`, runtime surface 22 tools, source freshness passed. |
| Remaining proof blocker | Fresh actual-client proof replay is still required for final readiness. |

## Validation

| Command / gate | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\mcp_server_status.py scripts\test_mcp_server_status.py` | Passed |
| `python -m unittest scripts.test_mcp_server_status` | Passed, 6 tests |
| `scripts\riftreader-mcp-server-status.cmd --json` before restart | Blocked stale PID `124328` because source was newer than process start. |
| `scripts\riftreader-mcp-server-status.cmd --json` after restart | Passed with PID `124052`, 22 live tools, source freshness passed. |

## Safety boundaries observed

No RIFT input/movement, `/reloadui`, screenshot key input, CE, x64dbg, provider
repo writes, branch rewrite, reset, clean, destructive cleanup, arbitrary shell
MCP endpoint, or force push was performed. The only process mutation was a
verified stop/start of the repo-owned MCP adapter after explicit user approval.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit and push this source-freshness guard. | Prevents same-tool-count stale server loops. |
| 2 | Poll CI for the new pushed head. | Current-head CI must be green before final claims. |
| 3 | Restart MCP after future adapter/source changes before actual connector proof. | Source freshness will block stale processes. |
| 4 | Refresh actual-client proof for the 22-tool surface. | Final readiness still replays old proof. |
| 5 | Continue Stage 33 command registry. | Stage 32 design is complete-local. |
| 6 | Keep registry keys tiny and deterministic. | Avoids arbitrary shell drift. |
| 7 | Add registry denial tests before MCP exposure. | Blocks destructive/live/provider/debugger classes. |
| 8 | Expose command tool only at Stage 34 after registry proof. | Maintains stage order. |
| 9 | Add audit/replay at Stage 35. | Makes command runs explainable and reproducible. |
| 10 | Stop before Stage 38 unless explicitly approved. | Stage 38 is the first live-RIFT boundary. |

Generated UTC: `2026-06-17T11:40:16Z`.
