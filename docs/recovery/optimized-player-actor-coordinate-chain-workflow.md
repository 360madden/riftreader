# Optimized player actor coordinate-chain discovery workflow

Created: 2026-05-21
Scope: fast, current-PID player actor coordinate anchor and static pointer-chain discovery.

## Verdict

The optimal workflow is **provenance-first after the first credible actor-like
coordinate candidate is found**.

Do not keep repeating broad coordinate value scans once a current proof anchor
and actor-like candidate family exist. Broad scans are for reacquisition and
candidate discovery. Static player-actor chain recovery must then pivot to:

```text
target lock
  -> proof-anchor safety gate
  -> actor-like candidate family
  -> owner-layout hypothesis
  -> bounded x64dbg access provenance
  -> normalized access event
  -> module/RVA or static-owner resolver
  -> API-now vs chain-now validation
  -> restart validation
  -> promotion
```

## Two workflows that must stay separate

| Workflow | Purpose | Output | Must not be used as |
|---|---|---|---|
| Current proof-anchor recovery | Finds a current movement-safe coordinate source for the live PID/HWND | `current-proof-anchor-readback.json`, same-target `ProofOnly` pass | A finished player actor static chain |
| Player actor static-chain discovery | Finds a restart-stable/module-rooted resolver to the actor coordinate field | `current-player-actor-chain.json` or equivalent promoted resolver | A movement-safe source until fully validated |

Regression to avoid: treating a dynamic/API-family proof anchor as the player
actor chain just because it currently matches API coordinates.

## Optimized state model

| State | Meaning | Allowed next action |
|---|---|---|
| `target-current` | Exactly one visible/responding RIFT client is bound by PID/HWND/process start | Check proof status |
| `proof-anchor-current` | Same-target proof anchor has passed `ProofOnly` | Use as safety gate only |
| `actor-like-offset-candidate` | Candidate tracks API X/Z or XYZ with stable offset/owner evidence | Inspect owner layout |
| `owner-layout-candidate` | Candidate has plausible owner base, coordinate offset, and module-field signature | Capture access provenance |
| `access-provenance-candidate` | Bounded x64dbg event captured instruction/module/RVA touching the field | Build resolver candidates |
| `chain-resolver-candidate` | A module/RVA/static-owner resolver can locate a current field | Validate API-now vs chain-now |
| `chain-now-valid` | Resolver matches fresh API across poses in the current PID | Restart/relog validation |
| `promoted-player-actor-chain` | Resolver survived restart/relog and same-target ProofOnly | Eligible for movement/navigation use |

Any state before `promoted-player-actor-chain` is candidate evidence only.

## Speed rules

| Rule | Reason |
|---|---|
| Use broad value scans only until the first credible actor-like family exists | Repeating broad scans after that wastes time and finds more copies |
| Freeze the best actor-like candidate and owner hypothesis before x64dbg | Keeps debugger work bounded and targeted |
| Prefer access provenance over more pointer sweeps | The instruction/register context answers who owns or updates the field |
| Use one bounded watchpoint attempt at a time | Prevents accidental debugger scanning and crash-prone loops |
| Normalize every x64dbg event immediately | Converts ephemeral debugger state into durable repo evidence |
| Build resolvers from provenance, not from absolute addresses | Static chains require module/RVA/static-owner paths |
| Validate chain-now against API-now immediately | Prevents stale or cached coordinate copies from advancing |
| Restart validation is mandatory before promotion | Current-PID success is not a static chain |

## Bounded x64dbg policy for this workflow

Default allowed sequence after explicit current-turn authorization:

| Step | Mode | Constraint |
|---:|---|---|
| 1 | `stop-context` | Attach, capture context, detach/resume; no breakpoint |
| 2 | Responsiveness check | Confirm exact RIFT window still responds |
| 3 | `hardware-read` | One watchpoint on the actor-like coordinate field; short timeout; max one go attempt |
| 4 | Offline ingest | Use `scripts/x64dbg_access_event_ingest.py` or successor helper |

Default forbidden behavior:

| Anti-pattern | Why blocked |
|---|---|
| Broad debugger scanning | Higher crash risk and not needed once an actor-like field exists |
| Watchpoint loops without new evidence | Repeats the same risk without increasing signal |
| Memory-access breakpoints by default | Broader/more intrusive than a single hardware watchpoint |
| Memory writes or process patching | Not part of coordinate-chain discovery |
| Treating x64dbg event as truth before resolver validation | Access events are provenance candidates, not promoted chains |

Use `memory-access` or any broader debug scan only after a new explicit operator
decision that accepts the added risk for the current target.

## Artifact contract

Every run of this workflow should produce a single run directory under
`scripts/captures/` with at least:

| Artifact | Required content |
|---|---|
| `run-manifest.json` | PID, HWND, process start, module base, safety flags, command plan |
| `proof-status.json` | Current proof status and proof anchor path |
| `actor-candidate.json` | Candidate address, source file, classification, owner hypothesis |
| `owner-layout.json` | Owner base hypotheses, coordinate offset, module-field signature |
| `x64dbg-stop-context-summary.json` | Stop-context result, attach/detach status, responsiveness verdict |
| `access-event-normalized.json` | Instruction/module/RVA/register context from watchpoint/access event |
| `chain-resolver-candidates.jsonl` | Candidate module/RVA/static-owner resolvers |
| `chain-validation-summary.json` | Fresh API-now vs chain-now per-pose comparison |
| `handoff.md` | Compact resume packet and blockers |

If a helper cannot produce all fields yet, it must explicitly mark the missing
piece as a blocker or `not-run`, not silently omit it.

## Promotion gate

A player actor coordinate chain may be promoted only when all of these are true:

| Requirement | Why |
|---|---|
| Exact current PID/HWND/process start were locked at the start of the run | Prevents target drift |
| Current proof anchor passed same-target `ProofOnly` | Keeps movement safety separate and current |
| Candidate is actor-like, not API-buffer/source-copy only | Prevents wrong-family promotion |
| Access provenance was captured or equivalent static provenance exists | Proves a code/owner relationship |
| Resolver uses module/RVA/static-owner provenance | Avoids absolute-address-only chains |
| API-now vs chain-now passes across at least two displaced poses | Proves live tracking, not stale copy |
| Restart/relog validation passes without old absolute addresses | Proves chain stability |
| Final same-target `ProofOnly` passes | Confirms the promoted source is safe to use |
| SavedVariables were not used as live truth | Avoids post-save snapshot contamination |
| No CE, memory writes, or unapproved broad debug scan occurred | Preserves safety boundary |

## Anti-regression checklist

Before continuing any coordinate-chain work, answer these:

| Question | Required answer |
|---|---|
| Are we recovering a movement-safe proof anchor or a player actor static chain? | Name exactly one lane |
| Are we about to use an API/proof anchor as actor-chain truth? | No |
| Do we already have a credible actor-like candidate? | If yes, stop broad scanning and move to provenance |
| Does the next action advance candidate state? | It must move to owner, access provenance, resolver, validation, or promotion |
| Is x64dbg use bounded and explicitly authorized now? | It must be current-turn authorized and minimally scoped |
| Is any absolute address being treated as restart-stable? | No |
| Is there fresh API-now vs memory-now/chain-now evidence? | Required before validation claims |
| Has restart/relog validation happened? | Required before static-chain promotion |

If the answer to any required gate is no, do not promote and do not claim actor
static-chain truth.
