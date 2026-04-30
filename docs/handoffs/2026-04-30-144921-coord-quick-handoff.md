# Coord Truth Handoff - 2026-04-30 14:49:22 EDT

## TL;DR

| Item | Value |
|---|---|
| Result | Coord proof remains blocked; no same-PID coord-trace-coords proof exists |
| Repo/Branch | main |
| Commit | 3108389 |
| Active movement | False |
| Gate reason | No validated post-restart coord-trace-coords anchor/watchset exists |
| Live session match | PID/HWND still live from blocker snapshot |

## Repo / state snapshot

| Field | Value |
|---|---|
| Repo | C:\\RIFT MODDING\\RiftReader |
| Branch | main |
| Commit | 31083896602ce4f1959a358faeae2cb694afcec1 (3108389) |
| Worktree status | `?? scripts/trace-coord-writer-instruction.ps1` (uncommitted, in worktree) |
| Latest blocker packet | `docs/recovery/current-coord-proof-blocker.json` |
| Latest yaw check packet | `docs/recovery/current-actor-yaw-restart-check.json` |
| Latest run folder | `scripts/captures/coord-debug-scan-20260430-134228` |
| Latest attempt folder | `scripts/captures/coord-reacquisition-20260430-143447` |

## Live target

| Field | Value |
|---|---|
| PID | 32468 |
| HWND | 0x15908B2 |
| Process name | rift_x64 |
| Process start UTC | 2026-04-30T16:03:29.7977969Z |
| Current process status | PID=32468, HWND=0x15908B2, Title=RIFT, Responding=True |
| Crash/restart policy | Do not reuse raw addresses if PID/HWND changes |

## Actor yaw (proof / validation status)

| Field | Value |
|---|---|
| Yaw source | 0x2C9A013A490 |
| Basis offset | +0xD4 |
| Yaw proof mode | current-session-yaw-available |
| Yaw sample (blocker packet) | 170.5779786657639 |
| Pitch sample | 0 |
| Restart-check yaw status | behavior-backed-current-session |
| Restart-check yaw sample | 125.08155427081634 |

## Coordinate proof status

| Gate | Status |
|---|---|
| Same-PID coord access proof | failed / not found |
| `resolve-proof-coord-anchor.ps1` | not rerun after no accepted proof |
| proof watchset has `coord-trace-coords` | missing |
| telemetry preflight | not re-run after proof failure |
| Active movement gate | false |

## Evidence / artifacts (latest)

- Current blocker packet: `docs/recovery/current-coord-proof-blocker.json` (mode `blocked-no-proof-grade-coordinate-anchor`)
- Last debug-scan evidence: `scripts/captures/coord-debug-scan-20260430-134228`
- Latest reacquisition attempts: `scripts/captures/coord-reacquisition-20260430-143447`
- Last command in this lane: `scripts/trace-coord-writer-instruction.ps1` variants with instruction `0x674B6F` and 12-byte candidate windows
- Last result: all runs either timed out/failed to arm or remained armed with `hitCount=0`; no candidate was promoted.
- A CE/VEH-dependent path remains unstable and should be treated as compromised for now.

## Candidate carry-forward list

- 0x2C989A56E9C (RBX + 0x3BC; previously seen as nearby writer-like hit at `rift_x64.exe+674B6F`)
- 0x2C9D11CF828 (R13 + 0x2E8 register-derived)
- 0x2C99C2B2DC0 (ReaderBridge static coord-like hit; no proof)
- 0x2C9A50B6CD0 (ReaderBridge static coord-like hit; no proof)
- 0x2C9BD7D98D0 (ReaderBridge static coord-like hit; not traced)

## Last command and observed result

Last notable execution: repeated instruction-collection attempts around `0x7FF7876F4B6F` from `scripts/captures/coord-reacquisition-20260430-143447`.
Observed result:
- status files report `status=armed` / `stage=armed or debug-attach` with `hitCount=0`
- no accepted coordinate-triplet proof
- movement remained blocked

## Next command

```powershell
pwsh -File scripts/trace-coord-writer-instruction.ps1 -ProcessId 32468 -TargetWindowHandle 0x15908B2 -InstructionAddress 0x7FF7876F4B6F -Pattern 'F3 0F 11 93 C0030000' -PrimaryRegister RBX -PrimaryCoordOffset 0x3BC -PrimaryWriteOffset 0x3C0 -SecondaryRegister R13 -SecondaryCoordOffset 0x2E8 -RunDurationSeconds 12 -SampleCount 180 -SampleDelayMs 250 -StimulusKey w -RunDir scripts/captures/coord-reacquisition-20260430-15xxxx
```

## Notes

- Movement remains disabled in this session and must stay disabled until proof recovery succeeds.
- Wall-collision and non-clear-path W pulses should not be used as proof evidence.

## Top 10 recommended next best actions

| # | Action | Why |
|---:|---|---|
| 1 | Verify live window targeting before any more scanning | Prevent stale address and wrong-session capture |
| 2 | Keep a brief visual preflight for collision-free movement path before W stimuli | Avoid wall-collision contamination of samples |
| 3 | Run RiftReader-native neighborhood reads before any further CE-dependent trace attempts | Lower blast radius and higher session stability |
| 4 | Capture short baseline ReaderBridge coordinates then run bounded candidate sampling | Reduces false positives from stale/static matches |
| 5 | Recompute candidate deltas before/after controlled stimulus using 12-byte windows | Matches proof policy for coord replay |
| 6 | Prioritize proof candidates by structural link to yaw source object graph | Higher signal than raw movement delta |
| 7 | Preserve and annotate all captures in a timestamped run folder each attempt | Enables resumable crash-safe handoff |
| 8 | Only promote after `scripts/resolve-proof-coord-anchor.ps1` and `scripts/export-proof-polling-watchset.ps1` both succeed | Maintains safety gate |
| 9 | Run `pwsh -File scripts/validate-current-actor-yaw-restart-check.ps1 -Json` after any successful proof replay | Confirms gate + facing/coord alignment |
|10 | Run `pwsh -File scripts/test-actor-facing-proof-suite.ps1` before declaring completion | Verifies no regressions in actor-facing flow |
