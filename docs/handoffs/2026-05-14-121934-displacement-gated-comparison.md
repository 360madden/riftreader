# Handoff — Displacement-Gated Comparison

Created: `2026-05-14T12:19:34Z`

## Verdict

The latest candidate `api-family-hit-000001` at `0x268E2BC09E0` still matches API-now/memory-now, but the apparent two-reference comparison is now correctly gated as **not valid displaced proof**. Raw both-reference matches are preserved for audit, but valid promotion count is `0` because the displaced API reference moved only `5.59732083466666e-05` planar units.

## Evidence table

| Field | Value |
|---|---|
| Route | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-081737-displacement-gated/coordinate-proof-route.json` |
| Route status | `api-memory-match` |
| Candidate comparison | `scripts/captures/coordinate-candidate-comparison-currentpid-2928-20260514-081730-displacement-gated/summary.json` |
| Comparison status | `blocked` |
| Raw both-reference matches | `2` |
| Valid both-reference matches | `0` |
| Comparison blockers | `['displaced-api-reference-planar-distance-too-small:5.37587e-05<1.0']` |
| Displaced readiness | `blocked` |
| Displaced planar distance | `5.59732083466666e-05` |
| Promotion readiness | `blocked-promotion-readiness` |
| Proof-anchor promotion allowed | `False` |
| Readiness gate | `scripts/captures/coordinate-proof-readiness-gate-20260514-081756-displacement-gated/summary.json` |
| Movement allowed | `false` |

## Blockers

- promotion-two-reference-candidate-match-missing
- promotion-displaced-readiness-not-passed:blocked
- displaced-api-reference-planar-distance-too-small:5.37587e-05<1.0
- displaced-reference-age-exceeded:1363.884>300.0
- displaced-reference-planar-distance-too-small:5.6e-05<1.0
- route-valid-both-reference-count=0-after-displacement-gate
- movement remains blocked until true displaced proof/static proof/same-target ProofOnly/explicit approval

## Next action

Get a genuinely displaced pose for the same PID/HWND, then rerun candidate comparison with `--min-displaced-planar-distance 1.0`, regenerate the route, and keep movement blocked until proof promotion and same-target ProofOnly pass.
