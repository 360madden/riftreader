# Aggressive Wrapper Unattended Validation

Date: April 15, 2026  
Branch: `codex/actor-yaw-pitch`

## Goal

Validate that the new unattended aggressive actor-yaw wrapper can:

1. start from the focused-PostMessage Desktop-2 workflow
2. recover gracefully when the forced ReaderBridge refresh lane fails
3. stop immediately after the first validated yaw winner
4. return a machine-readable success document instead of hanging or over-probing

## Command run

```powershell
powershell -ExecutionPolicy Bypass -File "C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1" -Json
```

## Outcome

The unattended wrapper succeeded.

Returned status:

- `Status = success`
- `RequireTargetFocus = true`
- `SkipUiClearCheck = true`
- `SkipLiveInputWarning = true`
- `StopOnFirstRecoveredYaw = true`

## Refresh fallback behavior

Requested:

- `RefreshReaderBridgeRequested = true`

Actual:

- `RefreshReaderBridgeUsed = false`
- `RefreshFallbackUsed = true`

Observed refresh failure message:

- `Single-stimulus screening failed for 0x245E247A860 @ 0xD4. Original error: AutoHotkey helper exited with code 2.`

Interpretation:

- the forced ReaderBridge refresh lane failed during the initial aggressive screen
- the wrapper correctly retried without forced refresh
- the retry completed successfully without operator intervention

This confirms the unattended fallback logic is working.

## Stop-on-first-winner behavior

The aggressive screen output recorded:

- `ScreenedCandidateCount = 4`
- `ResponsiveCandidateCount = 1`
- `RecoveryRunCount = 1`
- `StoppedAfterRecoveredYaw = true`

Interpretation:

- only one candidate survived into full recovery
- that candidate recovered yaw successfully
- the screen stopped immediately afterward as intended

This confirms the stop-on-first-winner behavior is working.

## Winning unattended candidate

Latest unattended wrapper winner:

- source address: `0x245B92311D0`
- basis forward offset: `0xD4`
- recovery artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245b92311d0-basis-d4.json`

Key recovery facts:

- `YawRecovered = true`
- `PitchRecovered = true`
- `IdleConsistencyPass = true`
- `BaselineIdleYawDeltaDegrees = 0`
- `InterStimulusYawDeltaDegrees = 0`
- focused key delivery mode remained `focused-postmessage`
- coordinate drift remained zero during the winning stimuli

Preflight deltas:

- `D` yaw delta: `-123.27665890948867°`
- `A` yaw delta: `120.27355721266289°`

Recovery deltas:

- `A` yaw delta: `123.13027064372221°`
- `D` yaw delta: `-123.02580405850442°`

## Relationship to the earlier manual win

This unattended validation did not invalidate the earlier proven manual winner.

Earlier validated winner:

- `0x245D78DCB50 @ 0xD4`
- artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\screening\aggressive\recovery-245d78dcb50-basis-d4.manual.nowarning.json`

New unattended validation shows:

- the workflow can now find and prove a live winner automatically
- the validated basis family remains `0xD4`
- absolute winning source addresses can differ across runs, so the workflow should preserve evidence and avoid overcommitting to a single stale absolute address

## Practical conclusion

The important branch result is no longer just "actor yaw can be recovered manually."

It is now also true that:

- the aggressive wrapper can recover actor yaw unattended
- forced refresh failure does not automatically kill the run
- the workflow stops after the first validated winner

## Follow-up implication

Future recovery/discovery work for other features should reuse:

- `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-workflow.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\focused-postmessage-discovery-prompt.json`

because the unattended control flow is now validated by a real live run, not
just by static script inspection.
