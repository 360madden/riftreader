# Actor-yaw dynamic second-hop follow-up on `main`

Date: April 17, 2026

## Summary

On the fresh post-crash `main` session, actor-yaw did not behave like one reusable pinned
pointer-hop source.

The strongest current evidence points to a **dynamic second-hop family**:

- focused live input still works well enough to produce real `A`-side yaw-like motion
- the responsive family can relocate or invalidate between probes
- the same pinned source does **not** currently give a clean opposite-direction `D` proof
- later same-session raw search diffs can fall back to weak/noisy results even after a
  stronger earlier `A`-side transient

This means the current problem is no longer just “which absolute source address is actor
yaw?” It is now:

> which live second-hop child within the current family is active at stimulus time, and
> which right-turn stimulus on this client still produces a trusted opposite-direction
> proof?

## What was re-qualified

- focused live `PostMessage` delivery with required foreground verification
- direct `dotnet` reader execution against the built reader assembly
- immediate `ReadProcessMemory` basis sampling against live candidates

## Fresh-session findings

### 1. Search shape changed

Direct search on the fresh session produced:

- `CandidateCount = 0` coord-hit winners
- pointer-hop-only families for the current actor-orientation search

That already differs from the earlier simpler pinned recovery shape.

### 2. A transient A-responsive family was observed

During the follow-up, immediate direct `ReadProcessMemory` sampling on one live second-hop
candidate showed real `A`-side motion:

- source: `0x1B2F0B9CC60`
- basis: `0xA0`
- direct A probe:
  - same source stayed readable during the probe
  - yaw moved by roughly `11.345` degrees over the post-stimulus sample window
  - determinant stayed near `1.0` during the usable part of the run

This was strong evidence that actor-yaw-like motion still exists in the fresh session.

### 3. The same family did not give a reusable D proof

The same pinned `0x1B2F0B9CC60 @ 0xA0` source did not yield a clean opposite-direction `D`
proof:

- direct D probes could invalidate the sampled source into garbage values
- later raw `D` search passes showed the family reappearing on a different child, for
  example:
  - `0x1B2E0013260 @ 0xD4`
  - parent family child `0x1B2F3CF3020 @ 0xD4`
- direct D probe on that later `0xD4` child was flat during the immediate sample window

So the right-turn side is currently not recovered as a single stable pinned source.

### 4. Saved raw diff artifacts from the later same-session passes

These later artifacts are useful mainly as evidence of instability, not as final winners:

- `C:\RIFT MODDING\RiftReader\scripts\captures\direct-actor-orientation-probes\20260417-102435-raw-a-diff.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\direct-actor-orientation-probes\20260417-102435-raw-d-diff.json`

By the time these were captured, the same session had already drifted away from the
stronger earlier transient, which is exactly the problem.

## Current conclusion

The fresh post-crash actor-yaw lane on `main` is now best described as:

- **dynamic**
- **second-hop**
- **A-responsive at least transiently**
- **not yet closed with a trusted reusable opposite-direction right-turn proof**

## Practical next step

Before promoting any new fresh-session actor-yaw winner, re-verify which gameplay key is
the real current right-turn stimulus on this client.

If `D` is still the real right-turn key, then the next fix is likely in the live-input /
second-hop-following logic rather than in basic discovery.

If the live client is no longer turning right on `D`, then further `A/D` screening is
misleading until the right-turn control is re-qualified.
