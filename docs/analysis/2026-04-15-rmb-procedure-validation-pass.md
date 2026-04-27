---
state: historical
as_of: 2026-04-15
---

# RMB Procedure Validation Pass

## Scope

Validate the **RMB + movement test procedure itself** on `main` after adding
the mouse-input focus gate. This was **not** a serious camera rediscovery proof
pass. The probed regions were only a provisional discovery set.

## Snapshot metadata

- report date: `2026-04-15`
- repo branch: `codex/actor-yaw-pitch`
- worktree path: `C:\RIFT MODDING\RiftReader`
- script under test:
  - `C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1`
- input mode:
  - direct mouse/camera input
- validation status:
  - procedure validated
  - camera-bearing signal not yet rediscovered

## Commands run

First run hit a PowerShell compatibility issue:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1" -Json
```

Compatibility fix applied:

- `Invoke-ReaderJson` now only passes `ConvertFrom-Json -Depth` when the local
  PowerShell actually supports that parameter

Then the same command was rerun:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\probe-live-camera-offset-diff.ps1" -Json
```

## Purpose

Procedure validation pass:

- prove the script can find Rift
- prove it can focus Rift
- prove it can verify focus
- prove it can send RMB + movement
- prove it can complete memory readback

This run was **not** intended to prove camera yaw/pitch rediscovery from the
12 provisional regions it sampled.

## Harness status

**Success**

Confirmed during the successful rerun:

- Rift process found:
  - `rift_x64 [30888]`
- the script completed with `TargetFocusRequired = true`
- RMB + movement stimulus executed
- memory readback completed
- JSON output returned successfully

## Signal status

**Empty**

Returned values:

- `TopYawCandidates = []`
- `TopPitchCandidates = []`

The 12 tested regions came from:

- `CandidateSource = coord-hit-derived-bases`

This means the provisional coord-derived bases did not surface usable
reversible camera yaw/pitch deltas in this pass.

## Safe interpretation

What this result **means**:

- the RMB test procedure now works under the focus-enforced mouse policy
- the current provisional regions are not yet good camera-bearing candidates

What this result **does not mean**:

- it does **not** mean the RMB/mouse harness failed
- it does **not** mean the new focus gate broke the test
- it does **not** mean camera yaw/pitch cannot be rediscovered

## Immediate next decision

- keep the RMB harness
- treat camera yaw/pitch as still needing rediscovery
- next camera work should start from better candidate families, not by
  re-debugging the mouse procedure first
