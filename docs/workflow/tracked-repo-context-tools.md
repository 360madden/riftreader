# Tracked Repo Context Tools v0.1

Version: riftreader-tracked-repo-context-doc-v0.1.0
Total-Character-Count: 0000002798
Purpose: Document the read-only tracked repo context helper intended for MCP tool exposure.

## Purpose

This helper is the Phase 1C-B0 precursor for MCP tracked repo reader/search tools. It gives ChatGPT bounded access to public/tracked repository context without exposing arbitrary local filesystem paths.

The first package adds a repo-owned Python helper and tests. The MCP adapter can then wrap these functions as callable tools after the adapter file is inspected and patched safely.

## Tool names represented by helper functions

The helper implements Python-callable functions matching the intended MCP surface:

```text
repo_tree_tracked
repo_search_tracked
repo_read_tracked_file
repo_read_many_tracked_files
repo_context_pack
```

## Safety model

Allowed:

```text
- git-tracked files only
- bounded text reads
- bounded literal or regex search
- repo-relative paths only
- docs, scripts, tools, tests, and config text
- predefined context packs
```

Blocked by default:

```text
- untracked and ignored files
- .git/**
- .riftreader-local/**
- absolute paths
- backslash paths
- path traversal including URL-encoded traversal
- secret-like names and extensions
- binary/archive/executable/raw dump extensions
- oversized reads
- command execution
- writes
```

## CLI usage

From the repo root:

```powershell
.\scripts\riftreader-tracked-repo-context.cmd self-test --json
.\scripts\riftreader-tracked-repo-context.cmd tree --prefix tools/riftreader_workflow --depth 1 --json
.\scripts\riftreader-tracked-repo-context.cmd search riftreader_chatgpt_mcp --json
.\scripts\riftreader-tracked-repo-context.cmd read tools/riftreader_workflow/riftreader_chatgpt_mcp.py --json
.\scripts\riftreader-tracked-repo-context.cmd context-pack mcp-adapter --json
```

## Context packs

Initial packs:

| Pack | Intent |
|---|---|
| `mcp-adapter` | MCP adapter, wrapper, tests, and docs. |
| `git-state` | Phase 1A/1B git-state helper and related handoff/docs. |
| `package-flow` | Package-intake and artifact-bridge helper patterns. |
| `workflow-docs` | Workflow docs and handoffs. |

## Validation

Run after applying the package locally:

```powershell
python -m py_compile tools\riftreader_workflow\tracked_repo_context.py scripts\test_tracked_repo_context.py
python -m unittest scripts.test_tracked_repo_context
.\scripts\riftreader-tracked-repo-context.cmd self-test --json
git --no-pager diff --check
```

## Adapter integration note

Do not patch `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` from memory. Inspect the tracked adapter file first, then wire these helper functions into MCP using the existing adapter registration pattern.

END_OF_SCRIPT_MARKER
