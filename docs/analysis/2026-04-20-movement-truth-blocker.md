# Movement Truth Blocker — 2026-04-20

## Verdict

Actor-facing remains solved at:

- `0x1B115201EB0 + 0xD4`

The current blocker is **movement truth source mismatch**, not actor-facing discovery.

## What was tested

### Movement-key verification

Using:

- `C:\RIFT MODDING\RiftReader_facing\scripts\test-player-movement-stimulus.ps1`
- backend: `-UseAhkSendKey`

Tested keys:

- `W`
- `Up`
- `Z`
- `NumPad8`

With:

- `Escape` pre-key
- `2000 ms` hold
- direct player-current-anchor live memory boundary

Result:

| Key | Verdict | Planar distance |
|---|---|---:|
| `W` | fail | `0.0` |
| `Up` | fail | `0.0` |
| `Z` | fail | `0.0` |
| `NumPad8` | fail | `0.0` |

### Turn-input regression check

Using:

- `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-facing-validation.ps1 -Stimulus turn-left -UseAhkSendKey -NoBoundaryTrigger`

Result:

- **pass**
- yaw delta `140.96356814429998°`
- planar coord delta `0.0`

This confirms the AHK gameplay-input path is still reaching Rift for turn input.

## Coordinate-source comparison

Using:

- `C:\RIFT MODDING\RiftReader_facing\scripts\compare-live-player-coord-sources.ps1`

### Observed live sources

| Source | Coord |
|---|---|
| ReaderBridge boundary | `X=7274.6997070312, Y=818.39996337891, Z=2914.6799316406` |
| Player-current anchor | `X=7280.01, Y=818.39996, Z=2917.5` |
| Actor-orientation source | `X=7294.330078125, Y=818.39996337891, Z=2917.75` |
| `--read-player-current` | failed |

### Pairwise planar mismatch

| Left | Right | Distance |
|---|---|---:|
| ReaderBridge boundary | Player-current anchor | `6.01244607637179` |
| ReaderBridge boundary | Actor-orientation source | `19.868990638975312` |
| Player-current anchor | Actor-orientation source | `14.322494548704016` |

### `--read-player-current` failure

The direct reader path failed with:

- `Unable to resolve a full current-player snapshot from family 'fam-CEC3708F'.`

## Conclusion

The current `move-forward` blocker is not strong evidence against the solved actor-facing source.

Instead, the evidence now points to at least one of these being true:

1. the tested forward keys are not the actual live movement keys,
2. the chosen movement truth source is stale or not the live player carrier,
3. multiple coord sources are drifting badly enough that forward validation cannot trust them interchangeably.

## Operational guidance

- Keep actor-facing solved at `0x1B115201EB0 + 0xD4`
- Do **not** reopen actor-facing discovery from this evidence alone
- Treat forward/movement work as a separate downstream diagnosis track
- Prefer source-comparison and movement-key verification before retrying `move-forward`
