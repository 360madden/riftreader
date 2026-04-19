---
state: current
as_of: 2026-04-19
---

# Scanner-with-debug Resume Handoff (2026-04-19)

## Scope

This handoff freezes the current state of branch `scanner-with-debug` after the
latest pass on:

- the **actor-yaw proof / truth-promotion workflow**
- the **coord-anchor refresh safety path**
- the new **RiftReader Workflow HUD** utility

The branch goal is still to prove a reliable actor-yaw source strongly enough
to promote it to repo truth, while keeping the live workflow safer and easier
to observe during foreground gameplay.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `current` |
| As of | `2026-04-19` |
| Report date | `2026-04-19` |
| Game update/build date | unknown |
| Branch | `scanner-with-debug` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Input mode | repo edits + local PowerShell/.NET validation + bounded live HUD checks with RIFT foreground |
| Validation status | partial working |

## Commands run

```powershell
git branch --show-current
git status --short
dotnet build 'C:\RIFT MODDING\RiftReader\tools\RiftReader.WorkflowHud\RiftReader.WorkflowHud.csproj' --nologo
dotnet build 'C:\RIFT MODDING\RiftReader\RiftReader.slnx' --nologo
pwsh -NoLogo -NoProfile -File 'C:\RIFT MODDING\RiftReader\scripts\write-workflow-hud-status.ps1' -State active -Action 'candidate proof'
pwsh -NoLogo -NoProfile -File 'C:\RIFT MODDING\RiftReader\scripts\run-workflow-hud.ps1'
pwsh -NoLogo -NoProfile -File 'C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1' -Json -ProcessName '__rift_missing__'
pwsh -NoLogo -NoProfile -File 'C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1' -Json -SkipStimulus
```

## Artifacts checked

- `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\write-workflow-hud-status.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\run-workflow-hud.ps1`
- `C:\RIFT MODDING\RiftReader\tools\RiftReader.WorkflowHud\Program.cs`
- `C:\RIFT MODDING\RiftReader\tools\RiftReader.WorkflowHud\RiftReader.WorkflowHud.csproj`
- `C:\RIFT MODDING\RiftReader\tools\RiftReader.WorkflowHud\WorkflowHudForm.cs`
- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-18-rift-yaw-pointer-scan-guidance-alignment.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-17-native-debug-scanning-handoff.md`

## Files touched this pass

| File | Reason |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1` | Published HUD phase updates, final HUD summary state, and best-effort status writes throughout the live workflow |
| `C:\RIFT MODDING\RiftReader\scripts\write-workflow-hud-status.ps1` | Added stale heartbeat fields, last-message persistence, and quiet mode for script-driven status publishing |
| `C:\RIFT MODDING\RiftReader\tools\RiftReader.WorkflowHud\WorkflowHudForm.cs` | Added heartbeat/stale detection, debounce/minimum display time, and last-message-aware rendering while preserving no-activate + draggable HUD behavior |

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| HUD utility build | working | `RiftReader.WorkflowHud` builds cleanly and is already included in `C:\RIFT MODDING\RiftReader\RiftReader.slnx` |
| HUD visual contract | working | Fixed-size rounded HUD with one name/version line (`RiftReader Workflow HUD v0.1.0`) plus one centered status row |
| No-focus behavior | working | Live validation kept the foreground window title as `RIFT` before and after HUD launch |
| Draggable + saved position | working at code level | Existing HUD position persistence remains intact; no regression introduced in this pass |
| Status contract | working | `state`, `action`, `updatedAtUtc`, `staleAfterSeconds`, `lastMessage`, and `lastMessageAtUtc` are now written to the repo-local status file |
| Stale heartbeat display | working | Old active/waiting states degrade to a stale waiting display instead of looking permanently busy |
| Debounce / minimum display time | working | Rapid state changes no longer flicker immediately; blocked states still surface promptly |
| Top-level workflow HUD publishing | working | `run-actor-yaw-debug-scan.ps1` now emits short states such as `debug preflight`, `candidate search`, `candidate proof`, `coord refresh`, and final blocked/idle summaries |
| Startup `/reloadui` avoidance in the scan workflow | working | The actor-yaw scan still skips the startup ReaderBridge refresh path by default and did not reintroduce `/reloadui` in this pass |
| Truth-promotion gate | working | The workflow still blocks weak or degraded actor-yaw runs from being promoted to repo truth |

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| Coord-anchor freshness | still blocked | `TraceMatchesProcess = false` remains the main promotion blocker from prior actor-yaw work |
| Coord-trace refresh generator | still blocked | The bounded refresh path is safer now, but the underlying coord-trace generator still times out / fails to rewrite fresh trace evidence |
| Full actor-yaw completion in this pass | not completed | A live `-SkipStimulus` run was started only to observe HUD phase publishing, then manually stopped after status verification; it is not proof evidence |
| HUD depth below the top-level wrapper | partial | `run-actor-yaw-debug-scan.ps1` publishes HUD states, but `read-player-current.ps1` and `trace-player-coord-write.ps1` do not yet publish directly |
| Worktree cleanliness | mixed | Current branch state still has modified working-tree files and is not staged/committed |

## Stale artifacts

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json` remains the stale coord-trace anchor artifact from the earlier blocked refresh path and should not be mistaken for fresh proof.
- Runtime HUD files under `C:\RIFT MODDING\RiftReader\debug\workflow-hud-*.json` or screenshot validation captures are ephemeral validation artifacts; the temporary test captures created in this pass were removed after validation.

## Validation results frozen here

| Check | Result | Notes |
|---|---|---|
| `dotnet build 'C:\RIFT MODDING\RiftReader\tools\RiftReader.WorkflowHud\RiftReader.WorkflowHud.csproj' --nologo` | passed | Clean build after heartbeat/debounce changes |
| `dotnet build 'C:\RIFT MODDING\RiftReader\RiftReader.slnx' --nologo` | passed | Solution still builds cleanly |
| PowerShell parse: `C:\RIFT MODDING\RiftReader\scripts\write-workflow-hud-status.ps1` | passed | No syntax errors |
| PowerShell parse: `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1` | passed | No syntax errors |
| Safe missing-process workflow run | passed | Final HUD state became blocked with `preflight failed` |
| Live no-focus HUD check | passed | RIFT remained foreground during HUD launch |
| Stale heartbeat visual check | passed | HUD displayed `stale: candidate proof` with amber waiting state after heartbeat expiry |
| Debounce visual check | passed | Rapid `phase one` → `phase two` update held the earlier state briefly before switching |
| New actor-yaw promotion evidence | not produced | This pass did not generate a new promotion-ready workflow summary |

## Current working design snapshot

### HUD utility

- Launch script:
  - `C:\RIFT MODDING\RiftReader\scripts\run-workflow-hud.ps1`
- Status writer:
  - `C:\RIFT MODDING\RiftReader\scripts\write-workflow-hud-status.ps1`
- UI project:
  - `C:\RIFT MODDING\RiftReader\tools\RiftReader.WorkflowHud`

### Current HUD behavior contract

- always on top
- no activate / does not steal focus
- rounded corners
- draggable
- saved last known position
- one utility/version line
- one dot + short action line
- stale detection from `updatedAtUtc`
- short-message persistence via `lastMessage`
- debounce via minimum display duration

### Current top-level workflow states published by the scan

- `debug preflight`
- `player baseline`
- `coord anchor`
- `candidate search`
- `candidate proof`
- `ledger update`
- `coord refresh`
- `candidate select`
- `debug trace`
- final summaries such as:
  - `promotion ready`
  - `debug confirmed`
  - `turn unverified`
  - `no candidate`
  - `preflight failed`

## Branch / workflow authority

Current authority for this branch resume point:

- branch: `scanner-with-debug`
- worktree: `C:\RIFT MODDING\RiftReader`
- actor-yaw workflow entrypoint:
  - `C:\RIFT MODDING\RiftReader\scripts\run-actor-yaw-debug-scan.ps1`
- HUD utility entrypoint:
  - `C:\RIFT MODDING\RiftReader\scripts\run-workflow-hud.ps1`
- current truth gate:
  - `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`

Historical handoff/analysis docs remain background context only unless the
recovery docs explicitly send the next agent there.

## Input mode and safety notes

- This pass did **not** use `/reloadui`.
- This pass did **not** add new direct turn-stimulus logic.
- The only live-game interaction in this pass was a bounded foreground HUD
  visibility/focus check while `RIFT` remained foreground.
- A live `-SkipStimulus` actor-yaw scan was started only to verify HUD phase
  publishing and then manually stopped; it should not be treated as evidence for
  actor-yaw truth promotion.
- A missing-process scan (`__rift_missing__`) was used as the safe final-state
  blocker test for HUD publishing.
- No commit or staging was performed.

## Recommended first action in the next conversation

Wire direct HUD publishing into:

- `C:\RIFT MODDING\RiftReader\scripts\read-player-current.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1`

then instrument the coord-trace generator timeout path so the next live
actor-yaw run can separate:

- **proof-quality issues**
- from **coord-refresh lineage failures**

without depending only on the top-level wrapper for visibility.
