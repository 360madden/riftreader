# **⚠️ HANDOFF — post-policy push no-input proof pose, ProofOnly still required**

Updated UTC: `2026-05-27T08:32:30Z`

## TL;DR

The policy patch `a50ad93 Guard live input audit proof freshness` is now on
`origin/main` and both GitHub checks are green. After that push, a safe
no-input/no-CE proof-pose capture was run against exact target PID `12148` /
HWND `0x640C0C` using explicit candidate file
`scripts/captures/family-scan-currentpid-12148-20260527-060224-849853/api-family-vec3-candidates.jsonl`.

The current candidate `api-family-hit-000001` at `0x23863A26E50` matched a
same-time API reference with max delta `0.0030078125` across a 4-sample stable
readback. This is strong current-PID candidate evidence, but **movement remains
blocked** because the proof-anchor preflight is stale and the evidence is still
candidate/readback evidence, not a refreshed movement-grade ProofOnly anchor.

## Safety

| Item | Status |
|---|---|
| Game input / movement | `not sent` |
| x64dbg / debugger attach | `not used` |
| Cheat Engine | `not used` |
| Target memory writes | `none` |
| Provider repo writes | `none` |
| Proof/current-truth promotion | `none` |
| Evidence class | `same-time API reference + read-only candidate readback` |

## Git / CI status

| Field | Value |
|---|---|
| Branch | `main` |
| Pushed commit | `a50ad93dfe96381e12eba1f3bacd119de65df5c0` |
| Commit subject | `Guard live input audit proof freshness` |
| Remote | `origin/main` |
| `.NET build and test` | `success` |
| `RiftReader Policy` | `success` |

## No-input proof-pose evidence

| Field | Value |
|---|---|
| Output root | `scripts/captures/riftscan-proof-post-policy-push-no-input-20260527-083130` |
| Reference file | `scripts/captures/riftscan-proof-post-policy-push-no-input-20260527-083130/post-policy-push-no-input-api-reference.json` |
| Readback summary | `scripts/captures/riftscan-proof-post-policy-push-no-input-20260527-083130/riftscan-riftreader-currentpid-12148-readback-wrapper-summary-20260527-043148.json` |
| Candidate file | `scripts/captures/family-scan-currentpid-12148-20260527-060224-849853/api-family-vec3-candidates.jsonl` |
| Candidate | `api-family-hit-000001` |
| Candidate address | `0x23863A26E50` |
| Reference matched readback | `true` |
| Reference max abs delta | `0.0030078125000727596` |
| Reference planar distance | `0.00369064403922629` |
| Reference spatial distance | `0.004098436890351616` |
| Stable decoded candidates | `1` |
| Readback sample count | `4` |
| Readback failures | `0` |
| Current coordinate | `X=7261.8330078125`, `Y=821.7017822265625`, `Z=3003.057861328125` |
| Current coordinate recorded UTC | `2026-05-27T08:31:54.2385174Z` |

## Proof-age blocker

| Field | Value |
|---|---|
| ProofAnchorStatus | `failed` |
| ProofAnchorIssue | `proof_anchor_age_out_of_range_seconds:6948.390` |
| MovementAllowed | `false` |
| MovementGate | `blocked_until_current_process_validated_coord_trace_anchor_or_equivalent_canonical_source` |
| Required next proof | Fresh same-target ProofOnly/proof-anchor refresh |

## Interpretation

- `api-family-hit-000001` remains a high-value current-PID coordinate candidate.
- The same-time API reference match is current evidence that candidate readback
  aligns with live API coordinates for this stationary pose.
- This does **not** prove movement polling safety by itself.
- This does **not** promote a static actor/root chain.
- This does **not** update current truth or replace ProofOnly.
- A fresh exact-target ProofOnly/proof-anchor refresh remains the next required
  gate before any movement or movement-polling slice.

## Next safe/gated actions

| Action | Gate |
|---|---|
| Re-run no-input status/readback if the process stays alive | safe |
| Fresh same-target ProofOnly/proof-anchor refresh | requires explicit ProofOnly approval |
| New live movement validation | requires explicit live-input approval after fresh proof |
| New debugger/process-owner tactic | requires explicit debugger approval |
| Restart/reacquisition validation | requires explicit restart/reacquisition approval |
