# AGENTS.md

This file defines the default safety rules for AI agents working in this repository.

## Isolation

- Work only in an isolated fork, branch, worktree, or separate clone.
- Never modify the main repo directly unless the user explicitly asks for it.
- Never merge to `main` directly; provide a branch or PR for review.

## Default write scope

Allowed by default:

- `reader/RiftReader.Reader/**`
- task-specific files under `scripts/**` only when directly required

Read-only unless explicitly approved:

- `addon/**`
- `tools/**`
- `scripts/captures/**`
- `scripts/cheat-engine/**`
- `README.md`
- `CLAUDE.md`
- `.codex/**`
- `.claude/**`

## Forbidden without explicit approval

- Broad refactors
- Renames or moves across the repo
- Dependency updates
- Formatting-only changes
- Editing generated capture artifacts by hand
- Changing addon behavior for reader-only tasks
- Deleting files

## Change policy

- Keep changes minimal and task-focused.
- Only edit files directly needed for the task.
- Preserve existing architecture and naming unless the task requires otherwise.
- If a live trace or game-dependent step fails, stop and report the blocker instead of guessing.

## Validation

For code changes, run:

```powershell
dotnet build RiftReader.slnx
```

For script changes, run the narrowest relevant script or command and report the exact result.

## Required completion summary

Before finishing, report:

1. Root cause
2. Files changed
3. Exact validation run
4. Anything unverified

## Response style

After finishing a task, include a short optional section with practical next steps or improvement ideas only when it adds real value.
