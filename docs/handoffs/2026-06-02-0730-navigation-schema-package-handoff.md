# Navigation consumer schema package handoff — 2026-06-02 07:30 UTC

## Result

RiftReader now has a tracked JSON-schema package and repo validator for the
practical automated-navigation consumer artifacts built in the previous slices.
Another project can validate saved pose, waypoint, dry-run sequence, contract,
and readiness JSON without reading helper internals.

## What changed

| Area | Result |
|---|---|
| Schemas | Added `docs\schemas\navigation\` with draft-07 schema contracts for consumer state, normalized waypoints, sequence dry-runs, sequence contract reports, and waypoint readiness summaries. |
| Validator | Added `scripts\navigation_schema_validate.py` plus launcher `scripts\riftreader-navigation-schema-validate.cmd`. |
| Schema inference | Validator infers from top-level `kind` or `provenance.kind`; `--schema-key` can override. |
| Safety | Validator reads saved JSON only. It performs no live target reads, input, movement, debugger/CE attach, provider writes, target memory writes, or promotion. |
| Tool catalog | Added canonical `navigation-schema-validate` tool; tool count is now `45`. |
| Workflow docs | `docs\workflows\navigation-route.md` now includes the consumer schema validation command. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\navigation_schema_validate.py scripts\test_navigation_schema_validate.py scripts\test_tool_catalog.py tools\riftreader_workflow\tool_catalog.py` | Passed. |
| `python -m unittest scripts.test_navigation_schema_validate scripts.test_tool_catalog` | Passed: `Ran 11 tests in 0.772s OK`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` | Passed with `schemaKey=navigation-waypoint-readiness`, `validationErrorCount=0`. |
| `scripts\riftreader-tool-catalog.cmd --compact-json` | Passed with `total=45`, `exists=45`, `blockers=[]`. |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed with `blockerCount=0`, `warningCount=0`. |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed with `safeValidationCommandCount=5`, `blockers=[]`. |

## Practical navigation readiness

| Capability | Status |
|---|---|
| Consumer pose contract | Working: read-only current position/yaw JSON exists. |
| Waypoint normalization | Working: waypoint files can be linted and canonicalized. |
| No-input sequence dry-run | Working: plans first unreached leg without simulating movement. |
| Consumer contract report | Working: validates saved sequence dry-run safety and consumption rules. |
| Consumer schema validation | Working: downstream projects can validate saved navigation artifacts. |
| Reliable live multi-waypoint navigation | Not complete: live movement/turn execution remains gated by explicit approvals and proof freshness. |

## Current next action

Build a tiny downstream-consumer fixture/app that reads:

1. `.riftreader-local\navigation-consumer-state\latest\summary.json`
2. a normalized waypoint file from waypoint readiness
3. the sequence dry-run + contract report
4. the schema validation summary

Then expose a single `navigation-consumer-demo` report that says exactly what an
external project can safely do next: render map/route, request a gated live run,
or block on stale target/proof.
