# Waypoint Navigation V1

## Status

Waypoint navigation v1 is implemented as of **April 16, 2026** for the external
reader in `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader`.

This first slice is intentionally narrow:

| Area | V1 behavior |
|---|---|
| Control model | **Manual-align first by default**. The reader core can now optionally auto-turn before forward movement with `--auto-turn-before-move`, but active travel still uses the strict coord-trace anchor and fails closed on bad alignment, worsening turns, or input/telemetry failure. |
| Waypoint source | External tracked JSON at `C:\RIFT MODDING\RiftReader\scripts\navigation\waypoints.json` |
| Movement backend | .NET 10 orchestration with a thin adapter over `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1` |
| Live telemetry | Active movement requires the validated coord-trace anchor; read-only summaries may still surface fallback anchors when they are explicitly labeled by `anchorSource` |
| Addon boundary | Addon stays telemetry / validation only in v1 |
| Safety model | Fail closed on bad start, no progress, moving away, anchor loss, input failure, or timeout |

## Scope

### Included in v1

- waypoint-file-backed navigation config
- `--read-navigation-current` preflight vector summary
- `--navigate-waypoints` single-segment forward travel
- opt-in reader-core pre-movement auto-turn
- optional one-shot run / walk pace toggles
- verified live coord-anchor resolution before movement
- direct memory coord reads during movement
- stop reasons for the common unsafe or broken cases

### Explicit non-goals

- strafe corrections
- obstacle avoidance
- route graphs
- multi-waypoint chaining
- terrain intelligence
- addon waypoint UI
- slash waypoint capture

## Architecture

```mermaid
flowchart TD
    A["Waypoint JSON"] --> B["WaypointNavigationConfigurationLoader"]
    B --> C["Resolve destination/start waypoint"]
    C --> D["NavigationPoseSourceFactory"]
    D --> E["coord-trace anchor (proof-grade)"]
    D --> F["read-only fallback anchors"]
    E --> H["Proof-grade live pose source"]
    F --> I["Read-navigation-current summary"]
    H --> I
    H --> J["WaypointNavigator"]
    J --> K["PowerShellMovementBackend"]
    K --> L["post-rift-key.ps1"]
```

### Pose resolution policy

`--navigate-waypoints` is now proof-strict:

1. current-process coord-trace anchor
2. fail closed with `anchor-unavailable`

`--read-navigation-current` remains read-only and may still fall back in this
order:

1. current-process coord-trace anchor
2. cached player-current anchor
3. one-time `PlayerCurrentReader.ReadCurrent(...)` reacquisition

If the summary output reports any `anchorSource` other than
`coord-trace-anchor`, treat it as a read-only fallback result rather than
proof-grade movement truth.

### State machine

```mermaid
stateDiagram-v2
    [*] --> Preflight
    Preflight --> Ready: start gate passes
    Preflight --> Failed: start-mismatch / anchor-unavailable
    Ready --> Moving
    Moving --> Arrived: within arrival radius
    Moving --> Failed: input-failed
    Moving --> Failed: telemetry-lost
    Moving --> Failed: no-progress
    Moving --> Failed: moving-away
    Moving --> Failed: timeout
```

## Waypoint file schema

Default file:

- `C:\RIFT MODDING\RiftReader\scripts\navigation\waypoints.json`

Schema:

```json
{
  "schemaVersion": 1,
  "movement": {
    "forwardKey": "w",
    "runKey": null,
    "walkKey": null,
    "defaultPace": "keep",
    "forwardPulseMilliseconds": 250,
    "postPulseSampleDelayMilliseconds": 150,
    "startRadius": 2.0,
    "defaultArrivalRadius": 1.5,
    "noProgressWindowMilliseconds": 1500,
    "minimumProgressDistance": 0.35,
    "wrongWayToleranceDistance": 0.75,
    "maxTravelSeconds": 30
  },
  "waypoints": [
    {
      "id": "example_start",
      "label": "Example Start",
      "zone": "optional metadata only",
      "x": 0.0,
      "y": 0.0,
      "z": 0.0,
      "arrivalRadius": 2.0,
      "pace": "keep"
    }
  ]
}
```

### Validation rules

The loader rejects:

- missing `movement.forwardKey`
- unsupported `schemaVersion`
- duplicate waypoint ids
- invalid pace values
- missing `x`, `y`, or `z`
- non-positive timing / radius / distance fields

`zone` is metadata only in v1 and is **not** enforced as a runtime gate.

## CLI

### Read-only navigation preflight

Returns the current vector from the live player position to the destination
waypoint. When the current behavior-backed actor-facing lead is valid for the
same live process, the summary also surfaces current yaw / pitch plus the
signed / absolute heading delta to the destination bearing. That facing data is
manual-alignment guidance and the planning input for opt-in reader-core
auto-turn;
it does not change the proof-grade coord-anchor requirement for movement.

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --process-name rift_x64 `
  --read-navigation-current `
  --destination-waypoint example_destination `
  --json
```

### Active waypoint travel

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --process-name rift_x64 `
  --navigate-waypoints `
  --start-waypoint example_start `
  --destination-waypoint example_destination `
  --pace keep `
  --json
```

### Active waypoint travel with opt-in reader-core auto-turn

`--navigate-waypoints` can now opt into pre-movement auto-turn using the live
actor-facing truth that powers the facing-aware preflight summary:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --process-name rift_x64 `
  --navigate-waypoints `
  --start-waypoint example_start `
  --destination-waypoint example_destination `
  --pace keep `
  --auto-turn-before-move `
  --auto-turn-within-degrees 7.5 `
  --turn-pulse-ms 75 `
  --turn-max-pulses 12 `
  --turn-worsening-tolerance 0.5 `
  --turn-max-worsening-pulses 2 `
  --json
```

This remains opt-in and fail-closed. It still depends on the validated
coord-trace anchor for live movement, and it aborts instead of forcing repeated
turns when heading alignment does not improve or worsens across consecutive
pulses.

For text output, the reader now has two navigation-result verbosity levels:

| Mode | What you get |
|---|---|
| default text output | compact summary, event counts, and the latest navigation / auto-turn event |
| `--verbose-navigation-events` | the same summary plus the full compact event timeline for navigation and auto-turn |

Example verbose text run:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --process-name rift_x64 `
  --navigate-waypoints `
  --start-waypoint example_start `
  --destination-waypoint example_destination `
  --pace keep `
  --auto-turn-before-move `
  --auto-turn-within-degrees 7.5 `
  --verbose-navigation-events
```

The prototype wrapper still exists as a higher-level helper, but the current
reader-core path is now the authoritative auto-turn entrypoint.

### Supported navigation switches

| Switch | Meaning |
|---|---|
| `--navigation-waypoint-file <path>` | Optional override for the default waypoint JSON |
| `--read-navigation-current` | Read-only waypoint vector summary |
| `--navigate-waypoints` | Active waypoint travel |
| `--start-waypoint <id>` | Required for `--navigate-waypoints` |
| `--destination-waypoint <id>` | Required for both waypoint modes |
| `--pace run\|walk\|keep` | Optional pace override |
| `--arrival-radius <double>` | Override arrival radius |
| `--max-travel-seconds <int>` | Override movement timeout |
| `--auto-turn-before-move` | Opt into pre-movement turn alignment before forward travel |
| `--auto-turn-within-degrees <double>` | Alignment threshold for auto-turn completion |
| `--turn-left-key <key>` / `--turn-right-key <key>` | Override turn keys for auto-turn |
| `--turn-pulse-ms <int>` / `--turn-post-sample-delay-ms <int>` | Tune turn pulse duration and post-pulse re-sample delay |
| `--turn-max-pulses <int>` | Cap the number of turn attempts before failing closed |
| `--turn-worsening-tolerance <double>` / `--turn-max-worsening-pulses <int>` | Abort auto-turn if heading gets worse repeatedly |
| `--verbose-navigation-events` | Print the full text event timeline instead of only the latest event summaries |
| `--json` | Structured output for either waypoint mode |

## Movement behavior

### Start gate

The start waypoint is a **gate**, not a path node.

Before movement begins, the reader checks the live player planar distance from
the configured start waypoint using **X/Z**. If that distance is greater than
`movement.startRadius`, the run aborts with `start-mismatch`.

### Pace handling

- `keep`: do not change pace state
- `run`: press `movement.runKey` once if configured
- `walk`: press `movement.walkKey` once if configured

If an explicit `run` or `walk` pace is requested but the required key cannot be
sent, the run fails closed with `input-failed`.

### Forward movement loop

Each loop:

1. press `movement.forwardKey` for `movement.forwardPulseMilliseconds`
2. wait `movement.postPulseSampleDelayMilliseconds`
3. read live coordinates directly from memory
4. recompute planar distance to the destination waypoint

Success condition:

- destination planar distance is within the effective arrival radius

Failure conditions:

- `no-progress`: not enough improvement within the configured no-progress window
- `moving-away`: distance increases past the wrong-way tolerance
- `telemetry-lost`: coord sample cannot be read mid-run
- `input-failed`: key post fails
- `timeout`: total runtime exceeds the max travel limit

## Output contracts

### `NavigationVectorSummary`

- current coord
- destination coord
- `deltaX`, `deltaY`, `deltaZ`
- `planarDistance` using **X/Z**
- `heightDelta` using **Y**
- `worldBearingRadians`
- `worldBearingDegrees`
- `withinArrivalRadius`

### `NavigationRunResult`

- `status`
- `startWaypointId`
- `destinationWaypointId`
- `pace`
- `anchorSource`
- `initialPlanarDistance`
- `finalPlanarDistance`
- `pulseCount`
- `stopReason`

## Safety rules

- do not send any input until a verified coord anchor is resolved
- do not start active movement from cached or reacquired fallback anchors
- do not keep moving if telemetry is lost
- do not continue if distance is getting worse
- do not continue if the player is not making measurable progress
- do not rely on saved-variable refresh during movement
- do not continue auto-turn if heading worsens repeatedly
- do not attempt strafe or obstacle-recovery logic in this slice

## Live testing checklist

Use this checklist before tonight’s first live run:

| Step | Check |
|---|---|
| 1 | Confirm the target process is the intended Rift client |
| 2 | If you are not using `--auto-turn-before-move`, confirm the character is manually facing roughly toward the destination |
| 3 | Run `--read-navigation-current` first and verify the destination vector looks sane |
| 4 | Confirm the current position is inside the start waypoint radius |
| 5 | Start with `--pace keep` unless run / walk toggles are already validated |
| 6 | Use open flat terrain for the first travel test |
| 7 | Expect failure stops instead of recovery behavior when facing or terrain is wrong |

## Navigation proof suite

Use the repo-owned proof suite to recheck the current navigation slice before
or after changes:

- offline hardening only:
  - `pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`
- include the current live smoke-route + preflight validation:
  - `pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1 -IncludeLive -SkipRefresh -ProcessName rift_x64`

## V2 / V3 progression snapshot

Current movement posture:

- v1 reader movement remains proof-strict and single-segment
- the current v2 bridge is now the **read-only facing-aware preflight** plus
  opt-in reader-core auto-turn on `--navigate-waypoints`
- v3 is **not** ready yet; before promoting beyond the prototype bridge, prove
  one deliberately misaligned live route where corrective turn pulses fire,
  alignment improves, and forward travel still succeeds through the strict
  coord-trace anchor

## Current limitations

As of **April 23, 2026**:

- current actor-facing truth on `main` is restored, but canonical
  `--navigate-waypoints` movement is still **single-segment only**
- the core reader path is still **straight-line, same-segment, and no obstacle
  avoidance**
- reader-core auto-turn is **opt-in**, fail-closed, and not yet proven on a
  deliberately misaligned live route end-to-end
- live corrective turn pulses on a deliberately misaligned route are not yet
  proven end-to-end
- addon work remains minimal in v1

