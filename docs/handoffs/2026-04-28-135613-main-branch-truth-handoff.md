---
state: current
as_of: 2026-04-28T13:56:13-04:00
branch: main
---

# Branch Truth Handoff — 2026-04-28 13:56 EDT

## TL;DR

The canonical code-truth as of this handoff is **`main` and `navigation` aligned at `058979e...`** and both match `origin/main` + `origin/navigation` with no divergence. No local code changes are pending.

## Current repo status

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Active branch | `main` |
| Worktree state | Clean (`git status --short --branch`)|
| Current commit | `058979eb1209b2d6c7a8759258bd710d78acbad2` |
| `main` | `058979eb1209b2d6c7a8759258bd710d78acbad2` |
| `navigation` | `058979eb1209b2d6c7a8759258bd710d78acbad2` |
| `origin/main` | `058979eb1209b2d6c7a8759258bd710d78acbad2` |
| `origin/navigation` | `058979eb1209b2d6c7a8759258bd710d78acbad2` |

## Canonical branch comparison

| Comparison | Result |
|---|---|
| `main` vs `navigation` | `0 0` (in sync) |
| `origin/main` vs `origin/navigation` | `0 0` (in sync) |
| `main` vs `origin/main` | `0 0` (in sync) |
| `navigation` vs `origin/navigation` | `0 0` (in sync) |

## Supporting branch map

| Local branch | Relationship to `main` | Notes |
|---|---|---|
| `main` | `0` ahead, `0` behind | Canonical integration branch. |
| `navigation` | `0` ahead, `0` behind | Canonical integration branch. |
| `codex/actor-yaw-pitch` | behind `main` by 13 (with 129 ahead of main ancestry) | Not synced; no active merge target now. |
| `codex/camera-yaw-pitch` | behind `main` by 3 (with 129 ahead of main ancestry) | Camera branch work in separate lane. |
| `facing` | behind by 9 | Separate actor-facing lane. |
| `scanner-with-debug` | behind by 22 | Contains recovery scanner work, not merged into main yet. |
| `xyz` | behind by 21 | Utility lane, separate. |
| `codex/preserve-navigation-local-20260428-105610` | behind by 7 | Preserved navigation-pre-merge lane tip `0679fa3`; no active merge path now. |
| `codex/preserve-main-local-20260428-105610` | behind by 123, ahead by 4 | Preserved actor-orientation lane intentionally held as historical reference. |
| `feature/camera-orientation-discovery` | behind by 146, ahead by 69 | Camera work is in `C:\RIFT MODDING\RiftReader_camera_feature` worktree, not in main. |

## Worktree/branch topology at handoff time

| Worktree | Branch |
|---|---|
| `C:\RIFT MODDING\RiftReader` | `main` |
| `C:\RIFT MODDING\RiftReader_camera_feature` | `feature/camera-orientation-discovery` |
| `C:\RIFT MODDING\RiftReader_facing` | `Recovery` |
| `C:\RIFT MODDING\RiftReader_apr15_replay` | detached/head `73e7e6e3` |

## Commands run to validate truth

```powershell
git fetch --all --prune
git status --short --branch
git rev-parse main
git rev-parse navigation
git rev-parse origin/main
git rev-parse origin/navigation
git rev-list --left-right --count main...navigation
git rev-list --left-right --count origin/main...origin/navigation
```

## Related current-truth documents

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-28-main-navigation-merge-status.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-28-preserved-main-local-actor-orientation-review.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` *(note: timestamped 2026-04-23 and includes earlier runtime claims)*

## Decision

**Use `main` (same as `navigation`) for all continuation work today.**
Do not merge either preserved branch wholesale. Treat preserve branches as historical recovery material unless a focused revalidation branch is created.

## Top 5 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Continue from `main`/`navigation` in a new feature branch for any new change | Preserves clean canonical baseline and keeps CI history intact. |
| 2 | Avoid touching preserved local branches unless they are revalidated in isolation | Prevents reintroducing merge-conflict-prone content. |
| 3 | Re-run lightweight proof/offline validation commands before next live or route work | Keeps proof state trustworthy after each change. |
| 4 | Update this handoff any time runtime proof anchors change (`current-truth.md` / proof artifacts) | Keeps branch truth and runtime truth synchronized. |
| 5 | Preserve a final post-change commit of `docs/analysis` status files for any further branch promotions | Minimizes ambiguity during future branch checks. |
