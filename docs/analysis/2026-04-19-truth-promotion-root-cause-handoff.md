---
state: current
as_of: 2026-04-19
---

# Truth-Promotion Root-Cause Handoff (2026-04-19)

## Scope

This handoff freezes the current state of branch `scanner-with-debug` after the
latest push on:

- coord-write proof observability
- coord-refresh candidate diversification
- source / owner-chain pivot after repeated `armed-no-hit` refresh failures

The branch goal is still to promote actor-yaw / coord truth safely, but the
current work shows the remaining blocker is deeper than stale CE artifacts or
bad refresh wiring.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `current` |
| As of | `2026-04-19` |
| Report date | `2026-04-19` |
| Branch | `scanner-with-debug` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Input mode | repo edits + local PowerShell validation + bounded live trace / key-stimulus checks against foreground `rift_x64.exe` |
| Validation status | partial working |

## Commands run

```powershell
git branch --show-current
git status --short
pwsh -NoLogo -NoProfile -File 'C:\RIFT MODDING\RiftReader\scripts\cheatengine-exec.ps1' -LuaFile 'C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderWriteTrace.lua'
pwsh -NoLogo -NoProfile -File 'C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1' -Json -SkipRefresh -RefreshTraceAnchor -TraceRefreshOnly -RecoveryAttempts 0 -ProcessName rift_x64 -TraceRefreshStimulusMode AutoHotkey
pwsh -NoLogo -NoProfile -File 'C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1' -Json
pwsh -NoLogo -NoProfile -File 'C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1' -Json -ForceDebuggerTrace -NoFallback -TimeoutSeconds 4 -MaxArmAttempts 1
```

## Artifacts checked

- `C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\cheat-engine\RiftReaderWriteTrace.lua`
- `C:\RIFT MODDING\RiftReader\scripts\captures\ce-smart-player-family.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\coord-trace-refresh\coord-trace-refresh-f943ef4bf5fd4511a32bdbd76e207788-debug-register-access.attempt.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-source-chain.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-19-scanner-with-debug-resume-handoff.md`

## Files touched this pass

| File | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1` | Added explicit `armed-no-hit` / timeout diagnostics, diversified early candidate selection across families, and surfaced watch-mode / stimulus-attempt evidence |
| `C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1` | Made coord refresh cheaper and more observable with pass sequencing across stimulus modes, access-watch fallback, and clearer refresh failure summaries |
| `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1` | Updated workflow summary handling so refresh failures now preserve last-attempt details instead of hiding behind a generic timeout |

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| Current-player memory read | working | `read-player-current.ps1` still resolves the player and matches addon-export expected coords/health |
| Debug/watch arm path | working | Refresh attempts reach `armed` on `interface-2 + debug-register`; this is no longer failing at preflight/attach time |
| Current-process CE confirmation rebuild | working | `C:\RIFT MODDING\RiftReader\scripts\captures\ce-smart-player-family.json` was rebuilt on `2026-04-19T15:13:08Z` and yielded fresh current-process candidate `0x1B0D268A9D0` |
| Coord-refresh observability | working | Attempt artifacts now capture candidate, family, attach label, breakpoint method, watch mode, key used, elapsed time, and sampled movement delta |
| Candidate diversification | working | Refresh no longer burns the first four slots inside one coord-family blob; it now samples multiple family classes early |
| Source-chain reconstruction | partial working | `capture-player-source-chain.ps1` reconstructed the selector/container/load chain and produced a live selector pattern for the current process |

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| Direct movement evidence outside trace | blocked | Before/after current-player reads for `w`, `d`, `a`, and `s` stayed at `7416.6797 / 863.6 / 2957.8198` with `Magnitude = 0.0` |
| Write-mode coord proof | blocked | Refresh reaches `armed` / `armed-no-hit` but never records a coord-write hit on fresh current-process candidates |
| Access-mode coord proof | blocked | `coord-trace-refresh-f943ef4bf5fd4511a32bdbd76e207788-debug-register-access.attempt.json` shows four diversified candidates still timing out with `WatchMode = Access` and sampled delta `0.0` |
| Selector-owner live proof | blocked | Forced `trace-player-selector-owner.ps1 -ForceDebuggerTrace -NoFallback` stalled at `armed`; the persisted JSON is a cached-fallback artifact, not a live proof hit |
| Truth promotion | still blocked | `TraceMatchesProcess = true` has not been re-established, so promotion-ready truth has not been produced |
| Worktree cleanliness | mixed | Modified files remain unstaged: `debug\workflow-hud-status.json`, `scripts\read-player-current.ps1`, `scripts\run-actor-yaw-debug-scan.ps1`, `scripts\trace-player-coord-write.ps1` |

## Root-cause statement frozen here

| Type | Statement |
|---|---|
| Proven | The remaining blocker is **not primarily refresh wiring, stale CE artifacts, or single-family candidate ordering** |
| Proven | The current `rift_x64.exe` session is **not producing qualifying coord or owner memory activity** for the current proof path under the bounded movement/debug windows that were tested |
| Best current hypothesis | The authoritative current-process source is likely higher in the **source / owner chain**, while the movement-driven coord-blob proof path is low-yield in this client state |

## Stale / misleading artifacts

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json` remains stale and should **not** be treated as fresh coord proof for the current process.
- `C:\RIFT MODDING\RiftReader\scripts\captures\player-selector-owner-trace.json` currently reflects **cached-fallback recovery**, not a successful live forced-trace hit.
- `C:\RIFT MODDING\RiftReader\debug\workflow-hud-status.json` is a runtime status artifact and not part of the truth-promotion code change itself.

## Validation results frozen here

| Check | Result | Notes |
|---|---|---|
| PowerShell parse: `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1` | passed | No syntax errors |
| PowerShell parse: `C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1` | passed | No syntax errors |
| PowerShell parse: `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1` | passed | No syntax errors |
| CE Lua load: `cheatengine-exec.ps1 -LuaFile ...RiftReaderWriteTrace.lua` | passed | Returned `1` |
| Refresh-only coord pass | blocked with explicit diagnostics | Final reason is now `trace-refresh-armed-no-hit` instead of an opaque wrapper timeout |
| Latest access-mode refresh artifact | blocked | Four diversified candidates, all `timeout`, `WatchMode = Access`, sampled movement delta `0.0` |
| Direct no-trace movement checks (`w/d/a/s`) | blocked | Memory coords never changed in the sampled current-player reads |
| `capture-player-source-chain.ps1 -Json` | passed | Reconstructed selector/container lineage and wrote `player-source-chain.json` |
| `trace-player-selector-owner.ps1 -Json -ForceDebuggerTrace -NoFallback -TimeoutSeconds 4 -MaxArmAttempts 1` | failed | Ended with status `armed`; no live owner/source proof hit was captured |
| Full actor-yaw workflow rerun after latest pivot | not run | Deferred because the coord/owner gate is still the dominant blocker |

## Current working design snapshot

### Refresh path

- prefer narrow fast refresh first:
  - `interface-2`
  - `debug-register`
  - short hold / short timeout
- if still blocked, widen through:
  - alternate stimulus modes
  - access-watch fallback
- persist per-attempt artifact with:
  - candidate family
  - attach label
  - breakpoint method
  - watch mode
  - stimulus key
  - sampled before/after coords

### Current live interpretation

- The repo can still **read** the right player coords.
- The repo can still **arm** the debug/watch path.
- The repo is **not** currently proving the authoritative coord/owner source for
  this process instance.

## Branch / workflow authority

Current authority for the next resume point:

- branch: `scanner-with-debug`
- worktree: `C:\RIFT MODDING\RiftReader`
- truth-promotion wrapper:
  - `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1`
- refresh-only proof entrypoint:
  - `C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1 -RefreshTraceAnchor -TraceRefreshOnly`
- coord proof engine:
  - `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1`
- source/owner pivot entrypoints:
  - `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1`
  - `C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1`
- truth gate:
  - `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`

## Input mode and safety notes

- This pass used bounded live attach / trace attempts and short foreground key
  stimuli only.
- This pass did **not** restore promotion-ready truth.
- This pass did **not** depend on `/reloadui`.
- This pass did **not** produce a fresh authoritative coord-write or
  selector-owner proof artifact for the current process.
- No staging or commit was performed.

## Recommended first action in the next conversation

Stop spending the next pass on more coord-blob movement retries.

Instead:

1. make `C:\RIFT MODDING\RiftReader\scripts\trace-player-selector-owner.ps1`
   produce a **current-process live hit** instead of cached fallback
2. feed that owner/source proof back into
   `C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1`
3. only rerun the full actor-yaw promotion wrapper after the owner/source path
   starts producing current-process proof
