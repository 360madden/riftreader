# Python Live-Testing Orchestrator Plan

_Last updated: May 7, 2026 12:38 EDT._

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
| `--live` required for any input profile | One explicit live boundary per run. |
| No Cheat Engine unless explicitly reauthorized | Current no-CE live boundary. |
| No SavedVariables as live truth | SavedVariables are post-save snapshots only. |
| Profile caps enforce max hold and pulse count | Prevent runaway input. |
| Post-readback is always attempted after input | Confirms proof survived the live action. |
| Every run writes a summary | No mystery live tests. |

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

## Proposed file layout

```text
scripts/
  live_test.py
  rift_live_test/
    __init__.py
    commands.py
    profiles.py
    runner.py
    target.py
    proof.py
    input.py
    recorder.py
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
