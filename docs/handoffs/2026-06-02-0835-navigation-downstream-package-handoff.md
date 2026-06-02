# Navigation downstream package handoff — 2026-06-02 08:35 UTC

## Result

RiftReader now has a one-command downstream navigation package workflow. It
refreshes consumer pose, reruns the downstream consumer demo, builds the route
preview, and validates all package artifacts so another local project can fetch
one durable machine-readable bundle.

## What changed

| Area | Result |
|---|---|
| Helper | Added `scripts\navigation_downstream_package.py`. |
| Launcher | Added `scripts\riftreader-navigation-downstream-package.cmd`. |
| Output schema | Added `docs\schemas\navigation\navigation-downstream-package.schema.json` and registered it in `scripts\navigation_schema_validate.py`. |
| Tool catalog | Added canonical `navigation-downstream-package`; tool count is now `49`. |
| Docs | Updated `docs\workflows\navigation-route.md` and schema README. |

## Output contract

The package reports:

| Field | Purpose |
|---|---|
| `consumerRefreshSummaryJson` | Full refresh workflow summary. |
| `consumerDemoSummaryJson` | Downstream consumer readiness decision over saved artifacts. |
| `consumerStateSummaryJson` | Refreshed current pose contract. |
| `routePreviewSummaryJson` | Active-leg/remaining-leg route preview. |
| `schemaValidations[]` | Saved schema validation result for each package artifact. |
| `capabilities` | Single render/dry-run/preview/live-request decision for downstream consumers. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\navigation_downstream_package.py scripts\test_navigation_downstream_package.py scripts\navigation_route_preview.py scripts\navigation_schema_validate.py scripts\test_tool_catalog.py tools\riftreader_workflow\tool_catalog.py` | Passed. |
| `python -m unittest scripts.test_navigation_downstream_package scripts.test_navigation_route_preview scripts.test_navigation_consumer_refresh scripts.test_navigation_consumer_demo scripts.test_navigation_schema_validate scripts.test_tool_catalog` | Passed. |
| `scripts\riftreader-tool-catalog.cmd --compact-json` | Passed with `total=49`, `exists=49`, `blockers=[]`. |
| `scripts\riftreader-navigation-downstream-package.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` | Passed with `canRenderRoute=true`, `canUseDryRunContract=true`, `canRenderRoutePreview=true`, `canQueueGatedLiveRunRequest=true`, `canExecuteLiveNavigation=false`, `movementSent=false`, `inputSent=false`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input scripts\captures\navigation-downstream-package-20260602-083424-354068\summary.json --json` | Passed with `schemaKey=navigation-downstream-package`, `validationErrorCount=0`. |

Latest package summary:
`C:\RIFT MODDING\RiftReader\scripts\captures\navigation-downstream-package-20260602-083424-354068\summary.json`.

## Safety

The package may read live target memory through the consumer refresh step, but it
sends no input or movement, performs no target memory write, no `/reloadui`, no
screenshot key, no debugger/CE attach, no provider write, no proof/actor/facing
/turn-rate promotion, and no route control. Live execution remains explicitly
gated even when `canQueueGatedLiveRunRequest=true`.

## Practical navigation readiness

| Capability | Status |
|---|---|
| One-command downstream bundle | Working. |
| External route rendering | Working. |
| External refreshed pose contract | Working. |
| External route preview active-leg math | Working. |
| External dry-run contract consumption | Working. |
| External gated live-run queue decision | Working when the package passes. |
| Live navigation execution | Still not authorized by this workflow; movement approval and live proof gates remain separate. |

## Current next action

Add a gated live-run request schema and saved request artifact so downstream
consumers can express an intended route execution request without invoking live
movement. The actual route runner should continue to require explicit live
approval before execution.
