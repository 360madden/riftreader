<!--
Version: riftreader-mcp-tool-caller-docs-v0.1.2
Purpose: Document the local CLI caller for invoking RiftReader MCP tools over stdio.
-->

# RiftReader MCP Tool Caller v0.1.2

## Purpose

This helper lets the operator invoke one allowlisted RiftReader MCP tool from PowerShell without a separate MCP-capable UI.

It is useful for testing the actual MCP workflow end-to-end before wiring the server into an external client.

## Commands

Get git state:

```powershell
.\scripts\riftreader-mcp-call.cmd --tool riftreader.get_git_state --json
```

Run compact status through MCP:

```powershell
.\scripts\riftreader-mcp-call.cmd --tool riftreader.run_compact_status --arguments-json "{\"timeoutSeconds\":180}" --timeout-seconds 240 --json
```

Run static-chain diagnostics through MCP:

```powershell
.\scripts\riftreader-mcp-call.cmd --tool riftreader.run_static_chain_diagnostics --arguments-json "{\"timeoutSeconds\":300}" --timeout-seconds 900 --json
```

## Safety

The caller does not expose arbitrary shell. It can only call tools that the MCP server exposes.

MCP v0.1 tools still do not include movement, proof promotion, CE, x64dbg, or generic filesystem access.

## END_OF_SCRIPT_MARKER
