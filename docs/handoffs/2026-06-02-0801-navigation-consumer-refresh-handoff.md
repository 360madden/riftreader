# Navigation consumer refresh handoff — 2026-06-02 08:01 UTC

## Result

RiftReader now has a no-input consumer refresh workflow that regenerates the
consumer pose and reruns the downstream consumer demo in one command.

## What changed

| Area | Result |
|---|---|
| Helper | Added `scripts\navigation_consumer_refresh.py`. |
| Launcher | Added `scripts\riftreader-navigation-consumer-refresh.cmd`. |
| Output schema | Added `docs\schemas\navigation\navigation-consumer-refresh.schema.json` and registered it in `scripts\navigation_schema_validate.py`. |
| Tool catalog | Added canonical `navigation-consumer-refresh`; tool count is now `47`. |
| Docs | Updated `docs\workflows\navigation-route.md` and schema README. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\navigation_consumer_refresh.py scripts\test_navigation_consumer_refresh.py scripts\navigation_schema_validate.py scripts\test_tool_catalog.py tools\riftreader_workflow\tool_catalog.py` | Passed. |
| `python -m unittest scripts.test_navigation_consumer_refresh scripts.test_navigation_consumer_demo scripts.test_navigation_schema_validate scripts.test_tool_catalog` | Passed: `Ran 20 tests in 1.212s OK`. |
| `scripts\riftreader-tool-catalog.cmd --compact-json` | Passed with `total=47`, `exists=47`, `blockers=[]`. |
| `scripts\riftreader-navigation-consumer-refresh.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` | Passed with `canRenderRoute=true`, `canUseDryRunContract=true`, `canQueueGatedLiveRunRequest=true`, `canExecuteLiveNavigation=false`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input scripts\captures\navigation-consumer-refresh-20260602-080549-511814\summary.json --json` | Passed with `schemaKey=navigation-consumer-refresh`, `validationErrorCount=0`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input .riftreader-local\navigation-consumer-state\latest\summary.json --json` | Passed with `validationErrorCount=0`. |

## Safety

The refresh workflow may read live target memory through
`navigation_consumer_state.py`, but it sends no input or movement, performs no
`/reloadui`, screenshot key, debugger/CE attach, provider write, target memory
write, proof/actor/facing/turn-rate promotion, or route control. Live execution
is still explicitly gated even when the report says a downstream consumer can
queue a gated live-run request.

## Practical navigation readiness

| Capability | Status |
|---|---|
| External route rendering | Working. |
| External dry-run contract consumption | Working. |
| External gated live-run queue decision | Working after consumer refresh. |
| Live navigation execution | Still not authorized by this workflow; proof freshness and movement approval remain separate gates. |

## Current next action

Add a route preview artifact that derives per-leg distance, bearing, initial yaw
delta, and arrival radius from the refreshed consumer state plus normalized
waypoints. This gives downstream projects a map/UI-friendly preview before any
live run is requested.
