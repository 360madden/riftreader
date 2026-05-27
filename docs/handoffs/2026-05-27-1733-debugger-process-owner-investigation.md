# Debugger / Process-Owner Investigation — PID 12148

## Verdict

Approved investigation completed. Current read-only probe does **not** show the previous active debug object/debug port blocker.

This does **not** solve/promote the actor/static chain. It only changes the debugger-access provenance picture.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Process start | `2026-05-27T01:17:01.265352Z` |
| Module base | `0x7FF77AF40000` |

## New evidence

| Evidence | Result |
|---|---|
| Fresh recovery probe | `debuggerLikelyAttached=false` |
| ProcessDebugPort | `0x0` |
| ProcessDebugObjectHandle | `null` |
| DebugActiveProcessStop this run | `false` / not attempted |
| x64dbg attach this run | `false` / not attempted |
| Attach environment probe | `passed` with warning `current-process-SeDebugPrivilege-not-enabled` |
| Process owner lead | `rifterrorhandler_x64.exe` PID `31632`, child of PID `12148` |

## Key artifacts

| Artifact | Path |
|---|---|
| Investigation packet | `C:\RIFT MODDING\RiftReader\scripts\captures\debugger-process-owner-investigation-12148-20260527-173251-411698\summary.json` |
| Fresh recovery probe | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-target-recovery-20260527-173134-355655\summary.json` |
| Attach environment probe | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-attach-environment-probe-20260527-173204-325532\summary.json` |
| Prior approval packet | `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-27-1717-debugger-process-owner-approval-needed.md` |

## Interpretation

- The older `x64dbg-attach-blocked-existing-debug-object` evidence is preserved as history, but the fresh read-only probe no longer sees an active debug object/debug port.
- `rifterrorhandler_x64.exe` is still the strongest provenance lead because it was launched by RIFT with `-attach -pid 12148 -section Trion.Rift.DebugSection-12148`.
- This improves the attach-readiness picture but does not authorize or perform attach.
- Current process token still warns `current-process-SeDebugPrivilege-not-enabled`.

## Safety ledger

| Field | Value |
|---|---:|
| movementSent | false |
| inputSent | false |
| noCheatEngine | true |
| x64dbgAttach | false |
| debuggerAttached | false |
| breakpointsSet | false |
| watchpointsSet | false |
| debugActiveProcessStopCalled | false |
| handleClosed | false |
| processSuspended | false |
| dumpCreated | false |
| providerWrites | false |
| proofPromotion | false |
| actorChainPromotion | false |
| gitMutation | false |

## Remaining blockers

- `no-static-resolver-promoted`
- `actor-static-chain-not-promoted`
- `not-restart-validated-for-static-actor-chain`
- `proof-anchor-stale-for-movement`
- `x64dbg-attach-not-run-in-this-approved-investigation`
- `current-process-sedebugprivilege-not-enabled`

## Next single best step

Ask for explicit approval for a bounded x64dbg attach/static-chain provenance attempt. If approved, use the fresh no-debug-object probe as the preflight, avoid `DebugActiveProcessStop`, stop before promotion, and collect access provenance/static-chain evidence only.
