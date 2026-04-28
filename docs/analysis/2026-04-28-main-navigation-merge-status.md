---
state: current
as_of: 2026-04-28T13:13:26-04:00
---

# Main / Navigation Merge Status — 2026-04-28

## Scope

Record the safe promotion of `navigation` into `main` and the follow-up branch
alignment performed after PR #4.

No live game input, movement, focus, clicking, typing, or capture was used for
this status pass.

## Snapshot metadata

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Promotion PR | `https://github.com/360madden/riftreader/pull/4` |
| Merged `main` commit | `5807cfaede2cf915007455e35e98e38a16e71126` |
| `origin/main` | `5807cfaede2cf915007455e35e98e38a16e71126` |
| `origin/navigation` after fast-forward | `5807cfaede2cf915007455e35e98e38a16e71126` |
| Branch comparison after fast-forward | `origin/main...origin/navigation = 0 / 0` |

## Commands run

```powershell
git fetch --all --prune
git rev-list --left-right --count main...navigation
git rev-list --left-right --count origin/main...origin/navigation
dotnet build .\RiftReader.slnx
dotnet test .\RiftReader.slnx --no-build
```

## Branch / workflow authority

`main` now contains the promoted `navigation` work from PR #4.

`navigation` was fast-forwarded to the merged `main` commit and pushed, so the
remote branches are aligned again.

The old local-main-only actor/orientation commits were intentionally not folded
into PR #4 because merge simulation showed content conflicts. They remain
preserved for separate review at:

- `origin/codex/preserve-main-local-20260428-105610`

The pre-promotion navigation tip remains preserved at:

- `origin/codex/preserve-navigation-local-20260428-105610`

## Validation status

| Gate | Result |
|---|---|
| Pre-promotion `navigation` build | Passed |
| Pre-promotion `navigation` tests | Passed, `70/70` |
| Integration branch `git diff --check` | Passed |
| Integration branch build | Passed |
| Integration branch tests | Passed, `70/70` |
| Post-merge `main` build | Passed |
| Post-merge `main` tests | Passed, `70/70` |

## Immediate next step

Review `origin/codex/preserve-main-local-20260428-105610` separately before
deciding whether any of its actor/orientation work should be ported onto the
new `main`.
