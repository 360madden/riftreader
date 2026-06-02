# Navigation live-run command-plan handoff — 2026-06-02 09:19 UTC

## Result

RiftReader now has a saved-JSON-only live-run command-plan artifact. During the
current RIFT maintenance/world-entry outage, this advances practical automated
navigation infrastructure without requiring game access: the helper consumes a
passed live-run review and emits dry-run plus execution command templates while
still refusing to authorize or invoke route execution.

## What changed

| Area | Result |
|---|---|
| Helper | Added `scripts\navigation_live_run_command_plan.py`. |
| Launcher | Added `scripts\riftreader-navigation-live-run-command-plan.cmd`. |
| Output schema | Added `docs\schemas\navigation\navigation-live-run-command-plan.schema.json` and registered it in `scripts\navigation_schema_validate.py`. |
| Tool catalog | Added canonical `navigation-live-run-command-plan`; tool count is now `52`. |
| Docs | Updated `docs\workflows\navigation-route.md` and schema README. |

## Output contract

The command plan reports:

| Field | Purpose |
|---|---|
| `commandPlan.planId` | Durable plan identifier, generated when not provided. |
| `commandPlan.reviewSummaryJson` | Saved review artifact used as source. |
| `commandPlan.sourcePackageSummaryJson` | Saved downstream package referenced by the review. |
| `commandPlan.waypointReadinessSummaryJson` | Saved waypoint readiness artifact used to find normalized waypoints. |
| `commandPlan.dryRunCommandTemplate` | Command template for a later no-input dry-run. |
| `commandPlan.executionCommandTemplate` | Command template for a later explicitly approved live run. |
| `executionGate.commandPlanOnly` | Always true. |
| `executionGate.executionAuthorized` | Always false. |
| `executionGate.routeRunnerInvoked` | Always false. |
| `executionGate.blockersBeforeExecution` | Includes `game-maintenance-world-entry-unavailable` when `--game-maintenance` is supplied. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\navigation_live_run_command_plan.py scripts\test_navigation_live_run_command_plan.py scripts\navigation_schema_validate.py` | Passed. |
| `python -m unittest scripts.test_navigation_live_run_command_plan` | Passed: `Ran 4 tests in 0.557s`. |
| `scripts\riftreader-navigation-live-run-command-plan.cmd --live-run-review-json scripts\captures\navigation-live-run-review-20260602-090328-266990\summary.json --game-maintenance --json` | Passed with `requestedMode=continuous-route-run`, `commandPlanOnly=true`, `executionAuthorized=false`, `executionAttempted=false`, `routeRunnerInvoked=false`, `movementSent=false`, `inputSent=false`, and `targetMemoryBytesRead=false`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input C:\RIFT MODDING\RiftReader\scripts\captures\navigation-live-run-command-plan-20260602-091850-026491\summary.json --json` | Passed with `schemaKey=navigation-live-run-command-plan`, `validationErrorCount=0`. |

Latest command-plan summary:
`C:\RIFT MODDING\RiftReader\scripts\captures\navigation-live-run-command-plan-20260602-091850-026491\summary.json`.

Latest command-plan schema-validation summary:
`C:\RIFT MODDING\RiftReader\scripts\captures\navigation-schema-validation-20260602-091900-931591\summary.json`.

## Safety

The command-plan helper reads saved JSON only. It sends no input or movement,
performs no live target memory read/write, no `/reloadui`, no screenshot key, no
debugger/CE attach, no provider write, no proof/actor/facing/turn-rate
promotion, and no route control. The generated command templates are evidence
only; this helper does not execute them.

## Practical navigation readiness

| Capability | Status |
|---|---|
| One-command downstream bundle | Working. |
| External route rendering | Working. |
| External refreshed pose contract | Working. |
| External route preview active-leg math | Working. |
| External dry-run contract consumption | Working. |
| External gated live-run request artifact | Working. |
| External gated live-run request review | Working. |
| External non-executing live-run command plan | Working. |
| Live navigation execution | Blocked by world-entry maintenance and still requires explicit live approval when the game is back. |

## Current next action

While the game is down, add a downstream consumer replay fixture that validates
the full saved chain: package → request → review → command-plan. When RIFT is
available again, refresh target proof/current pose before considering any
bounded live dry-run or movement approval.
