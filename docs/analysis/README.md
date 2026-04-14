# Analysis Reports

Use `C:\RIFT MODDING\RiftReader\docs\analysis\` for **dated, append-only
reports**.

This folder is for documenting what changed during a specific investigation
window, especially after a game update or when anchor drift is detected.

## Relationship to recovery docs

Keep these roles separate:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
  - the current living truth
- `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md`
  - the rebuild order
- `C:\RIFT MODDING\RiftReader\docs\analysis\YYYY-MM-DD-<slug>.md`
  - an immutable dated report describing one investigation pass

Recovery docs answer **"what is true right now?"**

Analysis reports answer **"what did we observe during this specific run, on
this specific branch/worktree, using these specific commands?"**

## Naming

Use:

```text
YYYY-MM-DD-<slug>.md
```

Examples:

- `2026-04-14-post-update-anchor-drift-report.md`
- `2026-04-14-camera-workflow-branch-audit.md`

## When to add a new report

Add a new dated report when:

- the game updates
- a previously trusted anchor stops working
- a live workflow moves to a different branch/worktree
- a camera/actor path becomes stale or gets revalidated
- input-safety assumptions change
- a triage pass needs a frozen evidence snapshot before repair work starts

Do **not** overwrite an older report just to keep one file "current". Add a
new dated report instead, then update the recovery docs to point at the latest
one.

## Required report metadata

Every new report should capture, near the top:

1. report date
2. relevant game update/build date if known
3. repo branch
4. worktree path
5. scope
6. commands run
7. artifacts checked
8. anchors that survived
9. anchors that broke or drifted
10. artifacts now considered stale
11. authoritative script/doc location by branch when that matters
12. input mode used:
    - read-only
    - direct key/mouse stimulus
    - chat/reload/UI-intrusive helper
13. validation status
14. immediate next step

## Lightweight machine-readable status

Use this minimal status convention whenever a doc or capture needs an explicit
machine-readable freshness marker:

- `state`
  - `current`
  - `stale`
  - `historical`
- `as_of`
  - ISO date such as `2026-04-14`

For markdown reports, prefer frontmatter:

```md
---
state: historical
as_of: 2026-04-14
---
```

For existing JSON capture artifacts that you do not want to rewrite, prefer a
sidecar file:

- `player-owner-components.json`
- `player-owner-components.status.json`

Example sidecar:

```json
{
  "state": "stale",
  "as_of": "2026-04-14"
}
```

## Recommended structure

Use this order unless the investigation needs something narrower:

1. `## Scope`
2. `## Snapshot metadata`
3. `## Commands run`
4. `## Artifacts checked`
5. `## Surviving anchors`
6. `## Broken or drifted anchors`
7. `## Stale artifacts`
8. `## Branch / workflow authority`
9. `## Input mode and safety notes`
10. `## Immediate next step`

## Editing rules

- Prefer adding a new dated report over rewriting history.
- Only edit an older report for factual corrections, typos, or path fixes.
- If a report depends on live input, say exactly what kind.
- If a workflow only exists on a feature branch, state the branch and worktree
  explicitly.
- If a claim is historical only, label it that way instead of calling it
  current truth.

## Template

Start from:

- `C:\RIFT MODDING\RiftReader\docs\analysis\_template.md`
