# 2026-06-17 - MCP Stage 33 command allowlist registry complete-local

| Item | Current truth |
|---|---|
| Stage 33 | Complete-local: versioned bounded repo command registry added. |
| Registry module | `tools/riftreader_workflow/bounded_repo_commands.py` |
| Registry version | `bounded-repo-command-registry-v1` |
| Initial command keys | `mcp_server_status`, `mcp_final_status`, `current_head_ci_status`, `validate_mcp_sdk`, `test_mcp_server_status` |
| MCP exposure | `run_bounded_repo_command` is still **not exposed**; Stage 34 is next. |
| Safety | Registry/plan/self-test modes do not execute commands, accept shell strings, mutate Git, write providers, send RIFT input, attach CE/x64dbg, or promote proof/truth. |
| Remaining proof blocker | Final readiness still needs fresh actual-client 22-tool proof; local backend status must pass before proof replay. |

## Validation run

```cmd
python -m py_compile tools\riftreader_workflow\bounded_repo_commands.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_bounded_repo_commands.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py
python -m unittest scripts.test_bounded_repo_commands scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs
python tools\riftreader_workflow\bounded_repo_commands.py --self-test --json
python tools\riftreader_workflow\bounded_repo_commands.py --plan mcp_server_status --json
```

Results: all passed locally before commit.

## Fast resume commands

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
git --no-pager status --short --branch
python tools\riftreader_workflow\bounded_repo_commands.py --self-test --json
python -m unittest scripts.test_bounded_repo_commands scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs scripts.test_mcp_server_status
scripts\riftreader-mcp-server-status.cmd --json
scripts\riftreader-mcp-final.cmd --status --compact-json
```

## Next stage

Stage 34 should expose `run_bounded_repo_command` through MCP using only the
versioned registry. It must keep arbitrary shell absent and should block unknown
keys, registry-version mismatch, unsafe argv fragments, and unsupported
parameters before any process starts.
