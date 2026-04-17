# Actor-Facing Discovery Workflow (Navigation-Ready)

## Scope

This workflow is for **actor-facing only**, not camera-facing.

The goal is to keep the current selected-source basis forward row as the
**incumbent candidate** and give the repo a repeatable way to either:

- confirm it as the navigation-facing source, or
- reject it on evidence before widening the search.

As of **April 16, 2026**, this workflow is implemented, but the source is still
only a **candidate** until live validation passes.

## Current posture

| Area | Current state |
|---|---|
| Primary candidate | selected-source basis forward row |
| Ground truth for movement | addon-exported player coords captured at experiment boundaries |
| Facing math | fixed and offline-tested |
| Integrity gates | fixed and offline-tested |
| Failure-shape classifier | fixed and offline-tested |
| Authoritative source | **not confirmed yet** |
| Camera-facing | out of scope |

## Facing contract definition

Use this contract everywhere in discovery and later navigation:

| Item | Formula / meaning |
|---|---|
| Actor forward vector | normalized forward row from the selected actor-facing basis |
| Navigation facing | planar projection of actor forward on **X/Z** |
| Actor yaw | `atan2(forwardZ, forwardX)` |
| Actor pitch | `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))` |
| Turn error to waypoint | `Normalize(atan2(targetDeltaZ, targetDeltaX) - actorYawRadians)` |
| Flat-ground navigation usage | consume yaw / planar forward only; keep pitch as evidence |

## Implemented artifacts

### 1. Actor-facing sample

Produced by:

- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-facing.ps1`

Default output:

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-facing.json`

The sample normalizes the incumbent selected-source capture into a single
candidate-facing document with:

- source address / selected entry
- forward vector
- planar forward
- yaw / pitch radians and degrees
- determinant
- row magnitudes
- cross-row dot products
- duplicate-basis delta
- basis forward offset
- resolution mode / notes
- integrity gate result
- status: `candidate | rejected | stale`

### 2. Boundary capture

Produced by:

- `C:\RIFT MODDING\RiftReader\scripts\capture-readerbridge-boundary.ps1`

Default output:

- `C:\RIFT MODDING\RiftReader\scripts\captures\readerbridge-boundary.json`

This helper explicitly triggers:

- `/rbx export`

then reloads the latest ReaderBridge snapshot so the boundary capture uses the
latest addon-exported player coordinates instead of passively trusting the
heartbeat file cadence.

### 3. Facing validation runs

Produced by:

- `C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-validation.ps1`

Default outputs:

- latest run-set summary:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-validation.json`
- append-only per-run history:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-validation-history.ndjson`

Each run records:

- stimulus type
- before / after addon coords
- before / after facing samples
- planar coord delta
- observed movement heading
- predicted heading from facing sample
- signed angular error degrees
- yaw / pitch delta
- integrity gate result
- failure shape
- verdict

### 4. Navigation-facing contract

Produced by:

- `C:\RIFT MODDING\RiftReader\scripts\build-navigation-facing-contract.ps1`

Default output:

- `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-facing-contract.json`

This contract becomes `confirmed` only when one source passes:

- basis integrity gates
- idle stability
- turn-left response
- turn-right response
- five forward movement validations with repeated-forward thresholds

Otherwise it remains `candidate` or `rejected`.

## Implemented workflow

### Phase A — revalidate the incumbent first

Reuse the existing orientation capture path first:

- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`

Then normalize the result with:

- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-facing.ps1`

Integrity gates are fixed as:

| Gate | Required result |
|---|---|
| Determinant | `0.98` to `1.02` |
| Row magnitudes | each `0.98` to `1.02` |
| Cross-row dot products | absolute value `<= 0.02` |
| Duplicate basis agreement | max row delta `<= 0.02` when duplicate exists |

### Phase B — correlate facing to actual movement

Use:

- `C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-validation.ps1`

Stimulus matrix:

| Stimulus | Purpose | Acceptance |
|---|---|---|
| `idle` | measure jitter / false change | yaw jitter `<= 3°`, planar drift `<= 0.15` |
| `turn-left` | prove pure yaw response | abs yaw delta `>= 15°`, planar drift `<= 0.25` |
| `turn-right` | prove pure yaw response | abs yaw delta `>= 15°`, planar drift `<= 0.25` |
| `move-forward` | compare facing vs actual heading | movement `>= 0.75`, angular error `<= 12°` |
| repeated `move-forward` (5x) | prove stability | median error `<= 8°`, no single valid run `> 15°` |

Ground truth for movement is the addon-exported coordinate boundary capture,
not the heartbeat delay itself.

### Phase C — classify failure shape before broadening search

The implemented classifier buckets failures into:

| Shape | Meaning |
|---|---|
| `sign-inverted` | likely forward sign inversion (~180°) |
| `wrong-axis` | likely wrong row / axis (~90°) |
| `locomotion-mismatch` | turn-responsive candidate does not predict movement heading |
| `integrity-instability` | basis integrity failed |
| `insufficient-movement` | movement too small / noisy to evaluate |
| `none` | no classified failure |

Only after this classification should the search widen.

## Script examples

Capture the current candidate facing sample:

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-actor-facing.cmd -Label baseline
```

Capture addon coords at a movement boundary:

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-readerbridge-boundary.cmd -Label before-turn
```

Run an idle validation:

```powershell
C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-validation.cmd -Stimulus idle
```

Run a left-turn validation:

```powershell
C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-validation.cmd -Stimulus turn-left
```

Run five repeated forward validations:

```powershell
C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-validation.cmd -Stimulus move-forward -RepeatCount 5
```

Build the current navigation-facing contract from the latest sample and history:

```powershell
C:\RIFT MODDING\RiftReader\scripts\build-navigation-facing-contract.cmd
```

## Offline-tested code support

The shared math / integrity / failure classifier now lives in:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Facing\ActorFacingMath.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Facing\ActorFacingAnalyzer.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Facing\ActorFacingThresholds.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Facing\ActorFacingBasisMetrics.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Facing\ActorFacingIntegrityResult.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Facing\ActorFacingFailureShape.cs`

Offline tests live in:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader.Tests\Facing\ActorFacingAnalysisTests.cs`

Those tests cover:

- yaw / pitch math
- planar normalization
- signed turn-error normalization
- basis integrity gates
- `180°` sign-inversion classification
- `90°` wrong-axis classification
- integrity instability
- insufficient movement
- locomotion mismatch

## Live checklist for tonight

| Step | What to do |
|---|---|
| 1 | stay on foot in flat, open terrain |
| 2 | capture one baseline actor-facing sample |
| 3 | run `idle` once |
| 4 | run `turn-left` once |
| 5 | run `turn-right` once |
| 6 | manually face roughly forward and run `move-forward -RepeatCount 5` |
| 7 | build the navigation-facing contract |
| 8 | treat the source as authoritative only if the contract becomes `confirmed` |

## Non-goals in this pass

- camera-facing discovery
- orbit pitch / zoom / camera controller work
- mounts, swimming, airborne, or scripted motion states
- automatic widening into broad memory search without incumbent failure evidence
- immediate auto-turn navigation implementation

## Result expected from this workflow

When live validation passes, the repo will have all five required outputs for a
navigation-ready actor-facing contract:

1. one confirmed source
2. fixed yaw / pitch math
3. forward movement correlation evidence
4. fixed signed turn-error formula
5. explicit fallback / rejection rules

Until then, the selected-source basis forward row remains the **incumbent
candidate**, not proven final truth.
