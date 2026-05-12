# Automated Movement Stimulus Policy

Created: 2026-05-11 EDT / 2026-05-12 UTC
Scope: RiftReader/RiftScan discovery, coordinate-family recovery, pose generation, and proof-anchor rebuild workflows.

## Central clarification

Automated movement is **not categorically forbidden** during discovery or recovery.

Automated movement is allowed when it is used as a **bounded measurement stimulus** and fresh coordinate truth is obtainable before and after the movement pulse.

The critical distinction is:

| Category | Meaning | Allowed before current proof anchor passes? |
|---|---|---:|
| Automated movement stimulus | A bounded, intentional key pulse used to create measurable coordinate displacement for discovery. | Yes, if coordinate truth is obtainable and gates pass. |
| Navigation / autonomous movement | Route following, follow behavior, combat movement, continuous steering, or decision-loop movement. | No. Requires rebuilt proof anchor and fresh same-target `ProofOnly`. |
| Proof-anchor movement smoke test | Movement used to validate the promoted current proof anchor. | No. Requires current proof anchor promotion first. |
| Blind movement | Movement when no fresh coordinate truth is available. | No. |

This policy supersedes any overly broad reading of earlier statements that said movement must always be blocked before `ProofOnly`. That wording was correct for navigation/proof validation, but too restrictive for discovery stimulus.

## Required gates for automated movement stimulus

Automated movement stimulus is allowed only when all of these are true:

1. Exact target PID/HWND is known.
2. Target-control confirms the intended RIFT window/process.
3. A fresh live coordinate reference is obtainable from API/RRAPICOORD or equivalent runtime truth.
4. The movement pulse is bounded and small, for example one `w` pulse with a fixed hold duration.
5. The workflow captures coordinate truth before and after each movement pulse.
6. The workflow records whether movement was sent, which key was sent, hold duration, target PID/HWND, and output artifact paths.
7. The workflow aborts if post-pulse coordinate truth cannot be captured.
8. The workflow does not treat candidate evidence as movement/navigation permission.
9. The workflow uses no Cheat Engine unless explicitly re-authorized for the current session.
10. The workflow does not update `current-truth.md` or `current-proof-anchor-readback.json` until proof promotion and same-target `ProofOnly` pass.

## Why movement stimulus is useful

Coordinate-family recovery needs displacement evidence. A single pose can produce many false positives. Controlled movement creates observable deltas that allow offline analysis to identify the memory family that tracks the real API coordinate.

The proper recovery model is:

```text
capture coordinate A
send bounded movement pulse
capture coordinate B
capture/read memory evidence
repeat for pose C / D when useful
offline correlate candidate families across poses
promote only after multi-pose support
run same-target ProofOnly
update current truth only after ProofOnly passes
```

## Allowed examples

The following pattern is allowed during recovery when coordinate truth is obtainable:

```text
pre-coordinate capture
bounded SendInput pulse
post-coordinate capture
memory capture/readback
cross-pose candidate correlation
```

The existing `scripts/reacquire-current-pid-coordinate-anchor-batch.ps1` may be used in movement-enabled mode for discovery stimulus when the above gates are satisfied. Its movement must remain bounded, logged, and tied to before/after coordinate evidence.

## Forbidden examples

These remain forbidden before current proof validation:

| Forbidden behavior | Reason |
|---|---|
| Navigation loops | This is autonomous behavior, not measurement stimulus. |
| Follow/multibox movement | Requires validated navigation truth, not just coordinate truth. |
| Movement when coordinate capture is unavailable | No way to measure or bound result. |
| Repeated movement pulses without checking coordinates after each pulse | Converts measurement into blind movement. |
| Running movement because a stale pointer might still work | Stale proof pointers must be rejected. |
| Promoting a single-pose match | Single-pose evidence is candidate evidence only. |
| Updating truth files before fresh same-target `ProofOnly` passes | Truth files must remain proof-backed. |

## Decision table

| State | Correct action |
|---|---|
| Current PID/HWND known and coordinate truth obtainable | Automated bounded movement stimulus is allowed for pose generation. |
| Current PID/HWND known but coordinate truth unavailable | Do not move. Restore coordinate truth or use no-movement capture only. |
| Proof pointer stale but coordinate truth obtainable | Use movement stimulus only to collect cross-pose evidence; do not navigate. |
| Candidate family found in one pose | Collect additional pose evidence; do not promote yet. |
| Candidate family tracks across poses | Promote proof anchor, then run same-target `ProofOnly`. |
| `ProofOnly` passes | Movement smoke tests/navigation experiments may resume under their own gates. |
| `ProofOnly` fails | Do not navigate; continue recovery. |

## Assistant workflow rule

Future assistants must not apply a blanket “no automated movement before ProofOnly” rule.

They must instead ask the operational question:

> Is fresh coordinate truth obtainable before and after the movement pulse?

If yes, bounded automated movement may be used as a discovery stimulus. If no, movement must be blocked.

## Terminology to use in future handoffs

Use this wording:

- `movementStimulusAllowed=true` when bounded movement is permitted for discovery because coordinate truth is available.
- `navigationMovementAllowed=false` until proof-anchor promotion and same-target `ProofOnly` pass.
- `movementSent=true/false` must always be recorded.
- `coordinateTruthBeforePulse` and `coordinateTruthAfterPulse` should be recorded when movement stimulus is used.

## Relationship to current truth

This policy does not weaken proof requirements. It only clarifies that bounded automated movement can be a data-collection stimulus when coordinate truth is available.

`current-truth.md` and `current-proof-anchor-readback.json` still require proof-anchor promotion and same-target `ProofOnly` before they are updated as current validated truth.
