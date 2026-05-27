# RiftReader handoff — current PID 12148 target found, provider/API freshness blocked

Created local: `2026-05-26T21:27:00-04:00`
Created UTC: `2026-05-27T01:27:00Z`

## Direct result

RIFT is running again, but static player-actor coordinate-chain discovery is still **blocked-safe** before proof reacquisition because the current proof pointer targets historical PID `28248` and ChromaLink/world-state API freshness is unavailable.

## Current observed target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Window title | `RIFT` |
| Responding | `true` |
| Observed local time | `2026-05-26T21:22-04:00` |

## Evidence

| Check | Result |
|---|---|
| `git --no-pager status --short --branch` | `## main...origin/main` |
| Decision packet | `status=passed`, `lane=proof-recovery`, safe next action `coordinate_recovery_status.py --json` |
| Coordinate recovery status | `blocked`; `current-proof-status:blocked-target-drift`; `artifact-target-pid-not-running:artifact=28248;live=12148` |
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` remains `blocked-target-drift` for historical PID `28248` |
| ChromaLink world-state reference | blocked with `world-state-fetch-failed:URLError:<urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>` |
| ChromaLink artifact | `scripts/captures/chromalink-world-state-reference-20260527-012311-137943/summary.json` |

## Movement / displacement recommendation

Movement is **not recommended yet**.

Displacement stimulus testing becomes the optimal next step only after all of these are true:

1. current target PID/HWND is locked and visible/responding;
2. ChromaLink/world-state or another accepted API-now coordinate source is fresh;
3. current-PID coordinate-family scan has found candidate coordinate triplets;
4. initial readback shows at least one candidate matches API-now without movement;
5. the next proof question is whether the same candidate/family follows a real pose change.

At that point, bounded/manual or explicitly approved displacement testing is recommended for multi-pose validation. Until then, movement would be premature because there is no fresh API-now truth surface to compare against.

## Safety ledger

| Operation | Status |
|---|---|
| Movement/game input | Not used |
| x64dbg/debugger attach | Not used |
| Breakpoints/watchpoints | Not used |
| Cheat Engine | Not used |
| Memory writes | Not used |
| Provider repo writes | Not used |
| Git stage/commit/push | Not used |

## Recommended resume path

1. Restore/start the ChromaLink HTTP bridge/world-state provider for the current live RIFT target.
2. Re-run a freshness/reference check for PID `12148` / HWND `0x640C0C`.
3. Once API-now coordinates are fresh, run current-PID proof-anchor recovery for PID `12148` instead of using PID `28248` artifacts.
4. Use current-PID family scan/readback to find candidate proof anchors.
5. Only then request/perform bounded displacement stimulus testing for multi-pose validation.
6. Keep actor-static-chain work separate: proof anchor recovery is only the movement-safety gate, not a promoted static chain.
