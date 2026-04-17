---
state: historical
as_of: 2026-04-15
---

# Live Key Delivery Recheck (2026-04-15)

## Scope

This report freezes a narrow live-input recheck on `main` to answer one
practical question for actor-yaw recovery work:

> which direct key delivery path is currently trustworthy for a simple player
> turn stimulus?

## Snapshot metadata

| Field | Value |
|---|---|
| Report date | `2026-04-15` |
| Game process | `rift_x64` PID `30888` |
| Branch | `codex/actor-yaw-pitch` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Primary goal | re-check gameplay key delivery on a clean live session |
| Input mode | direct key stimulus |
| Validation status | background `PostMessage` delivery confirmed; foreground `SendInput` remains untrusted for this setup |

## Commands run

```powershell
powershell -ExecutionPolicy Bypass -File C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1 -Key A -HoldMilliseconds 500 -BackgroundProcessName Codex
```

## Artifacts checked

- `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260414-235856-393.png`
- `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260414-235911-010.png`
- `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260414-235917-889.png`

## Surviving anchors

### 1. The default `post-rift-key.ps1` path still reaches gameplay state

The default helper flow uses background `PostMessage` keydown/keyup delivery
instead of the script's foreground `SendInput` branch.

In this recheck:

- key: `A`
- hold: `500 ms`
- background focus target: `Codex`
- reported result: `SUCCESS`

The player/camera visibly turned left while Rift remained backgrounded.

### 2. The no-focus key path is usable for live turn stimulus

The before/after captures showed a clear scene rotation, which is sufficient for
stimulus verification when the immediate need is:

- confirm that gameplay input landed
- produce a left/right turn for candidate yaw comparison

That means the earlier `2026-04-14` "stimulus blocked" conclusion should be
treated as session-specific, not as a permanent failure of
`C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`.

## Broken or drifted anchors

### 1. Foreground `SendInput` is not the trusted default lane

Operator feedback from the same live-testing window reported that the foreground
`SendInput` technique did **not** produce the desired turn result, while the
background `PostMessage` technique did.

Treat that as the current workflow truth on this setup:

- prefer background `PostMessage` for gameplay key stimulus
- do **not** assume the script's `-SkipBackgroundFocus` path is equivalent
- do **not** switch actor-yaw validation back to `SendInput` without a fresh,
  dated revalidation pass

### 2. MCP/tooling foreground sends are not a no-focus substitute

Foreground-gated tooling can still be useful, but it solves a different problem.
If a tool requires the Rift window to be the true foreground window, it should
not be treated as proof that the no-focus gameplay-key lane is broken.

## Branch / workflow authority

- current living truth still belongs in
  `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- input-risk classification still belongs in
  `C:\RIFT MODDING\RiftReader\docs\input-safety.md`
- this report only freezes the specific `2026-04-15` live key-delivery recheck

## Input mode and safety notes

- no chat helper was used
- no `/reloadui` helper was used
- the preferred lane for a live gameplay turn stimulus on `main` is currently:
  `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- keep a non-Rift foreground owner such as `Codex` when intentionally testing
  the no-focus `PostMessage` path

## Immediate next step

When a live actor-yaw pass needs a controlled left/right gameplay turn on
`main`, use the default `post-rift-key.ps1` background `PostMessage` flow
first, then perform the memory/candidate before/after comparison around that
stimulus.
