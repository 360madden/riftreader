# Static player coordinate pointer-chain discovery — 10-phase plan

## Goal

Promote a restart-stable static pointer chain that resolves the player actor coordinate triplet from module/static-root provenance, validates against fresh API coordinates, survives process restart/relog, and is safe for future movement/navigation use.

## Starting truth

| Field | Current value |
|---|---|
| Current target | PID `42508`, HWND `0x80E00` |
| Dynamic coord anchor | `0x1FD21900420` |
| Candidate ID | `api-family-hit-000001` |
| Proof status | `current-target-proofonly-passed` |
| Movement allowed effective | `true` |
| Static chain status | Not proven |

## Phase 1 — Current target and proof baseline freeze

1. Discover current RIFT targets.
2. Require exactly one visible/responding `rift_x64` window.
3. Run `python .\scripts\coordinate_recovery_status.py --json`.
4. Confirm `current-target-proofonly-passed` for the same PID/HWND.
5. Capture baseline screenshot through Rift MCP.
6. Write a timestamped static-chain discovery manifest.

Output: run manifest, target snapshot, baseline screenshot.

## Phase 2 — Module map and memory-region inventory

1. Capture module list for the current PID.
2. Capture readable memory region inventory.
3. Classify module-backed/static, heap/private, stack/thread, mapped regions.
4. Mark stack/scratch regions low confidence.
5. Write region scoring policy.

Output: module map, memory inventory, region score plan.

## Phase 3 — Coordinate leaf neighborhood inspection

1. Inspect bytes/floats/pointers around the proven dynamic coord leaf.
2. Decode narrow and wide neighborhoods.
3. Identify nearby pointer-like values, coordinate copies, object headers, and actor-adjacent fields.
4. Compare nearby floats against API coordinate.
5. Record likely owner-base candidates.

Output: coord leaf neighborhood report, owner-base candidates, nearby float copy inventory.

## Phase 4 — Reverse pointer-owner scan

1. Scan current memory for pointers to the coord leaf, nearby owner bases, and aligned surrounding addresses.
2. Rank hits by region type: module/static highest, stable heap medium, stack/scratch lowest.
3. Build candidate edges from root/owner toward coord leaf.
4. Keep every hit candidate-only.

Output: reverse pointer hits, owner candidates, candidate edge graph.

## Phase 5 — Chain candidate generation

1. Generate pointer chains from module base/RVA or static/global-like roots.
2. Store module, base, RVA, offsets, final coord offset, axis order, current resolved address.
3. Reject raw absolute-address-only chains as static candidates.
4. Preserve absolute address only as current-PID evidence.

Output: chain-candidates JSONL and chain generation summary.

## Phase 6 — Current-PID chain resolver validation

1. Resolve each chain in the current PID.
2. Read X/Y/Z from resolved leaf.
3. Compare to fresh API-now coordinate.
4. Reject chains that resolve outside expected regions, point to stale copies, or exceed tolerance.
5. Rank current-PID resolver results.

Output: resolver results, chain ranking, API-vs-chain summary.

## Phase 7 — Multi-pose live displacement validation

1. Capture baseline API coordinate and chain resolves.
2. Focus exact target.
3. Send bounded movement only after target preflight.
4. After each pose, capture API coordinate and chain resolves.
5. Require at least two displaced poses and `maxPlanarDisplacement >= 1.0`.
6. Reject chains that do not track displaced API positions.

Output: multi-pose chain validation, displacement support table, visual frame-change summary.

## Phase 8 — Restart/relog static-chain validation

1. Save current-PID candidate chain artifacts.
2. Restart/relog RIFT.
3. Re-run target discovery and API reference capture.
4. Resolve chains using module/RVA/static-root paths only.
5. Do not use old absolute addresses.
6. Repeat API-vs-chain and movement/displacement validation in the new PID.

Output: restart target snapshot, restart resolver results, restart displacement validation.

## Phase 9 — Promotion gate and durable resolver integration

Promotion requires:

- Current PID proof passed.
- At least two displaced poses.
- `maxPlanarDisplacement >= 1.0`.
- API-vs-chain max abs delta within tolerance.
- Module/RVA/static-root provenance.
- Restart/relog validation.
- Same-target ProofOnly after promotion.
- No SavedVariables live truth.
- No old absolute-address dependency.

Output: promoted static coordinate chain artifact, resolver summary, updated current truth docs, historical archive.

## Phase 10 — Regression, handoff, and operational guardrails

1. Add tests for chain schema, resolver fail-closed behavior, old absolute address rejection, zero displacement rejection, and stale PID/HWND rejection.
2. Run focused validation.
3. Write compact handoff with target, chain root, offsets, restart validation, safety summary, and remaining blockers.
4. Mark unpromoted leads candidate-only.

Output: regression tests, final handoff, current truth docs.

## Hard rules

- Current dynamic anchor is only a leaf, not a static chain.
- API-now vs chain-now is mandatory.
- Displacement is mandatory.
- Restart validation is mandatory.
- Module/RVA provenance is mandatory.
- Duplicate RIFT clients block discovery.
- CE and live x64dbg require explicit current-turn reauthorization.
