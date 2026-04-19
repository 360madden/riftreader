---
state: historical
as_of: 2026-04-18
---

# Rift Error Handler Attach Blocker and Live Attach Recovery (2026-04-18)

## Scope

This report freezes the investigation window where live native attach to the running
`rift_x64.exe` client was first blocked by an existing debugger relationship, then
recovered after `rifterrorhandler_x64.exe` was closed.

## Snapshot metadata

| Field | Value |
|---|---|
| State | `historical` |
| As of | `2026-04-18` |
| Report date | `2026-04-18` |
| Game update/build date | `unknown` |
| Branch | `scanner-with-debug` |
| Worktree | `C:\RIFT MODDING\RiftReader` |
| Input mode | `read-only inspection + bounded native debug attach`; no direct key/mouse stimulus in this pass |
| Validation status | `partial working` |

## Commands run

```powershell
powershell -ExecutionPolicy Bypass -File 'C:\RIFT MODDING\RiftReader\scripts\inspect-rift-debug-state.ps1'
dotnet run --project 'C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj' -- --process-name rift_x64 --read-player-coord-anchor --json
dotnet run --project 'C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj' -- --process-name rift_x64 --debug-trace-player-coord-write --debug-timeout-ms 2000 --debug-max-hits 1 --debug-disable-stack-capture --debug-disable-memory-windows --debug-disable-follow-up-suggestions --json
powershell -ExecutionPolicy Bypass -File 'C:\RIFT MODDING\RiftReader\scripts\open-rift-in-x64dbg.ps1' -PreviewOnly
```

## Artifacts checked

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\debug-traces\native-debug-failure-ledger.ndjson`
- `C:\RIFT MODDING\RiftReader\scripts\captures\debug-traces\20260418-151845-debug-trace-player-coord-write\debug-trace-manifest.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\debug-traces\20260418-161153-debug-trace-player-coord-write\debug-trace-manifest.json`

## Surviving anchors

| Area | Result | Notes |
|---|---|---|
| Live process discovery | working | `rift_x64.exe` remained discoverable and stable during the pass |
| Debug-state probe | working | `scripts\inspect-rift-debug-state.ps1` correctly distinguished blocked vs unblocked attach states |
| Read-only coord anchor validation | working | `--read-player-coord-anchor --json` succeeded against the live client |
| Native live attach/detach | working | After the helper exited, the bounded worker attached and detached cleanly |

## Broken or drifted anchors

| Area | Result | Notes |
|---|---|---|
| Live attach while helper owns debugger relationship | blocked | `DebugActiveProcess` failed with Win32 `87` while `rifterrorhandler_x64.exe` was attached |
| Player-coord trace hit capture | partial | Attach succeeded later, but the 2-second bounded trace recorded `0` hits |
| Player-coord instruction anchor freshness | drifted | Read-only live anchor scan reported a live pattern match at `0x93560E` while the trace manifest still used `0x932B3E` |

## Stale artifacts

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json` should not be treated as an exact current instruction offset without live rebasing.

## Branch / workflow authority

Authoritative implementation and live-debug workflow for this investigation live on:

- branch: `scanner-with-debug`
- worktree: `C:\RIFT MODDING\RiftReader`
- reader project: `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader`
- debug-state helper: `C:\RIFT MODDING\RiftReader\scripts\inspect-rift-debug-state.ps1`
- x64dbg launcher preview: `C:\RIFT MODDING\RiftReader\scripts\open-rift-in-x64dbg.ps1`

## Input mode and safety notes

- This pass used read-only inspection plus a bounded native attach worker.
- No direct keyboard stimulus was issued by the assistant during this pass.
- No direct mouse stimulus was issued by the assistant during this pass.
- No chat command injection or `/reloadui` was used.
- The user manually closed `rifterrorhandler_x64.exe` while leaving the game running.
- That helper exit was sufficient to clear the `DebuggerPresent` state and allow a later attach.

## Key observations

| Observation | Evidence |
|---|---|
| `rifterrorhandler_x64.exe` is the practical live-attach blocker when present | The debug-state probe showed `DebuggerPresent = true` with `rifterrorhandler_x64.exe` as the attach helper |
| The helper is not runtime-critical for immediate gameplay continuity | The user reported the game kept running normally after closing it |
| Clearing the helper enables attach recovery | A later bounded trace recorded `AttachOutcome = attached` and `DetachOutcome = detached` |
| Remaining problem is no longer attach ownership | The next bottleneck is hit triggering / live rebasing, not `DebugActiveProcess` failure |

## Immediate next step

Patch the `player-coord-trace` resolution path so the bounded debug worker reuses the live pattern-scan hit instead of the stale artifact offset, then rerun a short targeted live trace during deliberate movement.

## Follow-up findings later the same day

| Area | Result | Notes |
|---|---|---|
| Debug worker live rebasing | fixed | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Debugging\DebugTraceWorker.cs` now rebases `player-coord-trace` to the live module pattern hit (`0x93560E` in this pass) |
| Passive coord-anchor output | fixed | `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Models\PlayerCoordAnchorReader.cs` now reports the live rebased module base / offset / address instead of stale artifact fields |
| Adaptive trace stimulus selection | fixed | `C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1` now prechecks motion and auto-tries `WindowTools`, `SendInput`, then `PostMessage` before spending a watchpoint run |
| `window-tools.ps1` single-key send | fixed | scalar-token `.Count` bug for single keys like `W` / `RIGHT` was fixed |
| `window-tools.ps1` click support | expanded | click helper now supports `left`, `right`, and `both` mouse-button modes |
| `SendInput` keyboard path | improved but still ineffective | both `C:\RIFT MODDING\RiftReader\scripts\send-rift-key.ps1` and `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\helpers\window-tools.ps1` now emit scan-code based keyboard input instead of VK-only input |

## Synthetic-input blocker (current)

The remaining blocker is now best described as **live Rift not responding to the tested synthetic input channels**, not an address-resolution or attach problem.

| Probe | Result | Evidence |
|---|---|---|
| `W` via adaptive trace precheck | no motion | `WindowTools:delta=0.000000; SendInput:delta=0.000000; PostMessage:delta=0.000000` |
| `UP` via adaptive trace precheck | no motion | same zero-delta outcome |
| `ENTER` UI probe | no convincing UI response | full-frame compare only ~`1.10%`; screenshots did not show chat-open state |
| left-click world probe | no coord motion | full-frame change ~`3.63%`, but player coords stayed identical |
| both-mouse-buttons hold probe | no coord motion | full-frame change ~`2.50%`, but player coords stayed identical |
| privilege/UIPI mismatch | not supported | `rift_x64.exe` token read came back non-elevated / medium integrity in this pass |

## Practical interpretation

| Finding | Meaning |
|---|---|
| Foreground/focus alone is not the blocker anymore | later probes repeatedly saw `isForeground = true` and still produced zero coord delta |
| Keyboard bind guessing is unlikely to be the main issue | even `ENTER` did not produce a convincing visible UI-state change |
| VK-only `SendInput` was not the whole problem | scan-code based `SendInput` also failed to produce motion |
| Click-to-move is not currently giving an autonomous path | neither left-click nor both-button hold changed coords |

## Updated blocker summary

Autonomous live proof of the coord-write instruction is currently blocked on the fact that the live client is not reacting to the tested synthetic input channels (`WindowTools` SendInput, dedicated `send-rift-key.ps1`, `post-rift-key.ps1`, AutoHotkey key send, left click, and both-button mouse hold). The next high-confidence proof path is manual user movement while the bounded trace is armed, or a genuinely different input channel outside these current synthetic methods.
