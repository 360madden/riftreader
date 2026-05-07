# Live Testing Progress Contract

_Last updated: May 7, 2026 14:15 EDT._

## Scope

This document describes the JSON artifacts consumed by the read-only
orchestrator HUD and `--inspect-progress`. The contract is intentionally small:
it is for operator visibility, safety checks, and handoff review, not for GUI
control or live input.

## Progress artifact

File: `run-progress.json`

| Field | Required | Meaning |
|---|---:|---|
| `schemaVersion` | Yes | Must be `1`. |
| `mode` | Yes | Must be `rift-live-test-progress`. |
| `profileName` | Yes | Orchestrator profile name. |
| `status` | Yes | Current normalized orchestrator status. |
| `updatedAtUtc` | Yes | Last progress write timestamp. |
| `runDirectory` | Yes | Timestamped run folder. |
| `runProgressFile` | Yes | Path to this progress artifact. |
| `runSummaryFile` | Recommended | Final summary path. |
| `live` | Recommended | Whether the run was allowed to use live input. |
| `processId` | Recommended | Target process id. |
| `targetWindowHandle` | Recommended | Exact target HWND. |
| `movementSent` | Recommended | Whether input was successfully sent. |
| `movementAttempted` | Recommended | Whether input was attempted. |
| `issues` | Recommended | List of issue strings. |
| `states` | Recommended | State history list. |
| `latestChildCommand` | Optional | Current or most recent child command. |
| `runGates` | Recommended | Active safety gate settings. Missing is a warning for older artifacts. |
| `runHealth` | Recommended | Normalized health summary. Missing is a warning for older artifacts. |
| `noCheatEngine` | Yes | Must be `true`. |
| `savedVariablesUsedAsLiveTruth` | Yes | Must be `false`. |
| `finalSummaryWritten` | Recommended | Whether `run-summary.json` has been written. |

## `runHealth`

| Field | Meaning |
|---|---|
| `state` | One of `ok`, `running`, `warning`, `blocked`, `failed`, `stale`, or `unknown`. |
| `status` | Original run status. |
| `ok` | `true` only for successful terminal states. |
| `ageSeconds` | Age of the progress timestamp when inspected, if available. |
| `issueCount` | Count of issue strings. |
| `primaryIssue` | First issue string, if present. |
| `movementSent` | Whether input was sent. |
| `movementAttempted` | Whether input was attempted. |
| `finalSummaryWritten` | Whether final summary is present/written. |
| `latestChildStatus` | Latest child command lifecycle status when available. |
| `latestChildOk` | Latest child command success when available. |
| `noCheatEngine` | Safety flag, expected `true`. |
| `savedVariablesUsedAsLiveTruth` | Safety flag, expected `false`. |

## Latest pointer

File: `scripts\captures\latest-live-test-run.json`

| Field | Meaning |
|---|---|
| `runSummaryFile` | Latest final summary path. |
| `runProgressFile` | Latest progress artifact path. |
| `runDirectory` | Latest run directory. |
| `profileName` | Latest profile name. |
| `status` | Latest run status. |
| `runHealth` | Latest normalized run health. |
| `generatedAtUtc` | Pointer write timestamp. |
| `finalSummaryWritten` | Whether final summary was written. |

## Inspect contract result

`python scripts\live_test_gui.py --inspect-progress ...` returns compact JSON:

| Field | Meaning |
|---|---|
| `status` | Inspect result, e.g. `progress-valid`, `progress-unreadable`, or `progress-invalid`. |
| `ok` | `true` when parsing succeeded and no hard contract errors were found. |
| `runStatus` | Status from the progress artifact. |
| `updatedAtUtc` | Progress artifact update timestamp. |
| `runHealth` | Health computed from the progress artifact. |
| `contract.status` | `valid`, `warning`, or `invalid`. |
| `contract.issues` | Contract warnings/errors. |
| `runSummaryFileExists` | Whether the referenced final summary exists at inspect time. |
| `latestPointer` | Present only with `--latest`; contains pointer status, generated timestamp, pointer health, resolved progress path, and resolved summary path state. |
| `latestPointer.freshness` | Present only with `--latest`; compares pointer timestamp/status/health with the referenced progress artifact. |
| `strict` | Present only when `--fail-on-warning` is used. |

### `latestPointer.freshness`

| Field | Meaning |
|---|---|
| `status` | `ok` when pointer/progress metadata agrees; `warning` when drift or disagreement is detected. |
| `pointerGeneratedAtUtc` | Timestamp from `latest-live-test-run.json`. |
| `progressUpdatedAtUtc` | Timestamp from the referenced `run-progress.json`. |
| `timestampGapSeconds` | Absolute timestamp gap when both timestamps parse. |
| `driftWarningSeconds` | Gap threshold used for warning. |
| `issues` | Drift, timestamp parse/missing, status mismatch, or health-state mismatch warnings. |

### `strict`

`--fail-on-warning` adds this object and exits nonzero when `strict.ok=false`.

| Field | Meaning |
|---|---|
| `failOnWarning` | Always `true` when strict mode is active. |
| `ok` | `true` only when the artifact parsed, contract has no hard errors, and no strict warnings were found. |
| `warningCount` | Count of strict warnings. |
| `warnings` | Warning strings from contract warnings, stale/warning run health, or latest-pointer freshness warnings. |

Hard failures include unsupported schema/mode, missing required fields, invalid
safety flags, and invalid required field shapes. Missing newer metadata such as
`runHealth` or `runGates` is a warning for backward compatibility.

`--compact-json` changes only whitespace formatting to one-line JSON. It does
not change fields, validation, or exit codes.

`--summary` changes output to a short human-readable status block. It can be
combined with `--fail-on-warning`; exit behavior is unchanged. `--summary` and
`--compact-json` are mutually exclusive.

## Checked-in fixtures

| Fixture | Expected health |
|---|---|
| `scripts\rift_live_test\testdata\progress-running.json` | `running` normally; `stale` when inspected with an older timestamp threshold. |
| `scripts\rift_live_test\testdata\progress-passed.json` | `ok`. |
| `scripts\rift_live_test\testdata\progress-blocked-reference.json` | `blocked`. |
| `scripts\rift_live_test\testdata\latest-pointer.json` | Resolves to `progress-passed.json`. |
| `scripts\rift_live_test\testdata\latest-pointer-drift.json` | Resolves to `progress-running.json` and should report latest-pointer freshness warnings. |
