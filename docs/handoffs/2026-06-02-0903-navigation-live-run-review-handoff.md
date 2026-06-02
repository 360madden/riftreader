# Navigation live-run review handoff — 2026-06-02 09:03 UTC

## Result

RiftReader now has a saved-JSON-only live-run request review gate. A downstream
consumer can create a live-run request, then run a separate review artifact that
validates the request schema, validates the source downstream package schema,
checks request/package freshness budgets, and reports whether the request is
ready for a later explicit live-approval decision.

This is still non-executable infrastructure: it does not authorize movement,
does not invoke route runners, and does not read live target memory.

## What changed

| Area | Result |
|---|---|
| Helper | Added `scripts\navigation_live_run_review.py`. |
| Launcher | Added `scripts\riftreader-navigation-live-run-review.cmd`. |
| Output schema | Added `docs\schemas\navigation\navigation-live-run-review.schema.json` and registered it in `scripts\navigation_schema_validate.py`. |
| Tool catalog | Added canonical `navigation-live-run-review`; tool count is now `51`. |
| Docs | Updated `docs\workflows\navigation-route.md` and schema README. |

## Output contract

The review reports:

| Field | Purpose |
|---|---|
| `review.reviewId` | Durable review identifier, generated when not provided. |
| `review.requestId` | Request being reviewed. |
| `review.requestSummaryJson` | Saved request artifact path. |
| `review.sourcePackageSummaryJson` | Saved downstream package path referenced by the request. |
| `freshness.request` | Request age budget result. |
| `freshness.sourcePackage` | Source package age budget result. |
| `schemaValidations[]` | Inline schema validation result for request and source package. |
| `review.readyForSeparateLiveApproval` | True only when the saved request/package are schema-valid, fresh, and queue-ready. |
| `review.executionReviewApproved` | Always false in this helper. |
| `review.executionAuthorized` | Always false in this helper. |
| `review.routeRunnerInvoked` | Always false in this helper. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\navigation_live_run_review.py scripts\test_navigation_live_run_review.py scripts\navigation_live_run_request.py scripts\test_navigation_live_run_request.py scripts\navigation_schema_validate.py scripts\test_tool_catalog.py tools\riftreader_workflow\tool_catalog.py` | Passed. |
| `python -m unittest scripts.test_navigation_live_run_review scripts.test_navigation_live_run_request scripts.test_navigation_schema_validate scripts.test_tool_catalog` | Passed: `Ran 19 tests in 1.194s`. |
| `scripts\riftreader-navigation-live-run-review.cmd --live-run-request-json scripts\captures\navigation-live-run-request-20260602-084748-577328\summary.json --json` | Passed with `readyForSeparateLiveApproval=true`, `executionReviewApproved=false`, `executionAuthorized=false`, `executionAttempted=false`, `routeRunnerInvoked=false`, `movementSent=false`, `inputSent=false`, and `targetMemoryBytesRead=false`. |
| `scripts\riftreader-navigation-schema-validate.cmd --input C:\RIFT MODDING\RiftReader\scripts\captures\navigation-live-run-review-20260602-090328-266990\summary.json --json` | Passed with `schemaKey=navigation-live-run-review`, `validationErrorCount=0`. |
| `scripts\riftreader-tool-catalog.cmd --compact-json` | Passed with `total=51`, `exists=51`, `missing=0`, and canonical `navigation-live-run-review`. |

Latest review summary:
`C:\RIFT MODDING\RiftReader\scripts\captures\navigation-live-run-review-20260602-090328-266990\summary.json`.

Latest review schema-validation summary:
`C:\RIFT MODDING\RiftReader\scripts\captures\navigation-schema-validation-20260602-090340-960004\summary.json`.

## Safety

The review helper reads saved JSON only. It sends no input or movement, performs
no live target memory read/write, no `/reloadui`, no screenshot key, no
debugger/CE attach, no provider write, no proof/actor/facing/turn-rate
promotion, and no route control. It intentionally keeps
`executionReviewApproved=false`, `executionAuthorized=false`, and
`routeRunnerInvoked=false`.

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
| Live navigation execution | Still not authorized by this workflow; movement approval and live proof/input gates remain separate. |

## Current next action

Add a non-executing live-run command-plan artifact. It should consume the passed
review summary and produce the exact route-runner command, target preflight
requirements, and refusal reasons, while still leaving execution authorization,
route-runner invocation, input, and movement false.
