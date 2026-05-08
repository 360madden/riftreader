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
| `latestPointer` | Recommended | Whether this run is allowed to update the repo latest-run pointer and why. |
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
| `runDirectoryInsideRepo` | Whether the latest run directory is inside this repo tree. |
| `progressFileInsideRepo` | Whether the latest progress file is inside this repo tree. |
| `runSummaryFileInsideRepo` | Whether the latest summary file is inside this repo tree. |
| `generatedAtUtc` | Pointer write timestamp. |
| `finalSummaryWritten` | Whether final summary was written. |

By default, the runner does not update this repo-level pointer when
`outputRoot` resolves outside the repo tree. Such runs still write their own
`run-progress.json` and `run-summary.json`, but `latestPointer.updateAllowed`
is `false` with `skipReason=output_root_outside_repo` unless the profile
explicitly opts in with `updateLatestPointerForExternalOutputRoot=true`.

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
| `latestPointer` | Present only with `--latest`; contains pointer status, generated timestamp, pointer health, resolved progress path, resolved summary path state, and repo-local path flags. |
| `latestPointer.freshness` | Present only with `--latest`; compares pointer timestamp/status/health with the referenced progress artifact and warns on external artifact paths. |
| `strict` | Present only when `--fail-on-warning` is used. |
| `runGate` | Present only when `--require-ok-run` is used. |

### `latestPointer.freshness`

| Field | Meaning |
|---|---|
| `status` | `ok` when pointer/progress metadata agrees; `warning` when drift or disagreement is detected. |
| `pointerGeneratedAtUtc` | Timestamp from `latest-live-test-run.json`. |
| `progressUpdatedAtUtc` | Timestamp from the referenced `run-progress.json`. |
| `timestampGapSeconds` | Absolute timestamp gap when both timestamps parse. |
| `driftWarningSeconds` | Gap threshold used for warning. |
| `issues` | Drift, timestamp parse/missing, status mismatch, health-state mismatch, or external-artifact warnings. |

External-artifact warnings include:

| Issue | Meaning |
|---|---|
| `latest_pointer_run_directory_outside_repo` | The repo latest pointer targets a run directory outside the repo tree. |
| `latest_pointer_progress_file_outside_repo` | The repo latest pointer targets a progress file outside the repo tree. |

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

### `runGate`

`--require-ok-run` adds this object and exits nonzero when `runGate.ok=false`.

| Field | Meaning |
|---|---|
| `requireOkRun` | Always `true` when the gate is active. |
| `ok` | `true` only when inspect parsing/contract checks pass and `runHealth.ok=true`. |
| `issues` | Reasons the run did not satisfy the gate, such as `run_not_ok:state=blocked;status=blocked-target-mismatch`. |

Use this when a script needs the latest inspected run to have actually passed.
Do not rely on `--fail-on-warning` alone for that meaning; strict mode validates
warnings/freshness, while `--require-ok-run` validates run success.

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
