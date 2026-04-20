---
state: current
as_of: 2026-04-19
---

# Actor-Facing Discovery Solution Proposal (2026-04-19)

## Scope

This proposal defines the shortest meaningful path to discover the real
**actor-facing** source for Rift using the evidence already gathered across:

- `C:\RIFT MODDING\RiftReader_facing`
- `C:\RIFT MODDING\RiftReader`

It explicitly treats the current incumbent actor-facing artifact as **rejected**
until a new source passes live behavioral validation.

## Executive verdict

| Area | Verdict | Why |
|---|---|---|
| Fresh player anchor | **trusted** | `0x1B0E8504CF0` (`fam-6F81F26E`) is still the best verified live player-current anchor |
| Incumbent actor-facing artifact | **rejected** | The scene visibly turned, but captured yaw stayed unchanged |
| Best current lead | **native-trace-backed candidate family** | `0x1B115201EB0 @ +0xD4` is now proven to be code-path live during manual turn |
| Best discovery strategy | **instruction-first, validation-first** | Structural scans alone already produced a live-false candidate |
| Cheat Engine posture | **disabled by default** | It added instability and did not produce the real source |

## Current evidence snapshot

### Trusted live anchor

| Field | Value |
|---|---|
| Artifact | `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-current-anchor.json` |
| Address | `0x1B0E8504CF0` |
| Family | `fam-6F81F26E` |
| Signature | `level@-144|health[1]@-136|health[2]@-128|health[3]@-120|coords@0` |
| Meaning | Best verified current-player anchor |

### Rejected incumbent candidate

| Field | Value |
|---|---|
| Artifact | `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-actor-facing.json` |
| Source address | `0x1B1230D39E0` |
| Forward offset | `0x144` |
| Structural status | determinant and row magnitudes looked valid |
| Behavioral status | **rejected** |
| Rejection reason | visual left turn occurred, but yaw stayed `26.7241523772533° -> 26.7241523772533°` |

### Native trace-backed candidate family

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Candidate object base | `0x1B115201EB0` |
| Candidate forward block | `+0xD4` |
| Watched address | `0x1B115201F84` |
| Hot sibling / effective address | `0x1B115201F8C` |
| Dominant instruction | `rift_x64.exe+0x5CDC93 : movss xmm3,[rcx+8]` |
| Base register during hit | `RCX = 0x1B115201F84` |
| Trace status | attached, 4 hits, detached cleanly |
| Meaning | This family is **code-path live** during manual turn stimulus |

## Root cause of the current stall

| Problem | Evidence | Impact |
|---|---|---|
| Structural validity is not enough | The incumbent candidate passed integrity checks but stayed frozen through a real turn | Shape-only ranking is producing false positives |
| Current-player anchor search was too local | Base-window and first-level child scans around `0x1B0E8504CF0` did not expose a turn-responsive source | The true facing source may sit on an adjacent controller / projector / selected-source family |
| Candidate search can drift to plausible but unproven families | Pointer-hop ranking found strong-looking candidates outside the verified current-player family | Ranking must be gated by live behavior, not just matrix quality |
| Behavioral proof has not yet been completed on the new live family | The native trace proves code-path activity, but not yet opposite-turn yaw truth | The candidate is promising, not confirmed |

## Proposed solution

The solution is to switch from **broad data-shape hunting** to a **three-gate
promotion pipeline**:

1. **Code-path gate** — the candidate must be touched by live turn code.
2. **Behavior gate** — the candidate must move correctly on left and right turn.
3. **Navigation gate** — the candidate must predict movement heading well enough to be useful.

Only sources that pass all three gates should be promoted to actor-facing.

## Why this is the shortest meaningful path

| Option | Speed | Risk | Recommendation |
|---|---:|---:|---|
| Broad float / matrix rescans from scratch | slow | high | no |
| Re-trying the rejected incumbent | fast | very high | no |
| Pointer-hop ranking without code-path proof | medium | high | no |
| **Native trace -> focused object inspection -> behavior proof** | **fastest** | **lowest available risk** | **yes** |

The native trace already narrowed the field to one live family. The fastest path
now is to prove or reject that family decisively instead of widening the search
again.

## Primary discovery workflow

### Phase 1 — Freeze the evidence contract

Treat these as the active rules:

| Rule | Requirement |
|---|---|
| Source of truth for live player anchor | `C:\RIFT MODDING\RiftReader_facing\scripts\captures\player-current-anchor.json` |
| Rejected artifact policy | `player-actor-facing.json` must not be trusted unless replaced by a behavior-proven source |
| Tool policy | Reader-native and repo-native debug tooling first; no Cheat Engine by default |
| Live interaction policy | prompt before interactive game-window actions; prefer manual A/D by the user |

### Phase 2 — Finish proving the native-trace-backed family

Run the next experiments only against the live candidate family around
`0x1B115201EB0`.

#### Experiment 1 — left-only access trace on the hot sibling

Target:

- watch `0x1B115201F8C`

Goal:

- prove that the same instruction family stays active during a controlled
  **left-only** turn window
- record whether hit count, instruction identity, and effective addresses remain
  stable

Acceptance:

- repeated hits on the same family or nearby same-block instructions
- no evidence that the prior hits were one-off noise

#### Experiment 2 — right-only access trace on the same component

Target:

- watch `0x1B115201F8C`

Goal:

- prove the same object participates during **right-only** turn stimulus
- compare left vs right trace symmetry

Acceptance:

- same object family remains active on both directions
- no shift to a completely different family for opposite turns

#### Experiment 3 — write trace on the block

Targets, in order:

1. `0x1B115201F8C`
2. `0x1B115201F84`

Goal:

- determine whether the engine is **writing** the actor-facing data here, rather
  than only reading it

Acceptance:

- any turn-correlated write hit to this block or its immediate neighbors
- if no write fires, access-trace evidence can still keep the family alive, but
  confidence stays lower

### Phase 3 — Inspect the live object, not the whole process

Once the trace family is stable, inspect only the region around:

- object base: `0x1B115201EB0`
- likely orientation block: `0xD4..0xEC`

What to look for:

| Pattern | Why it matters |
|---|---|
| 3-float vector block | likely forward/right/up row or column |
| 4-float normalized block | likely quaternion |
| neighboring float that tracks monotonic angle | possible direct yaw storage |
| duplicated vector block nearby | common in cached actor/camera/controller layouts |

This inspection should stay tightly scoped. Do **not** go back to broad blind
heap walking until this family is either proven or rejected.

### Phase 4 — Capture behavioral truth

The next validation artifact must be based on **before / left / right** reads of
this exact family, not on the rejected incumbent.

Required checks:

| Check | Pass condition |
|---|---|
| Idle stability | low jitter while standing still |
| Left turn | clear directional change |
| Right turn | clear opposite directional change |
| Repeatability | similar magnitude across repeated runs |
| Low planar drift | the candidate changes because of turning, not movement |

Promotion rule:

- if the candidate changes monotonically on left turn and reverses correctly on
  right turn, it graduates from **trace-backed candidate** to **behavior-backed candidate**
- if it also predicts forward movement heading within the existing navigation
  thresholds, it becomes the new actor-facing source

### Phase 5 — Only then wire it into the facing pipeline

After behavior proof, update the active capture path in
`C:\RIFT MODDING\RiftReader_facing` so the reader and scripts consume the new
source instead of the rejected incumbent.

Likely files to touch only after proof exists:

- `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Models\PlayerOrientationCandidateFinder.cs`
- `C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\Models\OrientationCandidateLedgerLoader.cs`
- `C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-facing.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader_facing\scripts\test-actor-facing-validation.ps1`

## Exact command pattern to prefer

These examples are intentionally biased toward the repo-native debug worker in:

- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj`

### Access trace

```powershell
dotnet run --project 'C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj' -- --process-name rift_x64 --debug-trace-memory-access --debug-address 0x1B115201F8C --debug-width 4 --debug-timeout-ms 12000 --debug-max-hits 4 --debug-output-directory 'C:\RIFT MODDING\RiftReader\scripts\captures\debug-traces\actor-facing-left-or-right' --json
```

### Write trace

```powershell
dotnet run --project 'C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj' -- --process-name rift_x64 --debug-trace-memory-write --debug-address 0x1B115201F8C --debug-width 4 --debug-timeout-ms 12000 --debug-max-hits 4 --debug-output-directory 'C:\RIFT MODDING\RiftReader\scripts\captures\debug-traces\actor-facing-write' --json
```

### Reader-only anchor refresh

```powershell
dotnet run --project 'C:\RIFT MODDING\RiftReader_facing\reader\RiftReader.Reader\RiftReader.Reader.csproj' -- --process-name rift_x64 --read-player-current --json
```

## Promotion and rejection criteria

### Promote a candidate only if all are true

| Criterion | Required result |
|---|---|
| Code-path live | proven by native trace |
| Left turn response | clear change |
| Right turn response | clear opposite change |
| Repeatability | similar across repeated runs |
| Navigation usefulness | forward movement heading roughly agrees with candidate heading |

### Reject a candidate immediately if any are true

| Rejection trigger | Meaning |
|---|---|
| Visual turn occurs but captured yaw stays flat | not the real actor-facing source |
| Candidate only looks orthonormal but never correlates with behavior | false structural positive |
| Opposite-turn runs activate a different unrelated family | family is not stable enough |
| Candidate only moves with planar translation, not turn stimulus | locomotion-adjacent, not facing |

## What not to do next

| Avoid | Reason |
|---|---|
| Reusing `0x1B1230D39E0 + 0x144` as if it were still viable | it is already behaviorally false |
| Broad rescans of unrelated families before finishing the traced family | wastes the best live lead |
| Promoting another candidate on determinant / row magnitude alone | this already failed once |
| Cheat Engine pointer work by default | thread rule says no, and it added noise |
| Scripted game input without prompt | avoid accidental live interaction |

## Definition of done

Actor-facing discovery is complete only when all of the following are true:

| Requirement | Status needed |
|---|---|
| A live source is traced to a real turn-update code path | required |
| The source changes correctly on left and right turn | required |
| The source is repeatable across runs | required |
| The source predicts movement heading well enough for navigation | required |
| The active artifact path points to the proven source instead of the rejected incumbent | required |

## Practical next move

The single best next move is:

1. run a **left-only** native access trace on `0x1B115201F8C`
2. run a **right-only** native access trace on `0x1B115201F8C`
3. if the same family survives both, run a **write trace** on `0x1B115201F8C`

That sequence gives the shortest path from "promising live family" to either
"confirmed actor-facing lead" or "reject and move on".
