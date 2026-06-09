# 2026-06-09 — Phase 1B Git-state MCP tools live

## Current lane
MCP / Git-state workflow stabilization. Do not switch to live RIFT proof/movement work from this handoff.

## Verified repo state
- Branch: `main...origin/main [ahead 14]`
- Worktree: clean after commit
- HEAD: `e06588b Expose Phase 1B read-only Git state MCP tools`
- Previous HEAD before Phase 1B adapter commit: `056470d Add Phase 1A read-only Git state helper`

## Phase 1B result
Phase 1B is committed locally and exposes two read-only Git-state MCP tools in the adapter source:

- `get_dirty_paths`
- `get_recent_commits`

The local runtime health response reports `toolCount: 14` under the full tool profile.

## Validation evidence
The commit runner passed all required validation stages before commit:

- adapter py_compile
- Phase 1A reader py_compile
- Phase 1A reader unit tests
- adapter tool manifest
- adapter local call: `get_dirty_paths`
- adapter local call: `get_recent_commits`
- adapter SDK validation
- git diff check
- explicit adapter-path staging only
- cached diff check
- local commit
- post-commit clean status

## Important runtime note
Health reports the runtime manifest as 14 tools, but the current ChatGPT conversation may still show a stale 12-function connector schema until the connector/app schema is refreshed or a new conversation is opened. In that stale-schema state, ChatGPT can call existing tools such as `health` and `get_repo_status`, but may not directly receive callable function schemas for `get_dirty_paths` and `get_recent_commits` yet.

## Safety boundaries unchanged
- No RIFT input or movement.
- No `/reloadui`.
- No screenshot key.
- No CE.
- No x64dbg attach.
- No arbitrary shell endpoint exposed.
- No commit/push MCP tool exposed yet.
- GitHub remote is not updated yet; local branch is ahead of origin.

## Exact next action
Refresh the ChatGPT MCP connector schema/session and smoke-test:

```text
health
get_dirty_paths
get_recent_commits
get_repo_status
```

Expected result: health remains passed with `toolCount: 14`; `get_dirty_paths` returns clean; `get_recent_commits` shows `e06588b` as latest local commit.

## Do not do
- Do not resume live RIFT movement/proof operations from this lane.
- Do not add commit/push tools until the read-only Git-state tools are proven through the refreshed ChatGPT schema.
- Do not push until current local clean state and ahead count are verified again.
