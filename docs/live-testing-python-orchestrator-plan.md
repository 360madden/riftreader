# Python Live-Testing Orchestrator Plan

_Last updated: May 7, 2026 14:15 EDT._

## Verdict

Codex should no longer act as the real-time controller between live-test steps.
The next live-testing method should use a **Python profile-driven orchestrator**
that runs a complete bounded experiment locally, then gives Codex one compact
result to review.

This is not a maximum-safety/minimum-progress design. It is a practical speed
upgrade: keep hard live-input invariants, but move the timing-sensitive closed
loop into deterministic automation.

## Problem being solved

| Problem | Effect |
|---|---|
| Codex thinks between proof, dry-run, input, and postcheck | Proof anchors age out and live windows stall. |
| Manual micro-steps are too conservative | Development velocity slows even when the path is already proof-gated. |
| PowerShell orchestration is brittle | Array binding, JSON parsing, date/time handling, and multi-step state are easy to break. |
| Ad hoc commands create uneven evidence | Each run produces different artifacts and requires manual interpretation. |
| New movement tests risk custom-script sprawl | Every new test type should not require a new workflow brain. |

## Core operating model

| Layer | Tool | Responsibility |
|---|---|---|
| User launcher | `.cmd` | Convenience only: change to repo, call Python, pass `%*`. |
| Workflow controller | Python | Profiles, state machine, subprocess calls, JSON parsing, proof-age budget, summaries, fail-closed labels. |
| Existing proof/input commands | Current `.ps1` leaves initially | Temporary adapters called by Python until ported one by one. |
| Memory/process reader | Existing C#/.NET | Low-level readback and process-memory engine. |
| Codex | Planner/reviewer | Choose profile, launch bounded run, inspect `run-summary.json` / `run-summary.md`, decide next experiment. |

## Hard invariants

These should remain non-negotiable even while improving speed:

| Invariant | Reason |
|---|---|
| Exact PID/HWND required | Prevent wrong-window input. |
| API-now vs memory-now coordinate freshness gate | Prevents cached artifact coordinates from being mistaken for current position. |
| `--live` required for any input profile | One explicit live boundary per run. |
| No Cheat Engine unless explicitly reauthorized | Current no-CE live boundary. |
| No SavedVariables as live truth | SavedVariables are post-save snapshots only. |
| Profile caps enforce max hold and pulse count | Prevent runaway input. |
| Post-readback is always attempted after input | Confirms proof survived the live action. |
| Every run writes a summary | No mystery live tests. |
| GUI is information-only | The HUD may read progress JSON, but it must not expose movement or orchestration controls. |

## Speed-focused relaxations

These are intentionally allowed to improve development velocity:

| Relaxation | Why it is acceptable |
|---|---|
| No Codex decision between proof refresh, dry-run, input, and postcheck | Removes the main lag and proof-expiry source. |
| Auto-refresh proof once on stale/low-age-budget conditions | Avoids predictable stalls. |
| Multi-pulse series profiles are allowed | Higher signal per bounded run. |
| Screenshots are profile-controlled, not mandatory for every run | Coordinate proof is enough for some iteration loops. |
| A failed post-readback stops the series and reports a partial result | Faster evidence without silent retry loops. |
| Stronger profiles can be enabled after base profiles pass | Avoids being stuck forever on tiny smoke tests. |

## Coordinate freshness workflow

The runner must not classify an artifact coordinate as current only because the
target PID/HWND still matches. PID/HWND/process-start is a targeting preflight;
the stale/non-stale coordinate gate is **API-now vs memory-now**:

| Step | Requirement |
|---|---|
| API sample | Read a fresh live API/runtime coordinate from a freshness-proven source such as ChromaLink `/api/v1/riftreader/world-state` or explicitly live ReaderBridge/in-game runtime telemetry. |
| Memory sample | Immediately read X/Y/Z from the current proof candidate/anchor in the same target process. |
| Delta check | Compare per-axis deltas and require them to be within the profile tolerance. Start with `maxAbsDelta <= 0.05` unless a profile declares a stricter or looser tolerance. |
| Failure behavior | If API is stale/missing, memory readback fails, or delta exceeds tolerance, report stale/mismatch, block movement, and keep old artifacts only as reacquisition seeds. |
| Evidence | Write API coord/timestamp/source, memory coord/timestamp/address/candidate, PID/HWND/process identity, per-axis deltas, tolerance, and verdict into the summary/progress artifacts. |

Do not use SavedVariables, `ReaderBridgeExport.lua`, `rift.cfg`, screenshots, or
old run summaries as the API side of this freshness gate.

## Proposed file layout

```text
scripts/
  live_test.py
  live_test_gui.py
  rift_live_test/
    __init__.py
    commands.py
    profiles.py
    runner.py
    target.py
    proof.py
    input.py
    recorder.py
    gui.py
    reports.py
    status.py

configs/
  live-test-profiles.json

cmd/
  live-proof-only.cmd
  live-forward-250.cmd
  live-forward-series.cmd
  live-recover-after-pulse.cmd
```

Keep the first version small. Do not build a plugin system until the profile
runner proves itself.

## Command examples

```powershell
python .\scripts\live_test.py --profile ProofOnly --pid 47560 --hwnd 0x2122E

python .\scripts\live_test.py --profile Forward250 --pid 47560 --hwnd 0x2122E --live

python .\scripts\live_test.py --profile ForwardSeries3x250 --pid 47560 --hwnd 0x2122E --live
```

A `.cmd` launcher should stay dumb:

```cmd
@echo off
cd /d "C:\RIFT MODDING\RiftReader"
python scripts\live_test.py --profile Forward250 %*
```

## MVP implementation entry points

The first Python-controller slice implements these entry points:

| Entry point | Purpose |
|---|---|
| `scripts\live_test.py` | Main Python profile runner. |
| `scripts\live_test_gui.py` | Read-only Tk HUD process for live progress display. |
| `cmd\live-gui-demo.cmd` | Dumb launcher for an offline HUD preview with generated demo progress. |
| `cmd\live-gui-latest.cmd` | Dumb launcher for opening the latest recorded run progress. |
| `cmd\live-gui-inspect-latest.cmd` | Dumb launcher for printing latest-run health without opening a window. |
| `cmd\live-gui-inspect-latest-ok.cmd` | Dumb launcher for latest-run strict inspect plus `--require-ok-run`. |
| `docs\live-testing-gui-operator-guide.md` | Short operator guide for HUD/inspect commands and post-crash order. |
| `docs\live-testing-progress-contract.md` | Progress/latest-pointer contract reference. |
| `scripts\rift_live_test\testdata\*.json` | Checked-in progress/latest-pointer fixtures for contract validation. |
| `configs\live-test-profiles.json` | Presets for `ProofOnly`, `RecoverAfterPulse`, `Forward250`, and `ForwardSeries3x250`. |
| `cmd\live-proof-only.cmd` | Dumb launcher for proof-only validation. |
| `cmd\live-forward-250.cmd` | Dumb launcher for the current one-pulse forward profile. |
| `cmd\live-forward-series.cmd` | Dumb launcher for the planned three-pulse forward series profile. |
| `cmd\live-recover-after-pulse.cmd` | Dumb launcher for no-input proof recovery. |

## MVP implementation note

As of the May 7 resume update, the MVP files above exist in the working tree
and pass unit/compile/profile validation plus proof-only and one-pulse live
validation. The current MVP deliberately
keeps proof refresh and input execution delegated to existing proven `.ps1`
leaves while Python owns profile loading, target verification, subprocess JSON
handling, fail-closed status mapping, run manifests, and compact summaries.

The first live Python-controller validation passed:

| Validation | Result |
|---|---|
| Safe no-live input boundary | `Forward250` without `--live` returned `blocked-live-flag-required`; `MovementSent=false`. |
| Proof-only controller path | `ProofOnly` passed against PID `47560`, HWND `0x2122E`; no input sent. |
| Live controller path | `Forward250 --live` passed against PID `47560`, HWND `0x2122E`; one exact-target `W` 250 ms pulse sent. |
| Latest live run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-144303\run-summary.json` |
| Latest wrapper summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-144303\gated-forward-smoke-currentpid-47560-summary-20260507-144325.json` |
| Latest movement delta | planar `0.30452861066430975`; `dX=0.04443359375`, `dY=0.0`, `dZ=-0.30126953125` |

Hardening added after review:

| Hardening | Why |
|---|---|
| Input profiles require `--live` unconditionally | Removes any config-level bypass. |
| `requireLiveFlagForInput=false` is rejected during profile load | Keeps the live boundary enforceable. |
| `proofAnchorFile` is passed into promotion, readback, and gated wrapper calls | Prevents promoting one anchor and validating/inputting against another. |
| `processName` is passed through leaf calls | Keeps CLI/profile overrides honest. |
| Promotion baseline target is checked before refresh | Fails clearly on stale PID/HWND baseline artifacts. |
| Input profiles enforce a minimum planar coordinate delta | Prevents `MovementSent=true` with zero coordinate movement from being reported as a passed live movement test. |
| Restart-stale artifacts are classified as historical evidence instead of thrown away | Old PID/HWND pointers and baselines stay visible as audit/reacquire hints, but cannot promote or gate movement until rescored against the current target. |
| Proof-pose capture reacquires reference before rejecting stale pointers | A restarted game now yields `blocked-target-drift` JSON with current API/reference data and preserved historical pointer hints, not an unstructured throw that loses context. |
| Current proof anchor wins over stale recovery pointer | If `telemetry-proof-coord-anchor.json` already matches the live PID/HWND, refresh uses its candidate seed instead of letting an older `docs/recovery/current-proof-anchor-readback.json` block the run. |
| Gated input defaults to exact-HWND window-message backend | Live evidence showed foreground `SendInput` returned success but produced zero coordinate delta; exact-window message input moved the character and remains foreground-gated by the wrapper. |
| RiftScan milestone review infers the latest live-test target | The strategy gate no longer recommends stale `docs/recovery/current-proof-anchor-readback.json` PID/HWND by default after a successful live run; it binds to `latest-live-test-run.json`/`run-summary.json` unless an explicit target is supplied. |
| RiftScan validation accepts safe blocked reviews | A blocked milestone review can still validate the no-CE/no-write/no-movement boundary when the current target lacks a RiftScan candidate; this preserves the blocker instead of misrouting to old coordinates. |

Known limits before the next live expansion:

| Limit | Current handling |
|---|---|
| `ForwardSeries3x250` | Configured, but currently delegates `PulseCount=3` to the existing gated wrapper instead of a richer Python per-pulse loop. |
| `RecoverAfterPulse` | Shares the proof-only path for now. |
| `proof.py`, `input.py`, `recorder.py` | Placeholder modules for future extraction; the MVP keeps orchestration in `runner.py`. |
| Live validation | `ProofOnly` and `Forward250 --live` passed for current PID/HWND; future use still requires current PID/HWND/proof refresh. |

Validation commands:

```powershell
python scripts\live_test.py --validate-profiles
python scripts\test_live_test_orchestrator.py
python scripts\live_test.py --profile Forward250 --pid 47560 --hwnd 0x2122E
python scripts\live_test.py --profile ProofOnly --pid 47560 --hwnd 0x2122E
python scripts\live_test.py --profile Forward250 --pid 47560 --hwnd 0x2122E --live
```


## May 7 update - Python-owned `ForwardSeries3x250` passed live

The series profile now runs as a Python-owned per-pulse loop instead of a single
wrapper call with `PulseCount=3`. Each pulse performs its own wrapper dry-run and
single-pulse live wrapper call. The run stops with `partial-series-stopped` if a
later pulse fails after earlier movement.

| Validation | Result |
|---|---|
| Command | `python scripts\live_test.py --profile ForwardSeries3x250 --pid 47560 --hwnd 0x2122E --live` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260507-145404\run-summary.json` |
| Status | `passed` |
| Completed pulses | `3` / `3` |
| Auto proof refreshes | `1`; pulse 3 dry-run requested refresh and retry passed |
| Series delta | planar `0.9534727619043354`, `dX=0.22412109375`, `dY=0.0`, `dZ=-0.9267578125` |
| Final coordinate | `X=7436.6025390625`, `Y=885.2205810546875`, `Z=3056.416259765625` at `2026-05-07T14:55:56.3626433Z` |
| Safety boundary | no CE; no SavedVariables live truth; exact PID/HWND; `--live` required |


## May 7 update - dynamic promotion baseline pool passed no-input validation

The orchestrator no longer depends on only one static
`promotionReferenceReadbackSummary`. Each proof-pose capture is recorded into a
Python-managed baseline pool, and proof promotion selects compatible same-target
summaries with enough reference displacement before adding the fresh summary.

| Validation | Result |
|---|---|
| Baseline capture command | `python scripts\live_test.py --profile RefreshBaseline --pid 47560 --hwnd 0x2122E` |
| Baseline capture summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-RefreshBaseline-20260507-160159\run-summary.json` |
| Proof validation command | `python scripts\live_test.py --profile ProofOnly --pid 47560 --hwnd 0x2122E` |
| Proof validation summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-160239\run-summary.json` |
| Baseline pool | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-promotion-baselines.json` |
| Selection diagnostics | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-160239\promotion-baseline-selection-attempt-1.json` |
| Selection result | `selected`, compatible displaced count `2` |
| Selected summaries | `3` summaries promoted into the current proof anchor |
| Latest proof anchor pose count | `3` |
| Latest proof max reference displacement | `2.4753908943841862` |


## May 7 update - interruption-safe run progress checkpoints passed

The runner now writes `run-progress.json` incrementally after state and series
pulse changes, and `scripts\captures\latest-live-test-run.json` points to both
the progress file and final summary. This makes interrupted live tests diagnosable
without blindly rerunning input.

| Validation | Result |
|---|---|
| Proof command | `python scripts\live_test.py --profile ProofOnly --pid 47560 --hwnd 0x2122E` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-161726\run-summary.json` |
| Run progress | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-161726\run-progress.json` |
| Latest pointer | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-live-test-run.json` |
| Final summary written | `true` |
| Movement sent | `false` |
| Current coordinate | `X=7437.462890625`, `Y=885.2191772460938`, `Z=3055.73779296875` |

## May 7 update - coordinate recorder implemented

The runner now honors profile `recording.coordSamples=true` by writing normalized
proof-readback coordinate samples around each pulse into
`recorder\coord-samples.ndjson`, plus per-pulse
`recorder\coord-pulse-###-summary.json` files. The recorder does not introduce a
new input path and does not use Cheat Engine or SavedVariables as live truth; it
extracts samples from the existing proof-anchor current-readback surfaces already
returned by the gated wrapper.

| Output | Purpose |
|---|---|
| `coordinateRecordings` in `run-summary.json` / `run-progress.json` | Fast per-pulse recording lookup. |
| `coordinateSamplesFile` | Single NDJSON stream for all recorded pulse samples. |
| `seriesPulses[].coordinateRecording` | Pulse-local sample count, phase counts, and recorded delta. |
| `run-summary.md` coordinate recording table | Human-readable evidence summary. |

## May 7 update - minimalist read-only GUI HUD implemented

The orchestrator can now launch a small Tk-based information HUD by default for
profile-driven runs. It watches `run-progress.json` and displays status lights,
labels, elapsed time, latest state/child command, current target, gate settings,
proof-age budget, safety flags, movement/coordinate info, recorder state, final
summary status, issues, and recent state history. It includes an `Options` menu
with a status-light legend, but all entries are informational/disabled for now:
no movement, retry, proof, scan, or stop controls are exposed through the GUI.

The progress and summary JSON now include a compact `runGates` object so the HUD
can show the active safety contract without parsing the effective profile:
profile mode, exact-target requirement, `--live` gate, proof/reference age caps,
post-readback age budget, auto-refresh usage, no-CE status, and the
SavedVariables live-truth prohibition.

The same polish pass tightened the orchestrator artifact path: JSON/markdown
artifacts are written through atomic replace, child command timeouts are captured
as child-result artifacts instead of escaping as unstructured internal errors,
and `latestChildCommand` now records duration, parse errors, and common JSON
status fields such as `Status` or `ProofValidationStatus`.

The HUD also supports `--latest`, which resolves
`scripts\captures\latest-live-test-run.json` and opens the referenced progress
file. Missing or malformed latest-run pointers fail cleanly with a compact JSON
error instead of a traceback. Demo mode supports
`--demo-scenario running|passed|blocked|blocked-reference|blocked-proof` so
success, stale/running, target mismatch, reference-capture failure, and
proof-expiry states can be previewed without RIFT. The live-info grid includes
run/progress identity rows, progress age, and stale-running markers so a stalled
run or unexpected artifact source is visually obvious without log inspection.
Issue lines are prefixed with `ERROR`, `WARN`, or `INFO` to make blockers easier
to scan while preserving the raw issue text.

The orchestrator now emits a compact `runHealth` object into progress, summary,
and latest-pointer artifacts. It normalizes health into `ok`, `running`,
`warning`, `blocked`, `failed`, or `stale` and carries issue count, primary
issue, movement flags, latest-child status, final-summary status, and safety
flags. The GUI CLI also supports `--inspect-progress` to print this health
summary headlessly for operator checks and automation smoke tests.

`--inspect-progress` now accepts either `--progress-file` or `--run-directory`
and validates a small progress contract in addition to parsing JSON. It checks
schema/mode, required identity and timestamp fields, required safety flags
(`noCheatEngine=true`, `savedVariablesUsedAsLiveTruth=false`), list/object field
shapes, final-summary path existence, and presence of the newer `runHealth` /
`runGates` metadata. Older artifacts missing `runHealth`/`runGates` are reported
as warnings; safety/schema violations fail the inspect command. Markdown
summaries include a **Run health** table so the same normalized state is visible
in handoff artifacts.

When `--latest` is combined with `--inspect-progress`, the headless output now
also includes a `latestPointer` object with pointer status, generated timestamp,
pointer health, and resolved progress/summary file existence. This keeps the
latest-run launcher useful after interrupted runs where pointer metadata and
progress metadata may differ. The nested `latestPointer.freshness` object warns
on timestamp drift, pointer/progress status mismatch, or pointer/progress
health-state mismatch before an operator reruns any live profile.
`--fail-on-warning` turns those warnings, contract warnings, and stale/warning
run health into a nonzero inspect exit while still printing the full JSON result.
`--compact-json` can be combined with strict mode to print the same inspect
payload as one-line JSON for scripts.
`--summary` prints the same inspect result as a short human-readable status
block for operator triage without changing exit behavior.
`--require-ok-run` is a separate opt-in gate for scripts that need the inspected
run itself to have passed; this prevents a valid blocked-run artifact from being
misread as movement-ready.
The runner also refuses to update the repo latest-run pointer from an external
`outputRoot` by default. External/temp runs remain inspectable by explicit path,
but they no longer silently replace repo-local latest truth unless a profile
sets `updateLatestPointerForExternalOutputRoot=true`.

Checked-in fixtures now cover running, passed, blocked reference-capture,
normal latest-pointer, and drifted latest-pointer artifacts. The unit suite
validates them through the same inspection logic, including stale-health and
latest-pointer freshness behavior, so schema or safety-contract drift is caught
without needing a live game window.

| Field | Default |
|---|---|
| `showGui` | `true` in profile defaults. |
| `guiPollMilliseconds` | `500`. |
| `guiAlwaysOnTop` | `false` initially to reduce focus-steal risk. |
| CLI override | `--no-gui` disables the HUD for a single invocation. |
| Offline preview | `python scripts\live_test_gui.py --demo` or `cmd\live-gui-demo.cmd`. |
| Latest run preview | `python scripts\live_test_gui.py --latest` or `cmd\live-gui-latest.cmd`. |
| Latest run inspect | `python scripts\live_test_gui.py --latest --inspect-progress` or `cmd\live-gui-inspect-latest.cmd`. |
| Strict inspect gate | `python scripts\live_test_gui.py --latest --inspect-progress --fail-on-warning`. |
| Require latest run success | `python scripts\live_test_gui.py --latest --inspect-progress --fail-on-warning --require-ok-run` or `cmd\live-gui-inspect-latest-ok.cmd`. |
| Compact strict inspect | `python scripts\live_test_gui.py --latest --inspect-progress --fail-on-warning --compact-json`. |
| Human inspect summary | `python scripts\live_test_gui.py --latest --inspect-progress --summary`. |
| Headless demo artifact | `python scripts\live_test_gui.py --demo --write-demo-only`. |

## State machine

| State | Purpose | Failure behavior |
|---|---|---|
| `load-profile` | Load config and merge CLI overrides. | Abort. |
| `verify-target` | Confirm exact process and HWND. | Abort. |
| `capture-reference` | Capture fresh live API/memory reference. | Retry once if profile allows. |
| `capture-proof-pose` | Read RiftScan candidate against fresh reference. | Retry once if profile allows. |
| `promote-proof` | Promote current no-CE proof anchor. | Abort. |
| `dry-run-gate` | Run no-input movement gate. | Auto-refresh once if stale/low budget, otherwise abort. |
| `age-budget-check` | Confirm enough proof time remains for input and postcheck. | Auto-refresh once, then abort. |
| `pre-record` | Optional baseline coordinate/screenshot capture. | Warn or abort by profile. |
| `input-plan` | Validate pulse sequence against profile caps. | Abort. |
| `input-pulse` | Send configured bounded input. | Stop series if input fails. |
| `post-readback` | Validate proof after input. | Stop series if invalid. |
| `post-record` | Optional screenshot/coordinate tail. | Best effort. |
| `report` | Write result artifacts. | Always run. |

## Initial profiles

Implement profiles in this order:

| Profile | Input | Purpose | Priority |
|---|---:|---|---:|
| `ProofOnly` | No | Refresh/prove current anchor only. | 1 |
| `Forward250` | Yes | Current proven wrapper movement pulse. | 1 |
| `RecoverAfterPulse` | No | Rebuild proof after movement without input. | 2 |
| `ForwardSeries3x250` | Yes | Closed-loop repeated forward proof without Codex delay. | 2 |
| `Forward500` | Yes | Stronger displacement after `Forward250` is stable. | 3 |
| `TurnLeft250` | Yes | Begin facing/turn validation. | 4 |
| `TurnRight250` | Yes | Symmetric turn validation. | 4 |
| `StrafeLeft250` | Yes | Later lateral movement proof. | 5 |
| `StrafeRight250` | Yes | Later lateral movement proof. | 5 |
| `CustomKeySmoke` | Yes | Config-driven key/hold test without new code. | 6 |

## Profile config shape

```json
{
  "defaults": {
    "proofAnchorMaxAgeSeconds": 60,
    "minimumPostReadbackAgeBudgetSeconds": 20,
    "referenceMaxAgeSeconds": 180,
    "readbackSampleCount": 3,
    "readbackIntervalMilliseconds": 100,
    "autoRefreshProofOnExpired": true,
    "autoRefreshProofOnLowAgeBudget": true,
    "maxAutoRefreshAttempts": 1,
    "requireExactTarget": true,
    "requireLiveFlagForInput": true,
    "writeMarkdownSummary": true
  },
  "profiles": {
    "ProofOnly": {
      "mode": "proof-only",
      "input": null
    },
    "Forward250": {
      "mode": "live-input",
      "input": {
        "key": "w",
        "holdMilliseconds": 250,
        "pulseCount": 1,
        "interPulseDelayMilliseconds": 150
      },
      "recording": {
        "screenshots": false,
        "coordSamples": true,
        "preMilliseconds": 750,
        "postMilliseconds": 1250
      },
      "stopRules": {
        "stopOnPostReadbackFailure": true
      }
    },
    "ForwardSeries3x250": {
      "mode": "live-input-series",
      "input": {
        "key": "w",
        "holdMilliseconds": 250,
        "pulseCount": 3,
        "interPulseDelayMilliseconds": 300
      },
      "gates": {
        "dryRunBeforeSeries": true,
        "postReadbackAfterEachPulse": true,
        "refreshBetweenPulsesIfAgeBudgetLow": true
      }
    }
  }
}
```

## Artifact layout

Each run should write one timestamped folder:

```text
scripts/captures/live-test-Forward250-YYYYMMDD-HHMMSS/
  run-manifest.json
  profile-effective.json
  gui-start.json
  run-summary.json
  run-summary.md
  child-outputs/
    001-target-check.json
    002-reference.json
    003-proof-pose.json
    004-promote-proof.json
    005-dry-run.json
    006-live-input.json
    007-post-readback.json
  recorder/
    coord-samples.ndjson
  screenshots/
    before.png
    after.png
```

Codex should normally inspect only `run-summary.json` and `run-summary.md`.

## Normalized result labels

| Status | Meaning |
|---|---|
| `passed` | Input/proof/readback succeeded. |
| `passed-proof-only` | No input; proof valid. |
| `blocked-target-mismatch` | PID/HWND wrong or stale. |
| `blocked-target-drift` | Target exists, but cached proof pointer/anchor belongs to a prior PID/HWND; current API state was reacquired and movement stayed blocked until proof is rebuilt. |
| `blocked-live-flag-required` | Input profile requested but `--live` missing. |
| `blocked-reference-capture` | Fresh API/reference marker was unavailable; fail closed before proof/input. |
| `blocked-promotion-reference-mismatch` | Baseline promotion summary is from a different PID/HWND/process. |
| `blocked-proof-expired` | Proof stale and refresh failed/disabled. |
| `blocked-low-age-budget` | Not enough proof time remains. |
| `blocked-dry-run` | Dry-run gate failed. |
| `input-failed` | Input backend failed. |
| `post-readback-failed` | Input attempted but post proof failed. |
| `partial-series-stopped` | Some series steps passed, later gate failed. |
| `failed-internal-error` | Python/controller bug or unexpected exception. |

## Implementation milestones

### Milestone 1 - Python controller MVP

| Task | Output |
|---|---|
| Add `scripts/live_test.py` | Main CLI entry point. |
| Add `scripts/rift_live_test/commands.py` | `subprocess.run([...])`, JSON extraction, timeout handling. |
| Add `scripts/rift_live_test/profiles.py` | Load and validate `configs/live-test-profiles.json`. |
| Add `scripts/rift_live_test/runner.py` | Deterministic state machine. |
| Add `scripts/rift_live_test/reports.py` | `run-summary.json` and `run-summary.md`. |
| Add `configs/live-test-profiles.json` | Initial `ProofOnly`, `Forward250`, `RecoverAfterPulse`. |
| Validate `ProofOnly` | No live input. |
| Validate `Forward250 --live` | Confirms lag reduction. |

### Milestone 2 - Artifact quality

| Task | Why |
|---|---|
| Store child JSON outputs | Debuggable without log hunting. |
| Store effective profile | Reproducibility. |
| Add latest-run pointer | Fast resume/review. |
| Add markdown summary | Handoff readability. |

### Milestone 3 - Series profiles

| Task | Why |
|---|---|
| Add `ForwardSeries3x250` | Main speed multiplier. |
| Add post-readback after each pulse | Closed-loop confidence. |
| Auto-refresh on low age budget | Avoid proof expiry mid-series. |
| Stop on first failed gate | Bounded risk without manual delay. |

### Milestone 4 - Recorder and screenshots

| Task | Why |
|---|---|
| Add coordinate recorder around pulse | Higher-signal evidence than pre/post only. |
| Add optional screenshots | Visual proof when useful. |
| Add native RIFT screenshot backend | Uses the in-game `Take Screenshot` binding (`NUM PAD *`) when GDI/MCP/WGC capture is unreliable. |
| Forbid `Ctrl+P` screenshot path | That keybind is intentionally removed and must not be retried for screenshots. |
| Make recording profile-controlled | Avoid slowing every run. |

### Milestone 5 - Turn/facing profiles

| Profile | Purpose |
|---|---|
| `TurnLeft250` | Validate left-turn input and facing response. |
| `TurnRight250` | Validate right-turn input and facing response. |
| `TurnSeriesLeftRight` | Controlled alternating turn proof. |
| `ForwardThenTurn` | Movement plus facing interaction proof. |

### Milestone 6 - Gradual PowerShell leaf migration

Do not rewrite all `.ps1` scripts first. Port only after the Python controller is
stable.

| Candidate | Reason |
|---|---|
| JSON-heavy proof/reference helpers | Python handles JSON more reliably. |
| Promotion orchestration | Avoid PowerShell array-binding issues. |
| Summary/report generation | Python is cleaner and easier to test. |
| Low-level memory reader | Keep in .NET for now. |

## Implementation rules

- Use Python `subprocess.run([...])`, not shell command strings.
- Capture stdout and stderr separately.
- Extract JSON robustly from child output.
- Always write a partial summary on failure.
- Validate profile caps before any live input.
- Require `--live` for input profiles.
- Do not add a broad plugin system yet.
- Do not create one script per profile.
- Keep existing `.ps1` leaves as adapters until each is intentionally ported.
- For native in-game screenshots, use only `NUM PAD *`; `Ctrl+P` / `Control+P` is a forbidden screenshot chord and must fail closed before input.

## First recommended build target

The first useful command should be:

```powershell
python .\scripts\live_test.py --profile Forward250 --pid 47560 --hwnd 0x2122E --live
```

It should internally perform:

1. Verify target.
2. Capture reference.
3. Capture proof pose.
4. Promote proof anchor.
5. Run dry-run gate.
6. Auto-refresh once if stale or low age budget.
7. Send one `W` 250 ms pulse.
8. Run post-readback.
9. Emit `run-summary.json` and `run-summary.md`.

After this passes, add:

```powershell
python .\scripts\live_test.py --profile ForwardSeries3x250 --pid 47560 --hwnd 0x2122E --live
```

That is the first major development-speed multiplier.
