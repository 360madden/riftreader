<!--
Version: riftreader-mcp-client-quickstart-docs-v0.1.0
Purpose: Quickstart for generating and smoke-testing RiftReader MCP client configuration.
-->

# RiftReader MCP Client Quickstart v0.1

## Purpose

This helper reduces setup guesswork after the repo-owned MCP server is installed.

It can:

```text
print the MCP client JSON config
write the config into .riftreader-local
smoke-test the MCP stdio server by calling initialize, tools/list, and riftreader.get_git_state
```

## Commands

Print config:

```powershell
.\scripts\riftreader-mcp-client.cmd --print-config
```

Write config artifact:

```powershell
.\scripts\riftreader-mcp-client.cmd --write-config --json
```

Run smoke test:

```powershell
.\scripts\riftreader-mcp-client.cmd --smoke --json
```

Recommended first command:

```powershell
.\scripts\riftreader-mcp-client.cmd --write-config --smoke --json
```

## Expected tools

The smoke test expects these six MCP tools:

```text
riftreader.get_git_state
riftreader.get_current_handoff
riftreader.get_status
riftreader.run_compact_status
riftreader.run_static_chain_diagnostics
riftreader.publish_chatgpt_snapshot
```

## Safety

This helper does not expose a shell, send movement, attach CE/x64dbg, or mutate game state.

The smoke test calls `riftreader.get_git_state` only.

## END_OF_SCRIPT_MARKER
