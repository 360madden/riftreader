# Actor-Facing Passive Baseline (2026-04-16)

## Verdict

| Area | Result |
|---|---|
| Branch/worktree choice | used separate `facing` worktree at `C:\RIFT MODDING\RiftReader_facing` |
| Movement stimuli used | **none** |
| Passive snapshot source | latest ReaderBridge export (`DirectAPI`) |
| Current facing source status | still a **memory-side candidate** only |
| Addon expansion needed now | **No** |
| Next required live step later | idle / turn validation only after movement-enabled testing is allowed |

## What was executed

| Step | Command / source | Outcome |
|---|---|---|
| Passive snapshot read | `dotnet run --project C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --readerbridge-snapshot --json` | passed |
| Passive boundary capture | `pwsh -File C:\RIFT MODDING\RiftReader_facing\scripts\capture-readerbridge-boundary.ps1 -NoTrigger -Json` | passed |
| Artifact-side orientation read | `dotnet run --project ... -- --read-player-orientation --owner-components-file C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json --json` | passed |
| Owner-component ranking | `dotnet run --project ... -- --rank-owner-components --owner-components-file C:\RIFT MODDING\RiftReader\scripts\captures\player-owner-components.json --json` | passed |
| Passive analyzer | `pwsh -File C:\RIFT MODDING\RiftReader_facing\scripts\analyze-actor-facing-passive.ps1 -Json` | passed |

## Current passive baseline

### ReaderBridge snapshot

| Field | Value |
|---|---|
| Export count | `825` |
| Export reason | `save-begin` |
| Source mode | `DirectAPI` |
| Source addon | `RiftAPI` |
| Player | `Atank` |
| Location | `Sanctum of the Vigil` |
| Coord | `7462.84, 885.57, 3042.49` |

### Current artifact-side facing candidate

| Field | Value |
|---|---|
| Selected source address | `0x1FDA0D13170` |
| Selected entry index | `6` |
| Role hints | `selected-source`, `coord48-match`, `coord88-match`, `orientation60-match`, `orientation94-match` |
| Preferred yaw | `-0.4715°` |
| Preferred pitch | `0.0000°` |
| Preferred vector | `0.999966, 0.000000, -0.008230` |
| Duplicate basis delta | `0.00000110` |
| Duplicate agreement strong | `true` |

### Owner-component context

| Field | Value |
|---|---|
| Owner address | `0x1FD8BBDE410` |
| Container address | `0x1FDA0D1F320` |
| State record address | `0x1FD8BBDE4D8` |
| Selected source rank | `16` |
| Selected source kind | `transform/source` |
| Top stat-like candidate | `0x1FDA0D13290` |
| Top stat-like candidate kind | `state-like` |

Interpretation:
- the selected source is still present in the owner-component artifact
- the ranker correctly deprioritizes it for **stat-bearing** reads because it looks like the transform/source component instead
- this is consistent with using it as an orientation candidate, not a stat hub

### Historical drift vs current state

| Field | Value |
|---|---|
| Historical actor-orientation file | `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-orientation.json` |
| Historical selected source | `0x245B92311D0` |
| Matches current selected source | `false` |
| Historical -> current planar coord drift | `729.91` |

Interpretation:
- the older actor-orientation capture is still useful as **evidence**, but not as current truth
- current passive analysis should treat that artifact as historical because both source address and player location have moved materially

### Addon-facing support

| Field | Value |
|---|---|
| Orientation probe file | `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-orientation-probe.json` |
| Direct heading API available | `false` |
| Direct pitch API available | `false` |
| Any addon-facing signal | `false` |
| Addon expansion recommendation | `not-needed-now` |

Interpretation:
- the addon still provides coordinate/freshness truth only
- it does **not** provide an actor-facing corroboration signal today
- addon expansion should wait until a verified facing API source exists

## Constraint encountered

| Attempt | Result |
|---|---|
| Triggered boundary export with `capture-readerbridge-boundary.ps1` default behavior | failed |
| Failure shape | native post path could not use the expected background helper; AutoHotkey fallback exited with code `2` |
| Decision taken | switched to `-NoTrigger` passive boundary capture and continued |

This kept the session within the requested **no-movement** scope and still produced a usable passive baseline.

## Artifacts produced

| Artifact | Path |
|---|---|
| Passive boundary capture | `C:\RIFT MODDING\RiftReader_facing\scripts\captures\readerbridge-boundary.json` |
| Passive analysis summary | `C:\RIFT MODDING\RiftReader_facing\scripts\captures\actor-facing-passive-analysis.json` |

## Conclusion

The best current no-movement position is:

1. keep actor-facing discovery on the **memory side**
2. keep the addon as **coordinate/freshness truth only**
3. treat the current selected source as a **candidate**, not confirmed truth
4. postpone addon expansion and movement-triggered validation until later tonight
