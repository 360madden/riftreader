# RiftReader MCP Phase 1C operator automation design

## Status
Design-only proposal.

## Baseline
- Repo is clean and synced at `3a6cd10 Record Phase 1B MCP Git-state tool status`.
- MCP health reports full profile with 14 tools.
- Phase 1B added read-only Git-state tools: `get_dirty_paths` and `get_recent_commits`.
- Latest handoff: `docs/handoffs/2026-06-09-phase1b-git-state-mcp-tools-live.md`.

## Problem
The workflow is safe but still too manual. For routine repo work, ChatGPT should not need to create downloadable runners, have the operator run them, then parse pasted output. The repo should expose narrow, repo-owned helpers through MCP instead.

## Goal
Move repeated validated workflows into MCP tools while keeping hard gates for mutation:

1. Read state directly.
2. Validate through fixed repo-owned profiles.
3. Apply reviewed packages through the existing approval-token gate.
4. Commit reviewed slices with explicit path staging only.
5. Push the current branch only after explicit operator approval and remote SHA verification.

## Proposed tools

### `run_validation_suite`
Read-only. Runs fixed validation profiles only. No ad-hoc command passthrough.

Profiles:
- `mcp-smoke`: manifest and local read-only Git-state checks.
- `python-core`: selected py_compile and unit tests.
- `package-draft`: latest operator package dry-run checks.

### `commit_reviewed_slice`
Local Git mutation. Commits only an explicit reviewed path allowlist.

Fail-closed gates:
- configured RiftReader repo root only
- allowed branch only, default `main`
- dirty paths exactly match requested paths
- no absolute paths or repo escapes
- no target paths under local artifact roots
- stage explicit paths only with `git add -- <paths>`
- sorted cached-path comparison equals requested paths
- diff checks pass before and after staging
- commit hooks pass
- post-commit worktree clean

### `push_current_branch`
Remote Git mutation. Pushes only current branch to upstream after explicit approval.

Fail-closed gates:
- clean worktree and no staged files
- branch equals requested branch, default `main`
- upstream equals `origin/main` unless configured otherwise
- remote URL matches expected repo identity
- local HEAD matches expected SHA
- push command is limited to the expected remote and branch
- post-push remote SHA must match local HEAD
- post-push status must be clean and synced

## Approval model
- Read-only validation: no approval.
- Package apply: existing dry-run diff hash plus approval token.
- Commit: explicit operator approval or token tied to preflight facts.
- Push: explicit operator approval tied to branch, remote, and expected HEAD.

## Implementation order
1. Implement `run_validation_suite` local helper and MCP wrapper.
2. Implement `commit_reviewed_slice` local helper and MCP wrapper.
3. Implement `push_current_branch` local helper and MCP wrapper.
4. Refresh connector schema and prove tools from ChatGPT.

## Guardrails
- Do not build a general command endpoint as a shortcut.
- Do not mix this lane with live-game workflow lanes.
- Do not let ChatGPT approve its own remote mutation.
- Do not rely on stale chat memory when MCP can verify state.
