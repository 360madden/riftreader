# Tracked Repo Context Workflow

## Purpose
This document makes the corrected RiftReader workflow durable: ChatGPT must use available tracked repo context before coding. The public GitHub repo is not optional background context; it is the immediate source for tracked files until MCP tracked-repo reader tools exist.

## Problem fixed
The old workflow over-relied on chat memory, MCP summaries, pasted logs, and generated one-off scripts. That caused avoidable errors because existing helpers, wrapper styles, tests, and docs were not inspected first.

## Corrected workflow
Before writing code or proposing patches, use this order:

```text
1. Verify live local repo state with MCP get_repo_status.
2. Inspect tracked repo context.
   - Preferred after Phase 1C-B0: MCP tracked-repo reader/search tools.
   - Fallback until then: public GitHub repo 360madden/riftreader.
3. Search/read relevant existing helpers, tests, wrappers, adapter code, and workflow docs.
4. Reuse or patch existing helpers where practical.
5. Generate the smallest useful package/patch.
6. Validate through repo-owned checks.
7. Commit/push only through explicit validated workflow.
```

## Why GitHub is mandatory context now
RiftReader is public on GitHub. The tracked public repo files are already visible to the world, so they should be used as immediate coding context. GitHub is slower and less workflow-native than MCP, but it is still better than coding from memory.

## Why MCP tracked repo reader is still needed
Public GitHub gives tracked-source visibility, but MCP tracked repo reader will be faster and tied to the exact local checkout. It should support task-focused context packs and direct search/read tools without exposing ignored local artifacts.

## Phase 1C-B0 target tools
Add read-only MCP tools for tracked files:

```text
repo_tree_tracked
repo_search_tracked
repo_read_tracked_file
repo_read_many_tracked_files
repo_context_pack
```

These tools must use git-tracked file inventory as the source of truth, not broad filesystem walking.

## Allow policy
Allow read-only access to git-tracked text files that are already public or intended repo source:

```text
tools/riftreader_workflow/**/*.py
scripts/**/*.py
scripts/**/*.cmd
docs/**/*.md
*.md
*.toml
*.json
*.yml
*.yaml
```

## Block policy
Block local-only or noisy paths by default:

```text
.git/**
.riftreader-local/**
**/__pycache__/**
.venv/**
.env
*.key
*.pem
*.pfx
*.sqlite
*.db
*.zip
*.7z
*.rar
*.exe
*.dll
*.bin
large raw dumps
```

## Required behavior
Tracked repo reader/search tools must:

- be read-only
- reject absolute paths and path traversal
- reject untracked and ignored files
- cap file size and response size
- return clean JSON in JSON mode
- provide line ranges or bounded chunks for larger files
- never expose arbitrary local paths
- never execute commands from user input
- never provide write endpoints

## Context packs
The `repo_context_pack` tool should return curated file groups for common tasks, for example:

```text
mcp-adapter
package-flow
validation-suite
commit-push-flow
docs-workflow
source-pack
tracked-repo-reader
```

Each context pack should list files, sizes, hashes, and selected text snippets or bounded file contents.

## Durable assistant rule
Future ChatGPT sessions working on RiftReader must follow this rule:

```text
Before coding, inspect tracked repo files through MCP tracked repo reader when available, otherwise inspect the public GitHub tracked repo. Do not rely on memory alone.
```

## Updated near-term roadmap

```text
1. Phase 1C-B0 — tracked repo reader/search MCP tools
2. Phase 1C-B  — run_validation_suite
3. Phase 1C-C  — commit_reviewed_slice
4. Phase 1C-D  — push_current_branch
5. Phase 1C-E  — source-pack and handoff auto-refresh
```

## END_OF_DOCUMENT
