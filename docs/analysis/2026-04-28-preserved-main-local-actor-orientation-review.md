---
state: current
as_of: 2026-04-28T13:29:17-04:00
---

# Preserved Local-Main Actor / Orientation Review — 2026-04-28

## Scope

Review the four old local-`main` commits preserved before the `navigation` to
`main` promotion and decide whether any should be ported immediately.

No live Rift input, movement, focus, clicking, typing, addon reload, or capture
was used for this review.

## Snapshot metadata

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Current `main` / `navigation` | `fc480478b388531792cca2c69c28cea50702d6c5` |
| Preserved branch reviewed | `origin/codex/preserve-main-local-20260428-105610` |
| Preserved branch tip | `410fee0f8ae23740be8ef03b34a0e7a7df0b1a70` |
| Patch equivalence vs current `main` | all four commits remain patch-unique |
| Direct merge status | not safe; content/add-add conflicts remain |

## Commands run

```powershell
git fetch --all --prune
git log --reverse --oneline main..origin/codex/preserve-main-local-20260428-105610
git cherry -v main origin/codex/preserve-main-local-20260428-105610
git show --stat --oneline --decorate 7074042
git show --stat --oneline --decorate 90ffdff
git show --stat --oneline --decorate 3186027
git show --stat --oneline --decorate 410fee0
git merge-tree --write-tree --messages main origin/codex/preserve-main-local-20260428-105610
git grep -n -- "find-player-orientation-candidate"
git grep -n -- "StimulusMode"
git grep -n -- "rebuild-from-suggested-source-chain-pattern"
```

## Preserved commits reviewed

| Commit | Preserved intent | Current-main decision |
|---|---|---|
| `7074042` | Rebuild owner/source chain from live coord-trace lineage | Do not port now; current `capture-player-source-chain.ps1` already has the newer recovery lane using `rebuild-from-suggested-source-chain-pattern` before same-session reuse fallback. |
| `90ffdff` | Add live-chain fallback controls to actor orientation scripts | Do not port now; current actor-facing refresh/proof scripts already expose the newer AutoHotkey/stimulus and source-chain recovery workflow. |
| `3186027` | Restore non-debug orientation probes and yaw candidate search | Partially superseded: current `main` already has `--find-player-orientation-candidate`, candidate ledger support, and `PlayerOrientationCandidateFinder`. The older ReaderBridge `orientationProbe` experiment is not present and should not be ported without its own validation branch. |
| `410fee0` | Add selectable stimulus modes to actor yaw candidate tests | Do not port now; current scripts already expose `StimulusMode` / AutoHotkey paths through the newer actor-facing refresh and yaw-candidate tooling. |

## Merge conflict evidence

A dry merge of the preserved branch into current `main` still reports conflicts
in these areas:

| Area | Conflict files |
|---|---|
| Reader snapshot / CLI | `ReaderBridgeSnapshot.cs`, `ReaderBridgeSnapshotLoader.cs`, `ReaderOptions.cs`, `ReaderOptionsParser.cs`, `Program.cs` |
| Actor/source-chain scripts | `capture-actor-orientation.ps1`, `capture-player-owner-components.ps1`, `capture-player-source-chain.ps1`, `capture-player-trace-cluster.ps1`, `trace-player-selector-owner.ps1` |
| Input/yaw helpers | `find-player-orientation-candidate.ps1`, `post-rift-command*.ps1`, `post-rift-key.ps1`, `send-rift-key*.ps1`, `send-rift-key-ahk.ahk`, `test-actor-yaw-candidates.ps1` |

## Current coverage

Current `main` already contains the higher-value parts of the preserved branch's
intent:

- `--find-player-orientation-candidate` exists in the reader CLI.
- `OrientationCandidateLedgerLoader` and `PlayerOrientationCandidateFinder`
  exist under `reader/RiftReader.Reader/Models`.
- `test-actor-yaw-candidates.ps1`, `send-rift-key-ahk.ps1`, and
  `send-rift-key-ahk.ahk` exist on current `main`.
- `StimulusMode` is wired through the current actor-facing refresh path.
- `capture-player-source-chain.ps1` has the current
  `rebuild-from-suggested-source-chain-pattern` recovery mode.

## Not ported now

The preserved ReaderBridge `orientationProbe` experiment is intentionally left
unported.

Reason:

- current living actor-facing truth is memory-backed, not addon/API-backed;
- current docs still treat ReaderBridge orientation signal as empty on the live
  client;
- porting the addon probe would change the ReaderBridge export contract and
  should be validated with addon sync / `/reloadui` / snapshot parsing in its
  own focused branch.

## Decision

Do not merge or cherry-pick `origin/codex/preserve-main-local-20260428-105610`
into current `main`.

Keep the preservation branch available as historical recovery material. If
ReaderBridge orientation probing becomes useful again, restart from the old
`3186027` implementation in a dedicated branch and add tests plus live addon
validation before promotion.

## Immediate next step

Leave current `main` / `navigation` aligned and continue from the newer
actor-facing and navigation workflows already on `main`. Open a separate
feature branch only if the ReaderBridge orientation-probe experiment becomes a
priority.
