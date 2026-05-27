# Static player coordinate pointer-chain discovery — optimized 10-phase plan

Updated: 2026-05-21
Detailed workflow: `docs/recovery/optimized-player-actor-coordinate-chain-workflow.md`

## Goal

Promote a restart-stable static pointer chain that resolves the player actor
coordinate triplet from module/RVA or static-owner provenance, validates against
fresh API coordinates, survives restart/relog, and is safe for future
movement/navigation use.

## Core correction

The old workflow over-weighted coordinate value scans. That is safe for
current-PID proof-anchor reacquisition, but too slow and noisy for static actor
chain discovery.

After a current proof anchor and credible actor-like candidate exist, the
workflow must pivot to **owner/access provenance**:

```text
current target
  -> proof-anchor safety gate
  -> actor-like coordinate candidate
  -> owner-layout hypothesis
  -> bounded access provenance
  -> static/module resolver candidate
  -> API-now vs chain-now validation
  -> restart validation
  -> promotion
```

## Starting-truth rule

Do not put session-specific PID/HWND/addresses in this plan as durable truth.
Every run must discover current target data fresh and record it in that run's
manifest.

| Evidence type | Durable use |
|---|---|
| PID/HWND/process start | Current-run target identity only |
| Absolute heap address | Current-PID evidence only |
| Proof anchor | Movement-safety gate only |
| Actor-like candidate | Chain-discovery lead only |
| Module/RVA/static-owner resolver | Static-chain candidate |

## Phase 1 — Current target lock

1. Run current target discovery.
2. Require exactly one visible/responding `rift_x64` window.
3. Bind exact PID/HWND/process start/module base.
4. No-input target-control/visual checks may run in the no-movement recovery lane.
5. Abort on duplicate clients, minimized target, target mismatch, or missing visible RIFT window.

Output: `target.json`, baseline screenshot, no movement/input.

## Phase 2 — Proof-anchor safety gate

1. Run `python .\scripts\coordinate_recovery_status.py --json`.
2. If same-target proof anchor is current, keep it as a safety gate only.
3. If target drift exists, run current-PID coordinate-family recovery through
   the no-movement lane first.
4. Recommend displacement stimulus only after a current candidate file and
   initial API-now vs memory-now match exist; movement still requires explicit
   approval.
5. Keep `ProofOnly`, current-truth updates, debugger/CE, provider writes, and
   chain promotion as separate explicit gates.
6. Do not use a proof/API-family anchor as actor static-chain truth.

Output: `proof-status.json`, stale/current proof verdict.

## Phase 3 — Actor-like candidate selection

1. Prefer existing current-PID actor-like candidate evidence if it matches the current target epoch.
2. If no credible current actor-like family exists, use the no-movement
   recovery/scan-plan lane first; run a broad value scan once only when needed
   to find candidate families.
3. Classify candidates semantically: API/proof buffer, copy family, actor-like offset, owner-layout candidate.
4. Freeze the best actor-like candidate before debugger work.

Output: `actor-candidate.json`, candidate classification, blocker if only API-buffer evidence exists.

## Phase 4 — Owner-layout hypothesis

1. Inspect neighborhood around the actor-like candidate.
2. Identify likely owner base and coordinate offset.
3. Record module pointer fields, vtable-like fields, nearby actor-adjacent floats, and pointer slots.
4. Reject absolute-address-only ownership claims.

Output: `owner-layout.json`, root signature, owner-module-field score.

## Phase 5 — Bounded x64dbg attach safety check

1. Require explicit current-turn live-debugger authorization.
2. Run `stop-context` first: attach, capture context, detach/resume.
3. Set no breakpoint in this phase.
4. Verify the exact RIFT window still responds after detach.

Output: `x64dbg-stop-context-summary.json`, responsiveness verdict.

## Phase 6 — Single access-provenance capture

1. If Phase 5 is safe, run one short hardware watchpoint on the actor-like coordinate field.
2. Prefer a 12-byte XYZ window when supported; otherwise use a focused scalar and record limitation.
3. Use short timeout and max one go attempt.
4. Do not loop watchpoints without new evidence.
5. Avoid memory-access breakpoints unless explicitly approved as a higher-risk step.

Output: raw x64dbg access event and safety summary.

## Phase 7 — Offline event normalization

1. Normalize x64dbg event with repo-owned ingest tooling.
2. Extract instruction pointer, module/RVA, disassembly, register context, memory operands, and target field.
3. Link event to target PID/HWND/process start and candidate address.
4. Keep the result candidate-only.

Output: `access-event-normalized.json`.

## Phase 8 — Resolver candidate generation

1. Generate resolver candidates from module/RVA/static-owner provenance.
2. Do not generate promoted chains from raw absolute heap addresses.
3. Include owner offset, coordinate offset, axis order, module name, RVA, and current resolved address.
4. Record failure reason for rejected candidates.

Output: `chain-resolver-candidates.jsonl`, chain generation summary.

## Phase 9 — API-now vs chain-now validation

1. Capture fresh API/runtime coordinate immediately before chain readback.
2. Resolve each chain in the current PID.
3. Compare chain XYZ to API XYZ with per-axis deltas.
4. Require at least two displaced poses and `maxPlanarDisplacement >= 1.0`.
5. Reject stale copies, source-copy buffers, and chains that do not follow displacement.

Output: `chain-validation-summary.json`, pose comparison table.

## Phase 10 — Restart validation, promotion, and handoff

Promotion requires:

- exact current target lock;
- same-target proof anchor passed `ProofOnly`;
- actor-like candidate, not proof/API-buffer only;
- access/static provenance;
- module/RVA/static-owner resolver;
- multi-pose API-now vs chain-now success;
- restart/relog validation without stale absolute addresses;
- final same-target `ProofOnly`;
- no SavedVariables live truth;
- no CE or unapproved broad debug scan.

Output: promoted static coordinate chain artifact, updated current truth docs,
historical archive, compact handoff, and focused regression tests.

## Hard anti-regression rules

| Rule | Required behavior |
|---|---|
| Proof anchor is not actor chain | Use proof anchor only as safety/currentness gate |
| Actor chain discovery is provenance-first after candidate selection | Stop repeating broad value scans once a credible actor-like candidate exists |
| x64dbg must be bounded | Start with stop-context; then at most one targeted hardware watchpoint per decision |
| Absolute addresses are session evidence | Never promote them as restart-stable |
| API-now vs chain-now is mandatory | Validate immediately around each pose |
| Restart validation is mandatory | Current-PID success is not static-chain truth |
| Candidate states must be explicit | Use `candidate-only` until every promotion gate passes |
