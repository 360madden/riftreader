# RiftReader Handoff — Navigation waypoint readiness infrastructure — 2026-06-02 07:08 UTC

## Summary

RiftReader now has a one-command waypoint readiness workflow for practical
automated-navigation consumers. It validates waypoint files, writes a normalized
canonical waypoint artifact, optionally runs a no-input sequence dry-run, and
then validates the saved sequence contract report.

| Evidence | Result |
|---|---|
| Readiness helper | `scripts\navigation_waypoint_readiness.py`; launcher `scripts\riftreader-navigation-waypoint-readiness.cmd`. |
| Waypoint lint | Validates `waypoints[]`, finite `x/y/z`, nonnegative `arrivalRadius`, duplicate IDs, and requested ID filters. |
| Normalization | Writes canonical `normalized-waypoints.json`; legacy `radius` becomes `arrivalRadius`; missing IDs become `waypoint-###`. |
| Dry-run bundle | Default mode runs `static_owner_continuous_route_runner.py --dry-run --json` against the normalized file. |
| Consumer gate | Runs `navigation_sequence_summary_contract.py` against the saved dry-run summary and reports `contractConsumable`. |
| Offline mode | `--skip-dry-run` performs lint/normalization only and reads no live target memory. |
| Tool catalog | `navigation-waypoint-readiness` is canonical, safe-read-only, and in the recommended workflow. |

## Safety notes

- No live input, movement, `/reloadui`, screenshot key, Cheat Engine, x64dbg,
  provider writes, target memory writes, proof promotion, actor-chain promotion,
  or route-control promotion is performed.
- Default mode may perform read-only current-target memory reads through the
  existing dry-run route planner. Use `--skip-dry-run` for offline-only lint.
- Live multi-waypoint execution remains blocked until movement gates and proof
  freshness are explicitly opened.

## Validation

| Validation | Result |
|---|---|
| Unit test smoke | `python -m unittest scripts.test_navigation_waypoint_readiness` passed; `4` tests. |
| Compile | `python -m py_compile scripts\navigation_waypoint_readiness.py tools\riftreader_workflow\tool_catalog.py` passed. |
| Combined unit tests | `python -m unittest scripts.test_navigation_waypoint_readiness scripts.test_tool_catalog` passed; `9` tests. |
| Offline lint smoke | `scripts\riftreader-navigation-waypoint-readiness.cmd --waypoint-sequence-json scripts\navigation\smoke-test-waypoints.json --skip-dry-run --json` passed. |
| Full no-input readiness smoke | `scripts\riftreader-navigation-waypoint-readiness.cmd --waypoint-sequence-json scripts\navigation\smoke-test-waypoints.json --json` passed. |
| Full smoke verdict | `waypoint-readiness-consumable`; `dryRunVerdict=sequence-dry-run-plan-built`; `contractConsumable=true`; `movementSent=false`; `inputSent=false`. |
| Tool catalog compact | `scripts\riftreader-tool-catalog.cmd --compact-json` passed; `44` tools. |

## Current next action

Commit/push this waypoint readiness slice. The next infrastructure lane is a
consumer JSON-schema package for pose, dry-run sequence, contract report, and
waypoint readiness summaries.
