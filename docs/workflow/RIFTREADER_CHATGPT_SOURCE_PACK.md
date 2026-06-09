# RiftReader ChatGPT Source Pack

## Purpose
Compact operating manual for ChatGPT project Sources. Prefer this file plus live MCP checks over stale chat memory.

## Current repo truth at creation
- Repo: `360madden/riftreader`
- Local root: `C:\RIFT MODDING\RiftReader`
- Branch target: `main`
- Verified HEAD when this pack was first created: `e1b97f6 Add Phase 1C MCP operator automation design`
- Source-pack commit: `725cb3c Add RiftReader ChatGPT source pack`
- Latest handoff at first creation: `docs/handoffs/2026-06-09-phase1b-git-state-mcp-tools-live.md`
- Current lane: MCP/local repo automation, not live game work.

Start resumed tasks by checking:

```text
health
get_repo_status
get_latest_handoff
get_workflow_control_plan
```

## Mandatory context workflow
RiftReader is a public GitHub repo. Public tracked GitHub files are immediate repo context and must be factored before coding.

Before writing or patching repo code, ChatGPT must inspect existing tracked repo files.

Required order:

```text
1. Check live local state with MCP get_repo_status.
2. Inspect existing tracked repo context.
   - Preferred after Phase 1C-B0: MCP tracked repo reader.
   - Current fallback: public GitHub repo at 360madden/riftreader.
3. Search/read existing helpers, adapter patterns, tests, wrappers, and docs.
4. Reuse or patch existing helpers before creating new ones.
5. Only then propose or generate code.
```

Do not code from memory alone when relevant tracked repo files can be inspected.

## Context authority matrix
| Need | Source |
|---|---|
| Current branch, HEAD, dirty state | MCP `get_repo_status` |
| Existing tracked repo code/docs | MCP tracked repo reader when available; public GitHub until then |
| Durable operating rules | This source pack |
| Local ignored/generated artifacts | Curated MCP tools only |
| Repo writes | Package-intake flow |
| Commit/push | Dedicated validated helper/tool only |

## MCP state
Expected runtime health: full profile, 14 tools.

Read/state tools include:
- `health`
- `get_repo_status`
- `get_latest_handoff`
- `get_workflow_control_summary`
- `get_workflow_control_plan`
- `get_dirty_paths`
- `get_recent_commits`

Package flow tools include:
- `get_package_proposal_template`
- `submit_package_proposal`
- `list_inbox`
- `create_package_draft_from_inbox`
- `review_latest_package_draft`
- `dry_run_latest_package_draft`
- `apply_latest_package_draft`

Missing automation tools to build:
- `repo_tree_tracked`
- `repo_search_tracked`
- `repo_read_tracked_file`
- `repo_read_many_tracked_files`
- `repo_context_pack`
- `run_validation_suite`
- `commit_reviewed_slice`
- `push_current_branch`

## Roadmap snapshot
- Phase 1A: done — local read-only Git-state helper.
- Phase 1B: done — MCP exposes `get_dirty_paths` and `get_recent_commits`.
- Phase 1C-A: done — operator automation design doc.
- Phase 1C-B0: next — tracked repo context reader/search tools.
- Phase 1C-B: `run_validation_suite`.
- Phase 1C-C: `commit_reviewed_slice`.
- Phase 1C-D: `push_current_branch`.
- Phase 1C-E: refresh connector schema and prove tools from ChatGPT.

## Operating mode
This is a personal R&D repo. Optimize for speed, discovery, and recoverable iteration.

Default posture:

```text
fast by default
machine-verified
recoverable-error tolerant
minimal human transport
hard stop only for destructive or sensitive boundaries
```

Treat operator approval as permission to proceed, not proof that a patch is safe. Safety must come from deterministic repo checks.

## Fast-lane policy
For docs, status, handoff, source-pack, and scoped helper work:
- batch apply → validate → commit when checks pass
- avoid making the operator inspect every token or diff
- use repo-owned helpers and MCP tools whenever possible

For code/tooling changes:
- inspect tracked repo context first
- reuse existing helpers first
- patch or create repo-owned helpers for repeated workflows
- keep JSON output clean in JSON mode
- keep errors recoverable and easy to inspect

Hard-stop areas:
- branch rewrite, force push, reset, clean, bulk deletion
- credentials, account, domain, or tunnel registration changes
- live game control lanes
- broad arbitrary command tools

## Coding rules
- Python-first for substantial helpers.
- Thin `.cmd` wrappers are acceptable for launching.
- No `git add .`.
- Stage explicit paths only.
- Compare sorted cached paths before commit.
- Verify repo status before mutation.
- Verify post-commit clean state.
- Verify remote SHA after push.
- Long helpers should include timeout, artifacts, stdout/stderr capture, and compact JSON.
- Scripts should include Version, Total-Character-Count, Purpose, and END_OF_SCRIPT_MARKER.

## Repo map
```text
tools/riftreader_workflow/        Python helpers and MCP adapter
scripts/                          wrappers and validation entrypoints
docs/workflow/                    workflow docs, source pack, contracts
docs/handoffs/                    handoffs
.riftreader-local/                local generated artifacts and inboxes
START_RIFTREADER_CHATGPT_MCP.cmd  MCP launcher
```

## Known failure fixes
- Connector schema can lag runtime tool count; refresh session/new chat if health shows tools not callable.
- MCP network calls can fail transiently; recheck `health` and retry smaller packages.
- Platform safety may block a tool call before the repo sees it; verify repo state before fallback.
- Windows `.cmd` from Python should use `cmd.exe /d /c script.cmd`.
- Failed helpers often leave repo clean; verify before retrying.

## Best next actions
1. Use this file in the ChatGPT project Sources tab.
2. Build Phase 1C-B0 tracked repo reader/search tools.
3. Build `run_validation_suite`.
4. Build `commit_reviewed_slice`.
5. Build `push_current_branch`.
6. Update this file when MCP surface or operating policy changes.
