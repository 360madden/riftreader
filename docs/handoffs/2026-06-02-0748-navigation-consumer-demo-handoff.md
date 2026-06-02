# Navigation consumer demo handoff — 2026-06-02 07:48 UTC

## Result

RiftReader now has a saved-artifact-only downstream consumer demo report. It
combines consumer pose, normalized waypoints, route sequence dry-run, sequence
contract report, and schema checks into one practical decision for external
projects.

## What changed

| Area | Result |
|---|---|
| Helper | Added `scripts\navigation_consumer_demo.py`. |
| Launcher | Added `scripts\riftreader-navigation-consumer-demo.cmd`. |
| Output schema | Added `docs\schemas\navigation\navigation-consumer-demo.schema.json` and registered it in `scripts\navigation_schema_validate.py`. |
| Consumer-state schema repair | Widened `target.moduleBaseCheck`, `target.processStartCheck`, and `target.hwndCheck` to accept real object-shaped check payloads. |
| Tool catalog | Added canonical `navigation-consumer-demo`; tool count is now `46`. |
| Docs | Updated `docs\workflows\navigation-route.md` and schema README. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\navigation_consumer_demo.py scripts\test_navigation_consumer_demo.py scripts\navigation_schema_validate.py scripts\test_navigation_schema_validate.py scripts\test_tool_catalog.py tools\riftreader_workflow\tool_catalog.py` | Passed. |
| `python -m unittest scripts.test_navigation_consumer_demo scripts.test_navigation_schema_validate scripts.test_tool_catalog` | Passed: `Ran 16 tests in 1.557s OK`. |
| `scripts\riftreader-navigation-consumer-demo.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` | Passed with `canRenderRoute=true`, `canUseDryRunContract=true`, `canQueueGatedLiveRunRequest=false`, `canExecuteLiveNavigation=false`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input scripts\captures\navigation-consumer-demo-20260602-074903-247285\summary.json --json` | Passed with `schemaKey=navigation-consumer-demo`, `validationErrorCount=0`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input .riftreader-local\navigation-consumer-state\latest\summary.json --json` | Passed after schema repair with `validationErrorCount=0`. |
| `scripts\riftreader-tool-catalog.cmd --compact-json` | Passed with `total=46`, `exists=46`, `blockers=[]`. |
| `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` | Passed with `safeValidationCommandCount=5`, `blockers=[]`. |

## Practical navigation readiness

| Capability | Status |
|---|---|
| External route rendering | Working: demo reports `canRenderRoute=true`. |
| External dry-run contract consumption | Working: demo reports `canUseDryRunContract=true`. |
| External gated live-run queue decision | Working but currently false because consumer pose is stale. |
| Live navigation execution | Still not authorized by this report; live movement remains gated by proof freshness and explicit approval. |

## Current next action

Add an artifact freshness/refresh command that regenerates the consumer-state
pose and then reruns the consumer demo in one safe workflow. Keep it split from
live movement: the refresh may read target memory, but it must still send no
input and must not authorize route execution.
