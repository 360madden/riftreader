# Actor Yaw Workflow Handoff — 2026-04-17

## Current workspace state

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Date | `2026-04-17` |
| Scope | read-only actor-yaw / live proof workflow on current `main` |
| Debug scanning policy | **Do not use** debugger attach, breakpoint tracing, or CE debug scanning for this workflow |

## What was actually fixed

### 1) Strict foreground focus defaults for proof runs

The active actor-orientation proof scripts were patched so focused proof is now the default instead of “best effort”.

Modified files:

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\screen-actor-orientation-candidates.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\recover-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1`

Behavior change:

- Proof/input workflows now default to `RequireTargetFocus = true`.
- Foreground send paths now hard-fail if Rift is not actually foreground at send time.
- This was done because earlier live runs were too loose about focus.

### 2) Timestamped continuous logging added

Timestamped post-stimulus timeline logging was added to the active actor-yaw stimulus workflow.

Modified files:

- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\recover-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\screen-actor-orientation-candidates.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1`

New parameters now available on the active workflow:

| Parameter | Meaning |
|---|---|
| `-PostStimulusSampleCount <n>` | extra timed captures after the normal `after` capture |
| `-TimelineIntervalMilliseconds <ms>` | spacing between extra captures |
| `-TimelineOutputFile <path>` | optional explicit NDJSON output file |

Timeline captures now include:

- `GeneratedAtUtc`
- elapsed milliseconds from stimulus end
- player coords
- yaw/pitch
- yaw/pitch delta from the `before` baseline
- coord delta from baseline
- selected source address
- basis determinant / duplicate-basis drift

If timeline logging is enabled and no explicit file is provided, output defaults under:

- `C:\RIFT MODDING\RiftReader\scripts\captures\stimulus-timelines\`

## Most important behavioral conclusions from this thread

### What the problem is **not**

- not mainly a camera-yaw investigation
- not mainly a memory-reader capability issue
- not “all a PowerShell 5.1 problem”
- not proof that actor yaw was fake

### What the problem most likely is

The biggest live blocker is still **reliable gameplay input + reliable proof capture**, not raw memory reading.

More specifically:

1. earlier proof runs were too loose about foreground focus
2. earlier movement/yaw checks were too dependent on one before/after sample
3. different input paths and test styles got mixed too often
4. current live evidence suggests **real but inconsistent** actor-yaw-like response, not total signal death

## Important live evidence already observed

These findings were already established in this thread and should not be forgotten:

| Finding | Status |
|---|---|
| Current reader itself is read-only | confirmed |
| Latest work targeted actor yaw, not camera yaw | confirmed |
| Main problem was reliable player control/input acceptance, not readback alone | confirmed |
| Movement may have happened while earlier coord readback missed it | plausible / likely |
| Earlier “no movement” conclusion was too strong because the harness was too aggressive | confirmed |

### Strongest recent direct yaw evidence

On the top live candidate used in a direct spot-check:

| Key | Result |
|---|---|
| `A` | produced a large actor-yaw-like delta (about `-67.2°`) with `0` coord drift |
| `D` | produced `0.0°` on that same direct follow-up check |

Interpretation:

- the signal does **not** look dead
- the live proof/control workflow is still asymmetric or inconsistent

## Current modified files in working tree

At handoff time, these files are modified and not committed:

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\screen-actor-orientation-candidates.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\recover-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`

## Validation already done

PowerShell parse checks passed for:

- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\screen-actor-orientation-candidates.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\recover-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\run-aggressive-actor-yaw-discovery.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`

Not yet validated:

- live run with the new timeline logging enabled
- whether post-stimulus sampling alone is enough, or whether true in-hold sampling will be needed later

## Exact workflow rules the next agent should follow

1. **No debug scanning** for this task.
   - No debugger attach
   - No breakpoint tracing
   - No CE debug workflows

2. **Foreground focus is a hard proof requirement.**
   - Require Rift foreground immediately before each input send.
   - Do not refocus away during proof runs.
   - Abort a proof attempt if focus verification fails.

3. **Do not trust single before/after readings alone.**
   - Prefer the new timestamped timeline logging.

4. **Keep the protocol stable.**
   - Do not bounce between many input methods and proof styles in the same diagnosis cycle.

5. **Treat old weak runs carefully.**
   - Some earlier zero-delta movement conclusions were likely too strong.

## Recommended next command

Use the stricter active stimulus script directly with timeline logging:

```powershell
C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1 `
  -Key A `
  -RequireTargetFocus `
  -PostStimulusSampleCount 8 `
  -TimelineIntervalMilliseconds 250 `
  -Json
```

Then repeat with `-Key D` and compare:

- `Comparison.YawDeltaDegrees`
- `Timeline.MaxAbsYawDeltaFromBeforeDegrees`
- `Timeline.MaxCoordDeltaFromBeforeMagnitude`
- timeline NDJSON samples

## Best next objective

The cleanest next proof step is:

> use the new timestamped timeline logging to verify whether `A` vs `D` asymmetry is real, or whether earlier reads were just missing transient changes.

## Notes about session/tooling friction

- The thread hit repeated unified exec process-count warnings.
- The next agent should reuse or close old exec sessions instead of spawning more than necessary.
- The user explicitly wants long runs to continue unattended and only stop for true blockers.
