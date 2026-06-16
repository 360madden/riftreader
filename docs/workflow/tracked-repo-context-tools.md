# Tracked Repo Context Tools v0.2

Version: riftreader-tracked-repo-context-doc-v0.2.1
Total-Character-Count: 0000002798
Purpose: Document the read-only tracked repo context helper and MCP tool exposure.

## Purpose

This helper and MCP surface are the Phase 1C-B0 tracked repo reader/search tools. They give ChatGPT bounded access to git-tracked repository context without exposing arbitrary local filesystem paths.

The Python helper remains the reusable local implementation. The ChatGPT MCP adapter exposes the same read-only functions as callable tools with stricter MCP response caps.

## MCP tool names

The full MCP profile exposes these read-only tracked-context tools:

```text
repo_tree_tracked
repo_search_tracked
repo_read_tracked_file
repo_read_many_tracked_files
repo_context_pack
```

They are full-profile tools only; the public-read-only profile remains limited to the smaller phase-0 status/control surface.

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

## MCP caps

| Tool area | Default cap | Max cap |
|---|---:|---:|
| Tree items | 200 | 500 |
| Search matches | 25 | 50 |
| Single file bytes | 64 KiB | 256 KiB |
| Multi-file total bytes | 256 KiB | 512 KiB |
| Context-pack files | 8 | 12 |
| Read-many files | 20 | 20 |

## CLI usage

From the repo root:

```cmd
scripts\riftreader-tracked-repo-context.cmd self-test --json
scripts\riftreader-tracked-repo-context.cmd tree --prefix tools/riftreader_workflow --depth 1 --json
scripts\riftreader-tracked-repo-context.cmd search riftreader_chatgpt_mcp --json
scripts\riftreader-tracked-repo-context.cmd read tools/riftreader_workflow/riftreader_chatgpt_mcp.py --json
scripts\riftreader-tracked-repo-context.cmd context-pack mcp-adapter --json
```

## Context packs

Initial packs:

| Pack | Intent |
|---|---|
| `mcp-adapter` | MCP adapter, wrapper, tests, and docs. |
| `git-state` | Phase 1A/1B git-state helper and related handoff/docs. |
| `package-flow` | Package-intake and artifact-bridge helper patterns. |
| `workflow-docs` | Current handoff pointer, active MCP workflow docs, newest handoffs, then remaining workflow docs if the file budget allows. |

`workflow-docs` is intentionally ordered for resume context, not alphabetic
inventory. It prioritizes `docs/HANDOFF.md`, the active ChatGPT MCP roadmap and
workflow docs, and then sorts `docs/handoffs/*.md` newest-first by leading
handoff date/time before filling any remaining budget with other workflow docs.

## Validation

Run after tracked-context helper or MCP wrapper changes:

```cmd
python -m py_compile tools\riftreader_workflow\tracked_repo_context.py scripts\test_tracked_repo_context.py
python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\mcp_tool_surface.py
python -m unittest scripts.test_tracked_repo_context scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_phase1_completion
scripts\riftreader-tracked-repo-context.cmd self-test --json
git --no-pager diff --check
```

## Adapter integration status

Implemented locally in `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` and guarded by `scripts/test_riftreader_chatgpt_mcp.py`. Future changes must still inspect the tracked adapter file first and extend the existing registration pattern instead of patching from memory.

END_OF_SCRIPT_MARKER
