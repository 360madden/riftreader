# 2026-06-17 - MCP Stage 34 bounded command exposure complete-local

| Item | Current truth |
|---|---|
| Stage 34 | Complete-local: `run_bounded_repo_command` exposed through the ChatGPT MCP adapter. |
| Tool surface | Full profile changes from 22 to 23 tools. |
| Execution boundary | The tool accepts only versioned registry `commandKey` values from `tools/riftreader_workflow/bounded_repo_commands.py`; it never accepts shell strings or arbitrary argv. |
| Initial command keys | `mcp_server_status`, `mcp_final_status`, `current_head_ci_status`, `validate_mcp_sdk`, `test_mcp_server_status` |
| Output evidence | Each command run returns a bounded envelope and writes `.riftreader-local\riftreader-chatgpt-mcp\bounded-commands\<UTC>-<commandKey>\run-summary.json`. |
| Safety | No Git mutation, provider writes, RIFT input/movement, `/reloadui`, CE/x64dbg, arbitrary filesystem endpoint, proof promotion, or branch rewrite. |
| Remaining proof blocker | Final readiness still needs fresh actual-client proof for the new 23-tool surface. |

## Validation run

```cmd
python -m py_compile tools\riftreader_workflow\bounded_repo_commands.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\mcp_tool_surface.py tools\riftreader_workflow\mcp_server_status.py scripts\test_bounded_repo_commands.py scripts\test_riftreader_chatgpt_mcp.py
python -m unittest scripts.test_bounded_repo_commands scripts.test_riftreader_chatgpt_mcp
python tools\riftreader_workflow\bounded_repo_commands.py --self-test --json
python tools\riftreader_workflow\bounded_repo_commands.py --run mcp_server_status --json
```

Results before server restart: unit tests passed; the bounded `mcp_server_status`
run correctly reported the old running backend as stale because it still exposed
22 tools instead of the new expected 23.

## Fast resume commands

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
git --no-pager status --short --branch
python -m unittest scripts.test_bounded_repo_commands scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs scripts.test_mcp_server_status
scripts\riftreader-mcp-server-status.cmd --json
python tools\riftreader_workflow\bounded_repo_commands.py --run mcp_server_status --json
scripts\riftreader-mcp-final.cmd --status --compact-json
```

## Next stage

Stage 35 should harden command audit and replay evidence around the bounded
command lane. The Stage 34 wrapper already writes a run summary, but Stage 35
should add deliberate replay/inspection affordances and regression checks for
successful, blocked, and failed command envelopes.
