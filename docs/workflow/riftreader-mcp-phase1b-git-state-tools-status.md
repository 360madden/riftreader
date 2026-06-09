# RiftReader MCP Phase 1B Git-state tools status

## Status
Passed and locally committed.

## Commit
`e06588b Expose Phase 1B read-only Git state MCP tools`

## New tools
- `get_dirty_paths`
- `get_recent_commits`

## Purpose
Reduce stale-context recovery friction by exposing read-only Git dirty-path and recent-commit state through the RiftReader MCP adapter.

## Safety
Both tools are read-only and must not stage, commit, push, rewrite branches, send RIFT input, touch CE, or touch x64dbg.

## Validation completed before commit
- adapter py_compile
- reader py_compile
- reader unit tests
- tool manifest generation
- local `--call get_dirty_paths --json`
- local `--call get_recent_commits --arguments-json {"limit":5} --json`
- SDK validation
- `git diff --check`
- explicit path staging
- cached path comparison
- cached diff check
- commit hook suite

## Remaining workflow gap
The current ChatGPT conversation may still have a stale 12-tool function schema even when `health` reports `toolCount: 14`. Refreshing the MCP connector/app session or starting a new conversation should allow direct calls to the new tool schemas.

## Next recommended proof
After schema refresh, call:

```text
health
get_dirty_paths
get_recent_commits
get_repo_status
```

Then update/push once the local branch state is reverified.
