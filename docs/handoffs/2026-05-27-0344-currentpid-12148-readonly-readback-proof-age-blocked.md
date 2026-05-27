# **⚠️ HANDOFF — PID 12148 read-only readback, proof age blocked**

Updated UTC: `2026-05-27T07:44:00Z`

## TL;DR

After pushing `main` to `8aed8ba`, a safe read-only explicit-candidate
readback was run for current PID `12148` / HWND `0x640C0C`. The candidate
readback stayed stable at `0x23863A26E50`, but the proof-anchor movement
preflight failed because the cached proof anchor was older than the 60-second
freshness budget.

This preserves the candidate as useful current-process evidence, but **movement
is blocked until a fresh same-target ProofOnly/proof-anchor gate is approved and
rerun**.

## Safety

| Item | Status |
|---|---|
| Game input / movement | `not sent` |
| x64dbg / debugger attach | `not used` |
| Cheat Engine | `not used` |
| Target memory writes | `none` |
| Provider repo writes | `none` |
| Proof/current-truth promotion | `none` |
| Evidence class | `read-only candidate readback` |

## Readback evidence

| Field | Value |
|---|---|
| Wrapper summary | `scripts/captures/riftscan-riftreader-currentpid-12148-readback-wrapper-summary-20260527-034308.json` |
| Source candidate file | `scripts/captures/family-scan-currentpid-12148-20260527-060224-849853/api-family-vec3-candidates.jsonl` |
| Candidate | `api-family-hit-000001` |
| Candidate address | `0x23863A26E50` |
| Readback sample count | `2` |
| Stable across samples | `true` |
| Max delta across samples | `0.0` |
| Readback coordinate | `X=7261.8330078125`, `Y=821.7017822265625`, `Z=3003.057861328125` |
| First recorded UTC | `2026-05-27T07:43:22.5123305Z` |
| Readback integrity | `ok` |

## Proof-age blocker

| Field | Value |
|---|---|
| ProofAnchorStatus | `failed` |
| ProofAnchorMovementAllowed | `false` |
| ProofAnchorSource | `cache` |
| ProofAnchorMaxAgeSeconds | `60` |
| ProofAnchorIssue | `proof_anchor_age_out_of_range_seconds:4029.094` |
| MovementGate from wrapper | `blocked_until_current_process_validated_coord_trace_anchor_or_equivalent_canonical_source` |
| CanonicalCoordSource from wrapper | `none-candidate-watchset-only` |

## Interpretation

- `0x23863A26E50` is still a stable current-process candidate readback.
- The readback **does not** satisfy movement polling invariants by itself.
- Do not treat the recorded coordinate as current-now for movement.
- Do not promote the candidate as a static actor/root chain.
- A fresh exact-target ProofOnly/proof-anchor refresh is required before any
  new movement slice.

## Next safe/gated actions

| Action | Gate |
|---|---|
| Keep doing no-input artifact/status diagnostics | safe |
| Fresh same-target ProofOnly/proof-anchor refresh | requires explicit ProofOnly approval |
| New live movement validation | requires explicit live-input approval after fresh proof |
| New debugger/process-owner tactic | requires explicit debugger approval |
| Restart/reacquisition validation | requires explicit restart/reacquisition approval |
