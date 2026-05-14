# Handoff — Fresh No-Displacement Route Gate

Created: `2026-05-14T12:12:52Z`

## Verdict

A fresh no-input API/readback pass succeeded for PID `2928` / HWND `0xC0994`. The route-selected candidate remains `api-family-hit-000001` at `0x268E2BC09E0`, but the attempted displaced reference was not actually displaced enough. Movement and proof-anchor promotion remain blocked.

## Current evidence

| Field | Value |
|---|---|
| Route | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-080919-fresh-no-displacement/coordinate-proof-route.json` |
| Route status | `api-memory-match` |
| Candidate | `api-family-hit-000001` |
| Address | `0x268E2BC09E0` |
| Candidate file | `scripts/captures/family-scan-currentpid-2928-20260514-114535-319032/api-family-vec3-candidates.jsonl` |
| Fresh API reference | `scripts/captures/riftscan-proof-readonly-fresh-displaced-attempt-1-20260514-120812/readonly-fresh-displaced-attempt-1-api-reference.json` |
| Memory readback | `scripts/captures/riftscan-proof-readonly-fresh-displaced-attempt-1-20260514-120812/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260514-080850.json` |
| Reference match count | `1` |
| Max abs delta | `4.960937758369255e-07` |
| Displaced readiness | `blocked` |
| Promotion readiness | `blocked-promotion-readiness` |
| Pointer scan direct hits | `None` |
| Movement allowed | `false` |

## Blockers

- promotion-displaced-readiness-not-passed:blocked
- displaced-reference-age-exceeded:1363.884>300.0
- displaced-reference-planar-distance-too-small:5.6e-05<1.0
- pointer-scan-current-candidate-direct-hit-count=0
- movement remains blocked until promotion readiness, proof/static chain, same-target ProofOnly, and explicit approval

## Safe resume artifacts

| Artifact | Path |
|---|---|
| Milestone review | `scripts/captures/riftscan-milestone-review-20260514-121022.json` |
| Readiness gate | `scripts/captures/coordinate-proof-readiness-gate-20260514-081022-fresh-no-displacement/summary.json` |
| Pointer scan | `scripts/captures/pointer-family-scan-route-selected-currentpid-2928-20260514-081030/summary.json` |
| HTML summary | `docs/recovery/coordinate-proof-route-actions-1-10-summary-2026-05-14-121252.html` |

## Next best action

Manually displace the player or provide an approved movement/debugging lane, then capture a genuinely displaced API reference and rerun comparison + route generation. Do not promote or move from the current same-pose match.
