# RiftReader Handoff — Navigation sequence dry-run reliability — 2026-06-02 06:40 UTC

## Summary

The continuous route runner now has a safer consumer-facing dry-run sequence
contract. A dry-run no longer requires live turn/movement approval flags, and a
multi-waypoint dry-run no longer pretends all waypoints were reached without
movement.

| Evidence | Result |
|---|---|
| Helper updated | `scripts\static_owner_continuous_route_runner.py`. |
| Dry-run approval behavior | `--dry-run` bypasses `--turn-approved`, `--movement-approved`, and `--allow-candidate-turn-control` because no input can be sent. |
| Sequence dry-run behavior | Stops after the first unreached leg plan with verdict `sequence-dry-run-plan-built`; it does not simulate movement or mark later waypoints reached. |
| Waypoint compatibility | `arrivalRadius` remains canonical; legacy `radius` is accepted when `arrivalRadius` is absent. |
| Route docs | `docs\workflows\navigation-route.md` now has a continuous dry-run command, correct waypoint schema, and current CLI syntax. |

## Safety notes

- No live input, movement, `/reloadui`, screenshot key, Cheat Engine, x64dbg,
  provider writes, target memory writes, proof promotion, actor-chain promotion,
  or route-control promotion is performed by dry-run.
- Dry-run may still perform read-only current-target memory readback and route
  planning against `docs\recovery\current-truth.json`.
- Live multi-waypoint execution still requires the explicit turn, movement, and
  candidate-turn-control approval flags, plus the existing movement freshness
  gates.

## Validation

| Validation | Result |
|---|---|
| Python compile | `python -m py_compile scripts\static_owner_continuous_route_runner.py` passed. |
| Unit tests | `python -m unittest scripts.test_static_owner_continuous_route_runner` passed; `92` tests. |
| Live no-input dry-run | `python scripts\static_owner_continuous_route_runner.py --waypoint-sequence-json scripts\navigation\smoke-test-waypoints.json --dry-run --json` passed. |
| Live dry-run verdict | `sequence-dry-run-plan-built`; `legsPlanned=1`, `legsArrived=0`, `movementSent=false`, `inputSent=false`. |
| Diff check | `git --no-pager diff --check` passed. |

## Current next action

Use the dry-run sequence contract to validate consumer waypoint files and first
leg feasibility without approvals. The next reliability lane is a saved-summary
validator/report for sequence dry-runs so another project can ingest the output
without reading full runner internals.
