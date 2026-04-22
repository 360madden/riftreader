# Handoff - April 22, 2026 - actor-facing source-chain truth promoted

## Verdict

Actor-facing is fresh truth again on the current live `rift_x64` session.

- canonical source object: `0x24F595F8D10`
- canonical forward basis row: `+0x60/+0x64/+0x68`
- duplicate truth-bearing forward row: `+0x94/+0x98/+0x9C`
- pitch/yaw formulas remain:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

## Live session state at handoff time

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader_facing` |
| Branch | `navigation` |
| Rift PID | `34088` |
| Rift start | `2026-04-22 00:19:33 -04:00` |
| Rift state | responding |
| CE PID | `53392` |
| CE state | responding |
| `rifterrorhandler_x64.exe` | not running |

## What changed in this pass

| File | Change |
|---|---|
| `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-yaw-candidates.ps1` | fixed same-source multi-offset validation by keying snapshots as `SourceAddress|BasisForwardOffset` instead of source address only |
| `C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1` | fixed behavior-backed lead timestamp parsing so JSON-parsed local `DateTime` values no longer fail stale checks incorrectly |
| `C:\RIFT MODDING\RiftReader_facing\scripts\actor-facing-behavior-backed-lead.json` | promoted new current-session lead to `0x24F595F8D10 @ +0x60`, duplicate `+0x94` |
| `C:\RIFT MODDING\RiftReader_facing\docs\recovery\current-truth.md` | updated truth doc to the April 22 source-chain result |
| `C:\RIFT MODDING\RiftReader_facing\docs\analysis\2026-04-22-actor-facing-source-chain-behavior-backed-lead.md` | added compact validation note |

## Root cause of the earlier false-flat source-chain validation

The earlier source-chain candidate screen tested four offsets on the **same** source object:

- `0x60`
- `0x94`
- `0xD4`
- `0x140`

But `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-yaw-candidates.ps1` cached baseline/sample snapshots only by `SourceAddress`.

Because all four candidates used the same source address `0x24F595F8D10`, the last tested offset overwrote the prior ones in the snapshot map. The run effectively validated `0x140` for every candidate, which is why everything looked flat.

After fixing the keying bug, `0x60` and `0x94` immediately showed strong reversible yaw response while `0xD4` and `0x140` stayed flat.

## Fresh proof that promoted truth

Validation artifact:

- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\actor-yaw-candidate-test.json`

| Offset | D peak yaw deltas | A peak yaw deltas | Reversible cycles | Coord drift | Verdict |
|---|---|---|---:|---:|---|
| `0x60` | `-146.6686`, `-143.0910` | `+143.5635`, `+147.9166` | `2` | `0.0` | truth-bearing |
| `0x94` | `-146.6681`, `-143.0903` | `+143.5629`, `+147.9163` | `2` | `0.0` | truth-bearing duplicate |
| `0xD4` | `0.0`, `0.0` | `0.0`, `0.0` | `0` | `0.0` | reject |
| `0x140` | `0.0`, `0.0` | `0.0`, `0.0` | `0` | `0.0` | reject |

## Supporting source-chain / accessor-family evidence

Artifacts:

- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-coord-write-trace.json`
- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-coord-trace-cluster.json`
- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-source-chain.json`
- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-source-accessor-family.json`

Important live findings from `player-source-accessor-family.json`:

| Accessor | Meaning |
|---|---|
| `lea rax,[rbx+48]` | live coord lane |
| `lea rax,[rbx+88]` | duplicate live coord lane |
| `lea rax,[rbx+60]` | primary transform-like / facing row |
| `lea rax,[rbx+94]` | duplicate transform-like / facing row |

Duplicate-basis agreement on the same source:

- max row delta between `+0x60` and `+0x94`: `5.72119212238225E-06`

## Fresh capture after promotion

This now succeeds again:

- `C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1 -Json -RefreshReaderBridge`

Fresh capture artifact:

- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-actor-orientation.json`

Key values from the fresh capture:

| Field | Value |
|---|---|
| Selected source | `0x24F595F8D10` |
| Preferred basis | `Basis@0x60` |
| Duplicate basis | `Basis@0x94` |
| Current yaw | `162.69783949345296` |
| Current pitch | `0.0` |
| `Coord48` matches player coords | true |
| `Coord88` matches player coords | true |

## Current behavior-backed lead file

`C:\RIFT MODDING\RiftReader_facing\scripts\actor-facing-behavior-backed-lead.json`

Current promoted values:

- `SourceAddress = 0x24F595F8D10`
- `BasisForwardOffset = 0x60`
- `BasisDuplicateForwardOffset = 0x94`
- `Status = preferred-solved-lead`
- `SolvedActorFacing = true`
- `CanonicalActorYaw = true`

## Important operational notes

1. This promoted lead is **current-session-safe right now** because the live process is still the same PID (`34088`) used during validation.
2. If Rift restarts, `capture-actor-orientation.ps1` will correctly fail the stale-lead check and require fresh validation.
3. Cheat Engine is usable again in this environment, and `rifterrorhandler_x64.exe` should stay terminated for debugger-heavy work.
4. `trace-player-coord-write.ps1` was previously upgraded to support `-WatchMode access` and `-StimulusMode AutoHotkey`; that remains useful for future discovery.
5. `--read-player-current` usage still requires `--process-name rift_x64`; calling it without a process selector only prints usage.

## Repo status at handoff

`git status --short` at handoff time:

- `M docs/recovery/current-truth.md`
- `M scripts/actor-facing-behavior-backed-lead.json`
- `M scripts/capture-actor-orientation.ps1`
- `M scripts/test-actor-yaw-candidates.ps1`
- `M scripts/trace-player-coord-write.ps1`
- `?? docs/analysis/2026-04-22-actor-facing-source-chain-behavior-backed-lead.md`

## Best next moves after actor-facing truth

1. Rebuild selector-owner / owner-components around the now-proven source `0x24F595F8D10`.
2. Add a compact per-candidate summary export to `test-actor-yaw-candidates.ps1` so same-source multi-offset regressions are obvious immediately.
3. Add a live-session sentinel that hard-aborts on `Not Responding`, focus loss, or hung stimulus helpers.
4. Capture one labeled before/after regression pair using the new `+0x60/+0x94` truth lane.
5. Keep CE as the live discovery workbench and the native reader as validator / consumer.
