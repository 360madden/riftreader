---
state: historical
as_of: 2026-04-14
---

# Cheat Engine Reintegration and Attach-Failure Plan (2026-04-14)

## Scope

This report records the current unattended plan for bringing Cheat Engine back
into the active RiftReader workflow **without** immediately patching the CE Lua
debugger-attach path.

It freezes three things:

- the current bounded role for CE
- the exact Lua attach sites that would need guards later
- the decision to wait for **multiple fresh attach failures** before changing
  those guard points

## Snapshot metadata

| Field | Value |
|---|---|
| Date | `2026-04-14` |
| Branch | `codex/actor-yaw-pitch` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Goal | reintegrate CE safely while preserving scan and trace capabilities |
| Input mode | repo inspection + user-provided CE error screenshot |
| Live CE trace commands run in this pass | none |
| Attach symptom reported by operator | `Error attaching the windows debugger: 87` |
| Guard-change policy | **defer guard patching until multiple repeated fresh attach failures are logged** |

## Commands run

No new live CE attach or breakpoint runs were executed during this pass.

Repo inspection commands used:

```powershell
git grep -n "debugProcess\|debug_isDebugging\|debug_canBreak\|debug_setBreakpoint" -- scripts/cheat-engine scripts
Get-Content C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderWriteTrace.lua
Get-Content C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderSelectorTrace.lua
Get-Content C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderProjectorTrace.lua
Get-Content C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1
Get-Content C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1
Get-Content C:\RIFT MODDING\RiftReader\scripts\trace-player-state-projector.ps1
```

## Artifacts checked

- operator-provided screenshot showing:
  - `Error attaching the windows debugger: 87`
- `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderWriteTrace.lua`
- `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderSelectorTrace.lua`
- `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderProjectorTrace.lua`
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-state-projector.ps1`
- `C:\RIFT MODDING\RiftReader\docs\cheat-engine-workflow.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md`

## Surviving anchors

### 1. CE still has value as an interactive workbench

The current repo still benefits from CE for:

- grouped family inspection
- changed/unchanged narrowing
- address-list validation
- quick structure inspection
- disassembly cluster capture

Those uses remain worth keeping in the workflow.

### 2. The debugger-attach sites are narrow and identifiable

The current CE Lua attach path is concentrated in three `arm(...)` functions:

- `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderWriteTrace.lua:507-520`
- `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderSelectorTrace.lua:245-258`
- `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderProjectorTrace.lua:224-237`

Each uses this same pattern:

1. `openProcess(processName)`
2. `if not debug_isDebugging() then debugProcess(2) end`
3. wait for `debug_canBreak()`
4. call `debug_setBreakpoint(...)`

## Broken or drifted anchors

### 1. The observed instability appears earlier than repo trace logic

The operator reported that CE often crashes or fails **as soon as it attaches**,
independent of `/reloadui` or later game/UI behavior.

The observed dialog was:

> `Error attaching the windows debugger: 87`

That means the leading suspected failure point is the CE debugger-attach layer,
not the later trace callback/body logic.

### 2. CE debugger-trace mode should not be the default first lane

Given the attach symptom above, the repo should not currently treat:

- coord write trace
- selector-owner trace
- projector trace

as the default first move for every recovery pass.

## Branch / workflow authority

The current recommended split is:

### CE scan / inspection lane

Use by default when CE is involved:

- load/update `RiftReaderProbe.lua`
- run changed/unchanged scans
- inspect candidate families manually
- materialize address-list groups
- capture cluster/context artifacts that do not require a live debugger attach

### CE debugger-trace lane

Use only when explicitly needed:

- `trace-player-coord-write.ps1`
- `trace-player-selector-owner.ps1`
- `trace-player-state-projector.ps1`

This lane is **opt-in** until repeated attach failures are logged and the
suspected `debugProcess(2)` failure point is either confirmed or ruled out.

## Input mode and safety notes

This pass used:

- repo inspection only
- no new live CE debugger attaches
- no game-window input

The only live evidence added in this pass was the user-provided screenshot of
the CE attach error dialog.

## Ranked todo list

| Rank | Task | Current state |
|---|---|---|
| 1 | Split CE into scan/inspection lane vs debugger-trace lane | documented |
| 2 | Keep reader/addon as the baseline gate before CE escalation | documented |
| 3 | Start a CE crash ledger for repeated attach failures | pending |
| 4 | Rank all CE-backed scripts by risk and purpose | partially documented |
| 5 | Reintegrate CE scan mode first | ready |
| 6 | Keep debugger-trace mode opt-in only | documented |
| 7 | Confirm repeated `windows debugger: 87` failures before patching guards | pending |
| 8 | Record per-run preflight facts: elevation/session/process state | pending |
| 9 | Separate CE tasks that work without debugger attach | pending |
| 10 | Validate every useful CE finding back through the reader | active rule |
| 11 | Keep the exact Lua guard sites documented but unchanged | documented |
| 12 | Standardize expected status/output artifacts per CE-backed script | pending |
| 13 | Freeze useful CE runs faster into repo-owned artifacts | active rule |
| 14 | Define a stop threshold for abandoning CE in a bad live session | pending |
| 15 | Add a small CE reintegration checklist to the rebuild workflow | completed in docs |
| 16 | Keep CE scan/manual inspection as the normal discovery accelerator | active direction |
| 17 | Avoid making CE debugger-trace the universal first path again | active direction |
| 18 | Prepare, but do not apply, a future guard patch plan | documented only |
| 19 | Reconfirm attach failures across more than one debugger-trace script | pending |
| 20 | Resume actor-orientation work with addon/reader first, CE second | active direction |

## Immediate next step

Resume CE in **scan / inspection mode first**.

When debugger-trace is needed:

1. run it intentionally
2. log the exact attach failure if it happens
3. wait for multiple fresh repeats
4. only then patch the shared `debugProcess(2)` attach path

Do **not** change the Lua guard behavior from this report alone.
