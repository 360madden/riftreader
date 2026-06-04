<!--
Version: riftreader-mcp-adapter-docs-v0.1.0
Purpose: Plan and operator documentation for the RiftReader MCP Adapter v0.1.
-->

# RiftReader MCP Adapter v0.1

## Goal

Reduce manual copy/paste by exposing strict RiftReader repo workflows through a local Model Context Protocol server.

MCP v0.1 is intentionally conservative. It exposes repo/status tools only and does not expose a generic shell.

## Tool scope

Included tools:

```text
riftreader.get_git_state
riftreader.get_current_handoff
riftreader.get_status
riftreader.run_compact_status
riftreader.run_static_chain_diagnostics
riftreader.publish_chatgpt_snapshot
```

Not included in v0.1:

```text
proof-anchor promotion
movement
live navigation
Cheat Engine
x64dbg attach
generic command execution
generic filesystem read
```

## Why stdio

The MCP specification defines stdio as a client-launched subprocess where JSON-RPC messages are read from stdin and responses are written to stdout. Messages are newline-delimited UTF-8 JSON-RPC and stdout must contain only valid MCP messages. The server logs only to stderr.

## Setup

Add this command to an MCP-capable client:

```json
{
  "mcpServers": {
    "riftreader": {
      "command": "C:\\RIFT MODDING\\RiftReader\\scripts\\riftreader-mcp-server.cmd",
      "args": ["--repo", "C:\\RIFT MODDING\\RiftReader"]
    }
  }
}
```

Exact client UI varies. If a client cannot connect to local MCP servers, keep using the existing GitHub snapshot workflow.

## Local tests

```powershell
python -m py_compile tools\riftreader_mcp\server.py scripts\test_riftreader_mcp_server.py
python -m unittest scripts.test_riftreader_mcp_server
.\scripts\riftreader-mcp-server.cmd --self-test --json
.\scripts\riftreader-mcp-server.cmd --list-tools --json
git --no-pager diff --check
```

## Safety model

MCP tools are allowlisted by name. No tool accepts arbitrary shell commands. The only command-running tools call fixed repo-owned helper scripts.

`publish_chatgpt_snapshot` can push the `chatgpt/snapshot` branch through the existing snapshot helper, but it does not change game state.

## Future v0.2

Add approval-gated tools only after v0.1 is stable:

```text
riftreader.proof_reacquire_dry_run
riftreader.proof_reacquire_approved
riftreader.write_current_handoff
riftreader.commit_allowlisted
```

Those tools must retain explicit allowlists, JSON summaries, and fail-closed safety gates.

## END_OF_SCRIPT_MARKER
