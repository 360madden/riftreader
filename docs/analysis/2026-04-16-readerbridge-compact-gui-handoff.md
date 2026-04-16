---
state: historical
as_of: 2026-04-16
---

# ReaderBridge Compact GUI Fix Handoff (2026-04-16)

## Scope

This handoff freezes the repair pass for the **compact ReaderBridge status
panel** loaded from:

- `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge.lua`

The pass covered three live in-game regressions reported and manually verified
by the user:

1. compact GUI layout corruption after dragging the panel away from its initial
   post-`/reloadui` position
2. `/readergui reset` toggling or failing to restore the panel correctly
3. `/readergui help` hiding the panel and printing no chat feedback

This report is meant as a session handoff for the next agent, not as a
permanent replacement for the recovery docs.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `historical` |
| As of | `2026-04-16` |
| Report date | `2026-04-16` |
| Game update/build date | unknown |
| Branch | `main` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Input mode | repo file edits + addon deployment; in-game validation performed manually by user |
| Validation status | partial working |

## Commands run

```powershell
cmd /c C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd
cmd /c C:\RIFT MODDING\RiftReader\scripts\deploy-addon.cmd
git branch --show-current
git status --short
git diff --stat
```

Additional targeted inspection commands were used during diagnosis to read:

- `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge.lua`
- `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge_UI.lua`
- `C:\RIFT MODDING\RiftReader\addon\ReaderBridgeExport\main.lua`
- `C:\RIFT MODDING\RiftReader\addon\RiftReaderValidator\main.lua`

## Artifacts checked

- `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge.lua`
- `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge_UI.lua`
- `C:\RIFT MODDING\RiftReader\scripts\deploy-addon.cmd`
- `C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd`
- `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ReaderBridge\ReaderBridge.lua`
- `C:\Users\mrkoo\Documents\RIFT\Interface\Addons\ReaderBridge\ReaderBridge.lua`

## Files touched this pass

| File | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge.lua` | Fixed numeric coercion crash paths, compact GUI drag layout, and `/readergui` subcommand behavior |
| `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\RiftAddon.toc` | Imported as canonical tracked manifest during earlier part of this session |
| `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge_Logic.lua` | Imported from live addon folder as auxiliary source |
| `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge_UI.lua` | Imported from live addon folder as auxiliary source; not the active compact GUI path |
| `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\README.md` | Added canonical-source notes |
| `C:\RIFT MODDING\RiftReader\scripts\deploy-addon.cmd` | Now deploys toc-driven addons and syncs every detected Rift `Interface\AddOns` root |
| `C:\RIFT MODDING\RiftReader\scripts\validate-addon.cmd` | Now validates all `.lua` files for toc-driven addons too |
| `C:\RIFT MODDING\RiftReader\README.md` | Updated repo layout and deploy behavior notes |
| `C:\RIFT MODDING\RiftReader\docs\overview.md` | Added ReaderBridge addon capability summary |

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| Repo canonical source | working | `addon\ReaderBridge\ReaderBridge.lua` is now the tracked source of truth for the live addon |
| Multi-root deployment | working | `deploy-addon.cmd` syncs both OneDrive and Documents addon roots |
| Lua validation | working | `validate-addon.cmd` passed after each patch pass |
| Compact GUI drag behavior | working | user reported the compact GUI now drags cleanly without visual corruption |
| `/readergui reset` | working by user report | after final slash-command patch, user reported the issue looked fixed |
| `/readergui help` | working by user report | final patch added explicit help handling and chat output; user reported the command set looked fixed afterward |

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| Large alternate UI file (`ReaderBridge_UI.lua`) | unused / unverified | present in repo and syntax-valid, but screenshots proved the active compact HUD path lives in `ReaderBridge.lua` |
| Compact GUI position persistence | not implemented | panel still resets to default after reload unless a future pass adds saved position state |

## Stale artifacts

- No new stale analysis artifact was created during this pass.
- `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge_UI.lua` should **not**
  be treated as evidence for the compact HUD bug; it was the wrong UI path for
  this issue.

## Key fixes landed

### 1) Numeric coercion hardening

The original runtime crash was:

- `bad argument #1 to 'floor' (number expected, got string)`

Fixes were added so numeric-like Rift API values are coerced through
`tonumber()` before `floor`, formatting, resource comparisons, and percent
calculations.

### 2) Compact GUI drag/layout repair

The compact panel in `ReaderBridge.lua` used:

- `guiFrame:ClearAll()`
- `guiFrame:SetPoint(...)`

during drag, without reapplying all expected frame/header sizing. That matched
the reported visual corruption after moving the panel. The fix introduced a
single helper to re-anchor the panel while also restoring expected frame/header
dimensions and explicit text widths.

### 3) `/readergui` command parsing fix

The slash handler originally treated `args` like a token array instead of a raw
string. That caused subcommands such as `reset` and `help` to miss their branch
and fall through to the default toggle behavior. The fix changed parsing to:

```lua
local arg = string.match(args or "", "^(%S+)")
```

and added explicit `help` plus unknown-command feedback.

## Branch / workflow authority

Current authority for the live ReaderBridge addon during this pass:

- repo source: `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\`
- branch: `main`
- deployment helper: `C:\RIFT MODDING\RiftReader\scripts\deploy-addon.cmd`

The active installed addon copies now live in both:

- `C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ReaderBridge`
- `C:\Users\mrkoo\Documents\RIFT\Interface\Addons\ReaderBridge`

The deployment script syncs both roots, so future edits should be made in the
repo and pushed via `deploy-addon.cmd`, not by editing either installed copy
directly.

## Input mode and safety notes

- No automated key injection or `/reloadui` helper was run from this repair pass.
- No direct mouse automation was used.
- In-game validation was manual and user-driven:
  - user dragged the compact GUI
  - user ran `/readergui ...` slash commands
  - user reported whether the behavior was fixed
- Repo-side commands were limited to inspection, patching, syntax validation,
  and deployment.

## Immediate next step

If another compact GUI bug appears, start in:

- `C:\RIFT MODDING\RiftReader\addon\ReaderBridge\ReaderBridge.lua`

and reproduce it against the **compact** HUD path before assuming
`ReaderBridge_UI.lua` is involved.

Most likely next improvements, in order:

1. persist compact GUI position across `/reloadui`
2. add a small `/readergui status` or `/readergui pos` diagnostic command
3. optionally harden `ReaderBridge_UI.lua` with the same drag/anchor safeguards
   if that larger HUD path is ever re-enabled
