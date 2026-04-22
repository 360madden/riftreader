# Cheat Engine table preservation

Use this folder for **durable Cheat Engine `.ct` snapshots** that would be
painful to reconstruct from scratch.

## When to save a `.ct`

Save a table when it contains any of the following:

- hand-curated address lists or structure groups
- watch expressions that prove a source chain, selector path, or basis lane
- CE-only progress that is not already captured in repo scripts or JSON
- intermediate work that could be lost by a Rift restart, CE restart, or branch
  switch

Do **not** rely on `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\` for this.
That folder is treated as generated/local helper output and is ignored by git.

## Naming convention

Prefer:

`YYYY-MM-DD-topic-short-description.ct`

Examples:

- `2026-04-22-actor-facing-source-lane.ct`
- `2026-04-22-selector-owner-rebuild.ct`

## Sidecar note

For each saved `.ct`, add a short sibling note:

`YYYY-MM-DD-topic-short-description.md`

Include:

- branch/worktree used
- Rift process/build or PID if relevant
- what the table proves
- what remains tentative
- which repo scripts/docs/handoffs depend on it

## Goal

The goal is simple: if CE or Rift closes unexpectedly, the repo should still
retain the important reverse-engineering state needed to continue work.
