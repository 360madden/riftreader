# Navigation live-run request handoff — 2026-06-02 08:48 UTC

## Result

RiftReader now has a saved-JSON-only gated live-run request artifact. A
downstream consumer can take a passed navigation downstream package and record
an intended route execution request for later review without invoking movement,
route control, or live target access.

## What changed

| Area | Result |
|---|---|
| Helper | Added `scripts\navigation_live_run_request.py`. |
| Launcher | Added `scripts\riftreader-navigation-live-run-request.cmd`. |
| Output schema | Added `docs\schemas\navigation\navigation-live-run-request.schema.json` and registered it in `scripts\navigation_schema_validate.py`. |
| Tool catalog | Added canonical `navigation-live-run-request`; tool count is now `50`. |
| Docs | Updated `docs\workflows\navigation-route.md` and schema README. |

## Output contract

The request reports:

| Field | Purpose |
|---|---|
| `request.requestId` | Durable request identifier, generated when not provided. |
| `request.sourcePackageSummaryJson` | Downstream package summary used as the source. |
| `request.capabilitySnapshot` | Snapshot of package capabilities, with `canExecuteLiveNavigation=false`. |
| `request.executionGate` | Explicit queue/review state; execution authorization and route-runner invocation are always false. |
| `request.consumerInstruction` | Machine-readable warning that the artifact is not executable by itself. |
| `safety` | Saved-JSON-only safety flags: no input, movement, target-memory reads/writes, route control, debugger/CE, provider writes, or promotion. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\navigation_live_run_request.py scripts\test_navigation_live_run_request.py scripts\navigation_schema_validate.py scripts\test_tool_catalog.py tools\riftreader_workflow\tool_catalog.py` | Passed. |
| `python -m unittest scripts.test_navigation_live_run_request scripts.test_tool_catalog` | Passed: `Ran 9 tests in 0.981s`. |
| `scripts\riftreader-navigation-live-run-request.cmd --downstream-package-json scripts\captures\navigation-downstream-package-20260602-083424-354068\summary.json --json` | Passed with `requestAcceptedForReview=true`, `executionAuthorized=false`, `executionAttempted=false`, `routeRunnerInvoked=false`, `movementSent=false`, `inputSent=false`, and `targetMemoryBytesRead=false`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input C:\RIFT MODDING\RiftReader\scripts\captures\navigation-live-run-request-20260602-084748-577328\summary.json --json` | Passed with `schemaKey=navigation-live-run-request`, `validationErrorCount=0`. |

Latest request summary:
`C:\RIFT MODDING\RiftReader\scripts\captures\navigation-live-run-request-20260602-084748-577328\summary.json`.

Latest request schema-validation summary:
`C:\RIFT MODDING\RiftReader\scripts\captures\navigation-schema-validation-20260602-084806-052053\summary.json`.

## Safety

The request helper reads saved JSON only. It sends no input or movement,
performs no live target memory read/write, no `/reloadui`, no screenshot key, no
debugger/CE attach, no provider write, no proof/actor/facing/turn-rate
promotion, and no route control. It also blocks unsafe source packages: any
source package that reports input, movement, navigation control, target memory
writes, provider writes, debugger attach, or promotion cannot be accepted for
review.

## Practical navigation readiness

| Capability | Status |
|---|---|
| One-command downstream bundle | Working. |
| External route rendering | Working. |
| External refreshed pose contract | Working. |
| External route preview active-leg math | Working. |
| External dry-run contract consumption | Working. |
| External gated live-run request artifact | Working. |
| Live navigation execution | Still not authorized by this workflow; movement approval and live proof/input gates remain separate. |

## Current next action

Add a saved live-run request review gate that reads the request artifact,
confirms it is still schema-valid, checks that it came from a fresh enough
downstream package, and emits an explicit `approved=false` review summary unless
a separately authorized live execution token/gate is present. It should still
avoid invoking any route runner or sending input.
