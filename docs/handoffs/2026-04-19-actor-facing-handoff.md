# Actor-Facing Discovery Handoff — 2026-04-19

> **Superseded on April 20, 2026**
>
> Actor-facing is now solved for the canonical live source
> `0x1B115201EB0 + 0xD4`.
>
> See:
>
> - `C:\RIFT MODDING\RiftReader_facing\docs\handoffs\2026-04-20-actor-facing-solved-state.md`

## Status

- **Actor-facing source is not solved yet.**
- The current incumbent actor-facing candidate is **live-false** and must not be trusted.
- The best fresh live anchor is still the current-player family at `0x1B0E8504CF0` (`fam-6F81F26E`).

## Important workflow rule

> **Cheat Engine is disabled for this thread unless the user explicitly re-enables it.**
>
> Reason: it created instability/noise, including an access-violation popup, without producing the real actor-facing source.

## Fresh live anchor

Source artifact:

- [`C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-current-anchor.json`](C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-current-anchor.json)

Current values:

| Field | Value |
|---|---|
| ProcessName | `rift_x64` |
| AddressHex | `0x1B0E8504CF0` |
| FamilyId | `fam-6F81F26E` |
| Signature | `level@-144\|health[1]@-136\|health[2]@-128\|health[3]@-120\|coords@0` |
| CoordXOffset | `0` |
| CoordYOffset | `4` |
| CoordZOffset | `8` |
| LevelOffset | `-144` |
| HealthOffset | `-136` |
| SavedAtUtc | `2026-04-19T18:59:38.0627467+00:00` |

## Rejected actor-facing candidate summary

Rejected artifact:

- [`C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-actor-facing.json`](C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-actor-facing.json)

Why rejected:

| Finding | Evidence |
|---|---|
| Candidate looked structurally valid | Determinant and row magnitudes passed integrity checks |
| Candidate failed live behavior | A real left-turn visibly rotated the scene, but captured yaw stayed unchanged |
| Before/after yaw | `26.7241523772533° -> 26.7241523772533°` |
| DeltaYaw | `0.0°` |
| Conclusion | This candidate is **not** the real actor/camera-facing source |

Candidate details worth remembering:

| Field | Value |
|---|---|
| SourceName | `selected-source-basis-forward-row` |
| SourceAddress | `0x1B1230D39E0` |
| ResolutionMode | `read-only-pointer-hop-candidate-search` |
| BasisForwardOffset | `0x144` |
| YawDegrees | `26.7241523772533` |
| Status in file | `candidate` |
| Operational status | **Rejected by live turn evidence** |

## Most important discovery evidence

| Item | Result |
|---|---|
| Visual left-turn test | Passed visually; scene changed significantly |
| Facing capture correlation | Failed; no yaw change recorded |
| Pointer-hop candidates from current flow | Stayed frozen through turn stimulus |
| Reader current-player reacquire | Succeeded and returned fresh live family `fam-6F81F26E` |
| Direct base diff at `0x1B0E8504CF0` | No useful changing floats found in base window |
| First-level child scan | No stable turn-responsive orthonormal basis found |

## What to do next

Use a **Reader-only / read-only** approach:

1. Refresh the fresh player-current anchor using Reader only.
2. Enumerate readable first- and second-level children from `0x1B0E8504CF0`.
3. Capture `before / left-turn / right-turn` snapshots.
4. Score float windows for:
   - yaw-like monotonic response,
   - orthonormal-ish 3x3 matrices,
   - quaternion normalization,
   - repeatability across opposite turns.
5. Promote only candidates that actually track visual yaw.

## What not to do

- Do **not** continue CE write traces / projector traces / debugger attach workflows by default.
- Do **not** trust the incumbent `player-actor-facing.json` candidate.
- Do **not** reuse stale older `0x157...` trace artifacts as if they were live.

## Key artifacts and screenshots

| Type | Path |
|---|---|
| Fresh current-player anchor | [`C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-current-anchor.json`](C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-current-anchor.json) |
| Current actor-facing candidate file | [`C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-actor-facing.json`](C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-actor-facing.json) |
| Before-turn screenshot | [`C:\RIFT MODDING\RiftReader_facing\scripts\captures\tmp-rift-before-left-ahk.png`](C:\RIFT MODDING\RiftReader_facing\scripts\captures\tmp-rift-before-left-ahk.png) |
| After-turn screenshot | [`C:\RIFT MODDING\RiftReader_facing\scripts\captures\tmp-rift-after-left-ahk.png`](C:\RIFT MODDING\RiftReader_facing\scripts\captures\tmp-rift-after-left-ahk.png) |

## Files changed during the discovery work

These are the main files touched before this handoff:

- `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Cli\ReaderOptions.cs`
- `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs`
- `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Program.cs`
- `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Models\PlayerOrientationCandidateFinder.cs`
- `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Models\OrientationCandidateLedgerLoader.cs`
- `C:\RIFT MODDING\RiftReader_facing\scripts\actor-facing-common.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-facing.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-facing-validation.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\send-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\send-rift-key-ahk.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\send-rift-key-ahk.ahk`
- `C:\RIFT MODDING\RiftReader_facing\scripts\smart-capture-player-family.ps1`
