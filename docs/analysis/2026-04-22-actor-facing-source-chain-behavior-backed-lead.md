# April 22, 2026 actor-facing source-chain behavior-backed lead

> **Historical / superseded note:** this analysis captures the April 22
> source-chain-based actor-facing promotion. It is kept as evidence of that
> session, but the living current authority now lives in
> `docs/recovery/current-truth.md` and `docs/recovery/rebuild-runbook.md`.

## Verdict

Actor-facing truth is fresh again on the current `rift_x64` session.

- canonical source object: `0x24F595F8D10`
- canonical forward basis row: `+0x60/+0x64/+0x68`
- duplicate truth-bearing forward row: `+0x94/+0x98/+0x9C`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

## Why the earlier source-chain validation looked flat

`C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-yaw-candidates.ps1` keyed baseline/sample snapshots only by `SourceAddress`.

That collapsed multiple basis offsets on the same source object onto the last tested offset, so the April 22 source-chain screen (`0x60`, `0x94`, `0xD4`, `0x140`) was effectively reading `0x140` for every candidate.

The validator now keys snapshots by `SourceAddress|BasisForwardOffset`.

## Fresh behavior proof after the fix

Validation artifact:

- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\actor-yaw-candidate-test.json`

Current-session results on source `0x24F595F8D10`:

| Offset | D peak yaw deltas | A peak yaw deltas | Reversible cycles | Coord drift | Verdict |
|---|---|---|---:|---:|---|
| `0x60` | `-146.6686`, `-143.0910` | `+143.5635`, `+147.9166` | `2` | `0.0` | truth-bearing |
| `0x94` | `-146.6681`, `-143.0903` | `+143.5629`, `+147.9163` | `2` | `0.0` | truth-bearing duplicate |
| `0xD4` | `0.0`, `0.0` | `0.0`, `0.0` | `0` | `0.0` | reject |
| `0x140` | `0.0`, `0.0` | `0.0`, `0.0` | `0` | `0.0` | reject |

## Supporting live source-chain evidence

- refreshed coord trace: `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-coord-write-trace.json`
- refreshed source chain: `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-source-chain.json`
- refreshed accessor family: `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-source-accessor-family.json`

Accessor-family findings on the same source object:

- coords at `+0x48` and `+0x88`
- transform-like rows at `+0x60` and `+0x94`
- duplicate-basis agreement between `+0x60` and `+0x94`: `5.72119212238225E-06` max row delta

## Promoted lead

Behavior-backed lead file updated to:

- `C:\RIFT MODDING\RiftReader_facing\scripts\actor-facing-behavior-backed-lead.json`

Current promoted values:

- `SourceAddress = 0x24F595F8D10`
- `BasisForwardOffset = 0x60`
- `BasisDuplicateForwardOffset = 0x94`
- `Status = preferred-solved-lead`

## Fresh capture proof

`C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1 -Json -RefreshReaderBridge`
now resolves and validates the new live lead successfully.

Fresh capture artifact:

- `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-actor-orientation.json`

Key live properties from that capture:

- selected source: `0x24F595F8D10`
- preferred basis: `Basis@0x60`
- duplicate basis: `Basis@0x94`
- live source coords match current ReaderBridge player coords at both `+0x48` and `+0x88`
- preferred yaw/pitch remains derivable from the refreshed source basis without owner-component fallback
