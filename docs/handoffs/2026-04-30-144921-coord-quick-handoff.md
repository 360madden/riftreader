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
| Debug-scan constraint | No Cheat Engine / CE Lua / CE debugger for follow-up scanning |

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
- Latest no-CE follow-up: `scripts/captures/coord-no-ce-scan-20260430-1501/no-ce-scan-summary.json`
- Latest no-CE neighborhood report: `scripts/captures/coord-no-ce-neighborhood-20260430-1530/coord-no-ce-neighborhood-summary.json`
- Last debug-scan evidence: `scripts/captures/coord-debug-scan-20260430-134228`
- Latest reacquisition attempts: `scripts/captures/coord-reacquisition-20260430-143447`
- Last command in this lane: `scripts/trace-coord-writer-instruction.ps1` variants with instruction `0x674B6F` and 12-byte candidate windows
- Last result: all runs either timed out/failed to arm or remained armed with `hitCount=0`; no candidate was promoted.
- A CE/VEH-dependent path remains unstable and should be treated as compromised for now.
- User clarified after this handoff: debug scanning is okay as needed, but do
  **not** use Cheat Engine for it.

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

Resume note: the committed collector script uses `-ModuleOffsetHex` /
`-InstructionAddressHex`, `-TimeoutSeconds`, `-MaxHits`, and explicit
`-OutputFile` / `-StatusFile` / `-HitsFile`; it does not accept the older
draft parameters `-InstructionAddress`, `-Pattern`, `-RunDurationSeconds`,
`-SampleCount`, `-SampleDelayMs`, or `-RunDir`.

```powershell
$runDir = 'scripts/captures/coord-reacquisition-20260430-15xxxx'
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

pwsh -File scripts/trace-coord-writer-instruction.ps1 `
  -ProcessId 32468 `
  -TargetWindowHandle 0x15908B2 `
  -ModuleOffsetHex 0x674B6F `
  -PrimaryRegister RBX `
  -PrimaryCoordOffsetHex 0x3BC `
  -PrimaryWriteOffsetHex 0x3C0 `
  -SecondaryRegister R13 `
  -SecondaryCoordOffsetHex 0x2E8 `
  -TimeoutSeconds 12 `
  -MaxHits 180 `
  -StimulusMode AutoHotkey `
  -StimulusKey w `
  -StimulusHoldMilliseconds 1000 `
  -OutputFile (Join-Path $runDir 'coord-writer-instruction-trace.json') `
  -StatusFile (Join-Path $runDir 'coord-writer-instruction-trace.status.txt') `
  -HitsFile (Join-Path $runDir 'coord-writer-instruction-trace.hits.ndjson') `
  -Json
```

## Notes

- Movement remains disabled in this session and must stay disabled until proof recovery succeeds.
- Wall-collision and non-clear-path W pulses should not be used as proof evidence.

## Resume attempt - 2026-04-30 14:56 EDT

| Item | Result |
|---|---|
| Exact target recheck | PID `32468` / HWND `0x15908B2` still live, visible, responding, title `RIFT` |
| Visual preflight | Forward path appeared open toward water; not an enclosed-room/wall collision setup |
| Screenshot baseline | `tools/rift-game-mcp/.runtime/screenshots/capture-20260430-145538-291.png` |
| Corrected collector run dir | `scripts/captures/coord-reacquisition-20260430-1455-corrected-collector` |
| Collector result | Failed before arming: `cheatengine-exec.ps1` could not connect to Cheat Engine Lua pipe `RiftReader` |
| CE process/pipe check | No `cheatengine*` process found; no `RiftReader` named pipe found |
| W stimulus | Not sent; failure happened before the collector armed |
| Movement gate | Still `false` |

Next unblocker: start Cheat Engine with the RiftReader autorun bootstrap loaded,
then verify `pwsh -File scripts/cheatengine-exec.ps1 -Code 'return 123'`
before rerunning the corrected collector command above. If the bootstrap is
missing, install it with `scripts/install-cheatengine-autorun.cmd` and restart
Cheat Engine.

Superseding constraint from the next resume turn: do **not** use this CE
unblocker path for debug scanning. Keep the command above only as historical
context for why the CE-dependent collector was not run.

## No-CE debug scan - 2026-04-30 15:01 EDT

| Item | Result |
|---|---|
| Run folder | `scripts/captures/coord-no-ce-scan-20260430-1501` |
| Summary | `scripts/captures/coord-no-ce-scan-20260430-1501/no-ce-scan-summary.json` |
| Methods | Native `RiftReader.Reader` process-memory reads/scans only |
| Cheat Engine used | No |
| Live movement/input used | No |
| Exact ReaderBridge coord hits | 2: `0x2C9A50B6CD0`, `0x2C9BD7D98D0` |
| Signature families | 2: `fam-6F81F26E` at `0x2C9A50B6CD0`, `fam-CEC3708F` at `0x2C9BD7D98D0` |
| `read-player-current` | Still heuristic/cached-anchor only at `0x2C9A50B6CD0`; not proof-grade |
| Direct orientation candidates | 0 |
| Pointer-hop orientation candidates | 2; best `0x2C9C46F9948 @ +0x58`, candidate-only |
| Current behavior-backed yaw | Still `0x2C9A013A490 @ +0xD4`, fresh read yaw about `11.078°` |
| Pointer refs to coord hits | 0 refs to both exact coord triplet addresses |
| Pointer refs to yaw source | 13 refs to `0x2C9A013A490` |
| Movement gate | Still `false` |

Interpretation: the no-CE scan reinforces that the current exact coordinate
hits are cache/static candidates, not a proven source-chain/movement source.
There is still no post-restart `coord-trace-coords` anchor/watchset.

## No-CE neighborhood scan - 2026-04-30 15:30 EDT

| Item | Result |
|---|---|
| Script added | `scripts/capture-no-ce-coord-neighborhood.ps1` |
| Run folder | `scripts/captures/coord-no-ce-neighborhood-20260430-1530` |
| Full report | `scripts/captures/coord-no-ce-neighborhood-20260430-1530/coord-no-ce-neighborhood.json` |
| Compact summary | `scripts/captures/coord-no-ce-neighborhood-20260430-1530/coord-no-ce-neighborhood-summary.json` |
| Methods | Native reader raw memory reads over selected windows only |
| Cheat Engine used | No |
| Live movement/input used | No |
| Windows inspected | 23 |
| Local pointer links | 96 |
| Coord windows | 4 |
| Basis windows | 5 |

Key findings:

- Coord roots still only show exact ReaderBridge coord triplets in their own
  windows; no behavior-backed yaw basis was found in coord-root windows.
- `0x2C9A50B6CD0` has an exact local pointer to pointer-hop-2 parent
  `0x2C9AC932390` at `0x2C9A50B6DC8`; this is a structural candidate link only,
  not movement proof.
- Behavior-backed yaw source `0x2C9A013A490` contains duplicate basis rows at
  source `-0xCC` and source `+0xD4`, both reading current yaw about `11.078°`.
- Best pointer-hop candidate `0x2C9C46F9948` still has duplicate basis rows at
  `+0x58/+0x8C` with yaw about `171.282°`, divergent from the current
  behavior-backed yaw; keep it candidate-only.
- No local structural link from either exact coord root to the behavior-backed
  yaw source was found in this no-CE neighborhood pass.

Movement remains blocked: this was useful structural negative evidence, but it
does not produce a `coord-trace-coords` replacement proof.

## Top 10 recommended next best actions

| # | Action | Why |
|---:|---|---|
| 1 | Continue only no-CE native reader scans for this lane | Matches the current user constraint |
| 2 | Narrow around `0x2C9A50B6CD0 -> 0x2C9AC932390` with native pointer/neighborhood reads | This is the only coord-root structural link found |
| 3 | Inspect yaw-source ref tables separately from coord roots | Yaw graph is active but currently disconnected from coord roots |
| 4 | Treat `0x2C9C46F9948 @ +0x58/+0x8C` as candidate-only unless behavior-proofed without CE | It diverges from current behavior-backed yaw |
| 5 | Re-run exact coord/signature/neighborhood scans after a manual significant position change, if user permits movement | Separates cache/static hits from live-updating source candidates |
| 6 | Keep all scan outputs under timestamped run folders with `noCheatEngine=true` metadata | Makes recovery resumable and auditable |
| 7 | Extend native neighborhood reporting only if a specific structural question needs it | Avoids drifting into broad scanner rewrites |
| 8 | Do not rerun `trace-coord-writer-instruction.ps1` while the no-CE boundary is active | That collector is CE/Lua-backed |
| 9 | Only promote after a non-CE equivalent proof path satisfies the `coord-trace-coords` watchset invariant | Maintains safety gate |
|10 | Run proof/validator suites after any future promotion | Verifies no actor-facing/navigation regressions |
