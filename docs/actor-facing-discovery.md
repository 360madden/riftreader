# Actor-Facing Discovery Workflow (Navigation-Ready)

> **April 20, 2026 update**
>
> Actor-facing is now **solved for the canonical live source**
> `0x1B115201EB0 + 0xD4`.
>
> Actor yaw is now **solved as a derived value** from that same canonical basis
> row via `atan2(forwardZ, forwardX)`. The hot traced sibling component remains
> forward Z at `+0xDC`.
>
> The older incumbent `0x1B1230D39E0 + 0x144` is **rejected** and must not be
> reused.
>
> Forward movement / navigation proof remains a **separate downstream track**.
> Do not reopen actor-facing discovery unless new live evidence contradicts the
> canonical solved source.

## Scope

This workflow is for **actor-facing only**, not camera-facing.

The goal is to keep the canonical solved actor-facing source stable in the repo
and give the workflow a repeatable way to either:

- regression-check it as the actor-facing source, or
- explicitly contradict it on fresh live evidence before widening the search.

As of **April 20, 2026**, actor-facing itself is solved; only forward movement
correlation remains pending.

## Current posture

| Area | Current state |
|---|---|
| Canonical actor-facing source | `0x1B115201EB0 + 0xD4` |
| Canonical actor-yaw support | derived from `+0xD4/+0xDC` |
| Hot traced sibling component | `+0xDC` |
| Rejected incumbent | `0x1B1230D39E0 + 0x144` |
| Ground truth for movement | direct player-current-anchor boundary or addon-exported coords captured at experiment boundaries |
| Facing math | fixed and offline-tested |
| Integrity gates | fixed and offline-tested |
| Failure-shape classifier | fixed and offline-tested |
| Actor-facing authority | **solved** |
| Forward/navigation authority | **separate downstream track** |
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

Actor yaw in this repo is therefore **derived truth**, not a separately
promoted standalone yaw float. Do not reopen standalone yaw-float hunting unless
new live evidence directly contradicts the canonical basis-derived source.

## Implemented artifacts

### 1. Actor-facing sample

Produced by:

- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-facing.ps1`

Default output:

- `C:\RIFT MODDING\RiftReader\scripts\captures\player-actor-facing.json`

The sample now normalizes the canonical solved source into a single
actor-facing document with:

- source address / selected entry
- forward vector
- planar forward
- yaw / pitch radians and degrees
- yaw derivation formula / truth mode / standalone-yaw-float policy
- determinant
- row magnitudes
- cross-row dot products
- duplicate-basis delta
- basis forward offset
- resolution mode / notes
- integrity gate result
- status: `preferred-solved-lead | candidate | rejected | stale`

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

If the canonical source has passing idle + turn-left + turn-right evidence but
forward proof is still pending, the contract remains
`actor-facing-solved-forward-pending` instead of reopening actor-facing work.

### 5. Passive actor-facing analysis

Produced by:

- `C:\RIFT MODDING\RiftReader\scripts\analyze-actor-facing-passive.ps1`

Default output:

- `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-passive-analysis.json`

This helper is the **no-movement bridge** between existing capture artifacts and
the later live validation workflow. It:

- loads the latest ReaderBridge snapshot
- loads the owner-components artifact
- reads the current artifact-side orientation result
- ranks owner components for current snapshot context
- compares the current snapshot against the historical actor-orientation capture
- reports whether the addon exposes any direct facing signal
- emits a single passive baseline summary for the current client state

## Implemented workflow

### Phase A — revalidate the canonical solved source first

Reuse the existing orientation capture path first, but anchor it to the
canonical solved source:

- `0x1B115201EB0 + 0xD4`

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

### Phase B — correlate the solved facing source to actual movement

Use:

- `C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-validation.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\test-player-movement-stimulus.ps1` when the remaining question is whether a gameplay key produces real movement at all
- `C:\RIFT MODDING\RiftReader_facing\scripts\compare-live-player-coord-sources.ps1` when movement keys still fail and the remaining question is which coordinate truth source is stale or mismatched
- `C:\RIFT MODDING\RiftReader_facing\scripts\print-live-actor-yaw.ps1` when you want the current live actor yaw from the canonical source without reopening discovery
- `C:\RIFT MODDING\RiftReader_facing\scripts\assert-actor-yaw-truth.ps1` when you want a regression assertion that the canonical yaw source still matches the solved source and still has passing turn evidence

Stimulus matrix:

| Stimulus | Purpose | Acceptance |
|---|---|---|
| `idle` | measure jitter / false change | yaw jitter `<= 3°`, planar drift `<= 0.15` |
| `turn-left` | prove pure yaw response | abs yaw delta `>= 15°`, planar drift `<= 0.25` |
| `turn-right` | prove pure yaw response | abs yaw delta `>= 15°`, planar drift `<= 0.25` |
| `move-forward` | compare facing vs actual heading | movement `>= 0.75`, angular error `<= 12°` |
| repeated `move-forward` (5x) | prove stability | median error `<= 8°`, no single valid run `> 15°` |

Ground truth for movement is still the boundary or live coordinate truth source,
not the heartbeat delay itself. A failed `move-forward` run does **not** reopen
actor-facing discovery once the canonical source continues to pass `idle`,
`turn-left`, and `turn-right`.

### Phase C — classify downstream failure shape before broadening search

The implemented classifier buckets failures into:

| Shape | Meaning |
|---|---|
| `sign-inverted` | likely forward sign inversion (~180°) |
| `wrong-axis` | likely wrong row / axis (~90°) |
| `locomotion-mismatch` | turn-responsive candidate does not predict movement heading |
| `integrity-instability` | basis integrity failed |
| `insufficient-movement` | movement too small / noisy to evaluate |
| `none` | no classified failure |

Only after this classification should the search widen, and only if new live
evidence contradicts the canonical solved source.

## Script examples

Capture the current canonical actor-facing sample:

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

Verify whether a candidate movement key actually moves the player-current anchor:

```powershell
C:\RIFT MODDING\RiftReader_facing\scripts\test-player-movement-stimulus.cmd -UseAhkSendKey -Keys W,Up
```

Compare the live coordinate truth sources before trusting any movement verdict:

```powershell
C:\RIFT MODDING\RiftReader_facing\scripts\compare-live-player-coord-sources.cmd
```

Print the live actor yaw from the canonical solved source:

```powershell
C:\RIFT MODDING\RiftReader_facing\scripts\print-live-actor-yaw.cmd
```

Assert that actor yaw is still solved through the canonical basis-derived path:

```powershell
C:\RIFT MODDING\RiftReader_facing\scripts\assert-actor-yaw-truth.cmd
```

Build the current navigation-facing contract from the latest sample and history:

```powershell
C:\RIFT MODDING\RiftReader\scripts\build-navigation-facing-contract.cmd
```

Build a passive no-movement baseline from the latest snapshot plus the existing
owner/source artifacts:

```powershell
C:\RIFT MODDING\RiftReader\scripts\analyze-actor-facing-passive.cmd
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

## Passive no-movement phase

Before sending any turn or movement stimulus, prefer this sequence:

1. load `--readerbridge-snapshot`
2. capture or reuse a passive ReaderBridge boundary snapshot
3. run `analyze-actor-facing-passive`
4. confirm whether the canonical solved source still aligns with the current
   snapshot and whether addon expansion is needed for movement truth only

During this phase:

- do **not** use movement-triggered trace refresh helpers
- do **not** expand the addon just to synthesize facing from coords
- treat addon data as **coord/freshness truth**, not actor-facing truth

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
- automatic widening into broad memory search without contradiction evidence
- immediate auto-turn navigation implementation

## Result expected from this workflow

With the current solved source, the repo already has the actor-facing-side
outputs required for a navigation-ready contract:

1. one solved actor-facing source
2. fixed yaw / pitch math
3. fixed signed turn-error formula
4. explicit fallback / rejection rules

The remaining missing output is:

5. forward movement correlation evidence

Until contradictory live evidence appears, `0x1B115201EB0 + 0xD4` should be
treated as the **canonical solved actor-facing source**. Forward movement work
is a separate downstream validation track.
