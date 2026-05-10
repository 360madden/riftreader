# Restart reacquisition pre-ProofOnly handoff

Created: 2026-05-10 01:45 EDT / 2026-05-10 05:45 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Status: `pre-proofonly-ready`  
Scope: RIFT client restart reacquisition / recovery progress before fresh `ProofOnly`

## TL;DR

The RIFT client restarted, so the prior PID/HWND/process epoch and old absolute proof pointer are stale. The new target is `rift_x64` PID `30992`, HWND `0xD1008`.

No-input target-control passed. No-input visual gate with target-control passed. Fresh `ProofOnly` is still pending. Movement, yaw stimulus, actor-facing promotion, auto-turn, route execution, screenshot-key input, `/reloadui`, and Cheat Engine remain blocked until fresh `ProofOnly` passes for PID `30992` / HWND `0xD1008`.

## Current repo state

| Fact | Value |
|---|---|
| Latest known commit | `5c14961 Document PowerShell paste safety policy` |
| Local git status before handoff | Clean and synced with `origin/main` when checked. |
| GitHub connector policy | Read-only only unless explicitly overridden. |
| PowerShell policy | Complex PowerShell should be delivered as script artifacts; simple linear commands only for interactive paste. |

## Restart target

| Field | Value |
|---|---|
| Process name | `rift_x64` |
| PID | `30992` |
| HWND | `0xD1008` |
| Window title | `RIFT` |
| Process start time | `2026-05-10 01:32:32 EDT` |

## Completed gates

| Gate | Result | Evidence |
|---|---|---|
| Target-control | Passed | `status=passed-target-control`; `classification=exact-hwnd-foreground`; `readyForReadOnlyProof=true`; `readyForVisualGate=true`; `readyForLiveInput=true`; artifact `C:\RIFT MODDING\RiftReader\scripts\captures\target-control-currentpid-30992-20260510-014008\target-control-status.json`. |
| Visual gate with target-control | Passed | `status=passed-visual-gate-target-control`; `readyForVisualGate=true`; `readyForLiveInput=true`; `blockers=[]`; `movementSent=false`; `inputSent=false`; `screenshotKeySent=false`; `reloaduiSent=false`; `noCheatEngine=true`; artifact `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-target-control-currentpid-30992-20260510-014345\visual-gate-target-control-status.json`. |
| Capture state | Passed overall | CopyFromScreen sanity passed, RIFT MCP copy capture passed, WGC window and monitor captures were usable. PrintWindow and DXGI desktop duplication had unusable/black/flat outputs but did not block because usable capture methods existed. |

## Pending gate

| Gate | Status | Required target |
|---|---|---|
| Fresh `ProofOnly` | Pending | PID `30992`, HWND `0xD1008` |

## Safety boundary

| Area | Current state |
|---|---|
| Previous proof pointer | Historical/reacquisition seed only until re-proven for restarted process epoch. |
| Movement | Blocked until fresh `ProofOnly` passes. |
| Yaw / actor-facing promotion | Blocked; prior actor-facing truth is stale across restart. |
| Auto-turn | Blocked. |
| Route execution | Blocked. |
| Screenshot-key input | Blocked. |
| `/reloadui` | Blocked. |
| Cheat Engine | Not authorized / not used. |
| SavedVariables as live truth | Not trusted as live truth. |

## Next command

```powershell
# Version: riftreader-proofonly-currentpid-30992-v0.1.1
# Total-Character-Count: 9815
# Purpose: Run fresh no-movement ProofOnly after target-control and visual gate passed for restarted RIFT client PID 30992 / HWND 0xD1008.
cd "C:\RIFT MODDING\RiftReader"

python -u .\scripts\live_test.py --profile ProofOnly --pid 30992 --hwnd 0xD1008 --process-name rift_x64 --live --no-gui

Write-Host "PROOFONLY_CURRENTPID_30992_DONE"
# END_OF_SCRIPT_MARKER
```

## ProofOnly success criteria

| Field | Expected |
|---|---|
| Status | `passed-proof-only` |
| PID/HWND | `30992` / `0xD1008` |
| `movementSent` | `false` |
| `movementAttempted` | `false` |
| `noCheatEngine` | `true` |
| Current proof pointer | Updated only if same-target proof passes. |

## If ProofOnly passes

1. Inspect `docs\recovery\current-proof-anchor-readback.json`.
2. Verify it now targets PID `30992` / HWND `0xD1008`.
3. Update `docs\recovery\current-truth.md` with the new target, ProofOnly path, readback path, coordinate, and timestamp.
4. Commit only intended tracked documentation/proof-pointer files.

## If ProofOnly fails

1. Do not run movement, yaw, auto-turn, route execution, screenshot-key input, `/reloadui`, or Cheat Engine.
2. Treat the previous proof pointer as historical only.
3. Return to read-only baseline triage: ReaderBridge snapshot, `--read-player-current`, and `--read-player-coord-anchor`.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. GitHub connector is read-only only. The RIFT client restarted and the new target is `rift_x64` PID `30992`, HWND `0xD1008`. Target-control passed with `exact-hwnd-foreground`. Visual gate with target-control passed with `readyForLiveInput=true`, no blockers, no movement, no input, no `/reloadui`, and no Cheat Engine. Fresh `ProofOnly` has not run yet for the new target. Next action is to run no-movement `ProofOnly` against PID `30992` / HWND `0xD1008`; do not run movement/yaw/auto-turn/route execution until it passes.
