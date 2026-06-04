<!--
Version: riftreader-mcp-git-state-clean-paths-docs-v0.1.1
Purpose: Document the MCP git-state dirty-path parser correction.
-->

# MCP Git State Clean Paths v0.1.1

## Purpose

Fix a small MCP git-state quality issue where the `git status --short --branch` header line:

```text
## main...origin/main
```

was included in `dirtyPaths` as:

```text
main...origin/main
```

The branch header is not a dirty file and should not appear in dirty-path lists.

## Scope

Changed files:

```text
tools/riftreader_mcp/server.py
scripts/test_riftreader_mcp_server.py
```

## Safety

This patch changes parser/reporting behavior only.

It does not:

```text
run movement
send input
attach Cheat Engine
attach x64dbg
expose generic shell
change MCP tool names
write game memory
stage, commit, or push by itself
```

## Validation

```powershell
python -m py_compile tools\riftreader_mcp\server.py scripts\test_riftreader_mcp_server.py tools\riftreader_mcp\client_config.py scripts\test_riftreader_mcp_client_config.py
python -m unittest scripts.test_riftreader_mcp_server
python -W error::ResourceWarning -m unittest scripts.test_riftreader_mcp_client_config
python tools\riftreader_mcp\client_config.py --repo "C:\RIFT MODDING\RiftReader" --write-config --smoke --json
git --no-pager diff --check
```

## END_OF_SCRIPT_MARKER
