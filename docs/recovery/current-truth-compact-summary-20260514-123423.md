# RiftReader current truth compact summary

| Field | Value |
|---|---|
| Generated | `2026-05-14T12:34:23Z` |
| Status | `read_only_api_memory_match_displacement_gate_blocked_movement_blocked` |
| Target | `rift_x64` PID `2928`, HWND `0xC0994` |
| Movement allowed | `false` |
| Movement reason | `Same-pose API-memory match remains usable for read-only proof planning, but displacement-gated comparison has valid both-reference count 0; no promotion or movement proof.` |
| Candidate | `api-family-hit-000001` at `0x268E2BC09E0` |
| Route | `api-memory-match` |
| Promotion readiness | `blocked-promotion-readiness` |
| Raw both-reference matches | `2` |
| Valid both-reference matches | `0` |
| Displaced readiness | `blocked` / planar `5.59732083466666e-05` |
| Next | `Capture a genuinely displaced API reference for the same PID/HWND, rerun displacement-gated comparison, regenerate route/review/readiness, then keep movement blocked until proof promotion and same-target ProofOnly pass.` |

## Blockers

- `promotion-two-reference-candidate-match-missing`
- `promotion-displaced-readiness-not-passed:blocked`
- `displaced-api-reference-planar-distance-too-small:5.37587e-05<1.0`
- `displaced-reference-age-exceeded:1363.884>300.0`
- `displaced-reference-planar-distance-too-small:5.6e-05<1.0`
- `route-valid-both-reference-count=0-after-displacement-gate`
- `movement remains blocked until true displaced proof/static proof/same-target ProofOnly/explicit approval`
- `pointer-scan-current-candidate-direct-hit-count=0`
- `movement remains blocked until promotion readiness, proof/static chain, same-target ProofOnly, and explicit approval`
- `fresh displaced/two-reference match missing; bothReferenceMatchCount=0`
- `displaced-reference readiness is blocked`
- `proof-anchor promotion allowed=False`
