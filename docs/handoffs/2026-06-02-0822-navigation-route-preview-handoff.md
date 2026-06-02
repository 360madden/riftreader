# Navigation route preview handoff — 2026-06-02 08:22 UTC

## Result

RiftReader now has a saved-artifact route preview workflow for downstream
map/UI consumers. It derives the active leg and remaining route legs from the
latest consumer pose plus normalized waypoints without reading the live target or
sending input.

## What changed

| Area | Result |
|---|---|
| Helper | Added `scripts\navigation_route_preview.py`. |
| Launcher | Added `scripts\riftreader-navigation-route-preview.cmd`. |
| Output schema | Added `docs\schemas\navigation\navigation-route-preview.schema.json` and registered it in `scripts\navigation_schema_validate.py`. |
| Tool catalog | Added canonical `navigation-route-preview`; tool count is now `48`. |
| Docs | Updated `docs\workflows\navigation-route.md` and schema README. |

## Output contract

The preview reports:

| Field | Purpose |
|---|---|
| `route.activeLeg` | Current-pose to next-unreached waypoint. |
| `route.legs[]` | Remaining route legs, including waypoint-to-waypoint segments. |
| `planarDistance` / `distance3d` | Map/UI distance display and route sizing. |
| `bearingDegrees` | Direction from leg start to destination. |
| `initialYawDeltaDegrees` | Current yaw delta for the active leg only. |
| `suggestedInitialTurnDirection` | `aligned`, `left`, `right`, or `arrived`; still not live authorization. |
| `arrivalRadius` | Per-waypoint arrival boundary used for route-complete decisions. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\navigation_route_preview.py scripts\test_navigation_route_preview.py scripts\navigation_schema_validate.py scripts\test_tool_catalog.py tools\riftreader_workflow\tool_catalog.py` | Passed. |
| `python -m unittest scripts.test_navigation_route_preview scripts.test_navigation_schema_validate scripts.test_tool_catalog` | Passed: `Ran 15 tests in 1.020s OK`. |
| `scripts\riftreader-tool-catalog.cmd --compact-json` | Passed with `total=48`, `exists=48`, `blockers=[]`. |
| `scripts\riftreader-navigation-consumer-refresh.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` | Passed with `canQueueGatedLiveRunRequest=true`, `canExecuteLiveNavigation=false`, `movementSent=false`, `inputSent=false`. |
| `scripts\riftreader-navigation-route-preview.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --json` | Passed render preview; default 5s freshness window correctly warned stale after `13.259351s`. |
| `scripts\riftreader-navigation-route-preview.cmd --waypoint-readiness-json scripts\captures\navigation-waypoint-readiness-20260602-071111-256714\summary.json --max-consumer-state-age-seconds 60 --json` | Passed queue-ready preview with `activeLegPlanarDistance=273.80771899466805`, `activeLegBearingDegrees=52.256314250788364`, `activeLegInitialYawDeltaDegrees=50.49110968572896`, `canQueueGatedLiveRunRequest=true`, `canExecuteLiveNavigation=false`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input scripts\captures\navigation-route-preview-20260602-082123-882214\summary.json --json` | Passed with `schemaKey=navigation-route-preview`, `validationErrorCount=0`. |

## Safety

The route preview reads saved JSON only. It sends no input or movement, performs
no target memory read/write, no `/reloadui`, no screenshot key, no debugger/CE
attach, no provider write, no proof/actor/facing/turn-rate promotion, and no
route control. Live execution remains explicitly gated even when the preview can
queue a gated live-run request.

## Practical navigation readiness

| Capability | Status |
|---|---|
| External route rendering | Working. |
| External route preview active-leg math | Working. |
| External per-leg distance/bearing/yaw-delta display | Working. |
| External dry-run contract consumption | Working. |
| External gated live-run queue decision | Working when pose freshness budget is satisfied. |
| Live navigation execution | Still not authorized by this workflow; movement approval and live proof gates remain separate. |

## Current next action

Add a one-command downstream package helper that runs consumer refresh, route
preview, schema validation, and consumer demo as a single safe workflow so
external projects can fetch one bundle without racing the 5-second pose
freshness window.
