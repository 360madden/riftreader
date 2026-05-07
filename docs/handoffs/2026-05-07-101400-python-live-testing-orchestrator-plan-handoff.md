# ✅ Handoff: Python live-testing orchestrator plan

_Last updated: May 7, 2026 10:45 EDT / 14:45 UTC._

## TL;DR

We identified that Codex-driven live testing is now bottlenecked by **Codex thinking/input lag between proof refresh, dry-run, input, and post-readback**. The new intended method is a **Python profile-driven live-test orchestrator** that runs a full bounded experiment locally, then gives Codex a compact result artifact to review.

The repo now has a durable plan at:

```text
C:\RIFT MODDING\RiftReader\docs\live-testing-python-orchestrator-plan.md
```

Resume update: the Python orchestrator MVP has now been implemented in the working tree. It has been validated with non-live profile/unit/compile checks only. No new live input was run after this handoff update.

## Current live-testing truth at handoff time

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Latest live target | `rift_x64` PID `47560`, HWND `0x2122E` |
| Current proof pointer status | `valid-after-resume-gated-wrapper-forward-smoke` |
| Pointer last updated | `2026-05-07T13:49:35.8512343Z` |
| Latest coordinate | `X=7437.97802734375`, `Y=885.2205810546875`, `Z=3049.539794921875` at `2026-05-07T13:49:35.6276265Z` |
| Latest wrapper summary | `C:\RIFT MODDING\RiftReader\scripts\captures\gated-forward-smoke-currentpid-47560-summary-20260507-134922.json` |
| Latest wrapper planar delta | `0.3253012361509452` |
| Cheat Engine | Not used; still forbidden unless explicitly reauthorized. |
| SavedVariables live truth | Not used; still forbidden as live truth. |

## Progress completed in this conversation

| Area | Result |
|---|---|
| Live proof continuation | Resumed from `docs\handoffs\2026-05-07-072508-gated-wrapper-forward-smoke-handoff.md`; refreshed no-CE proof; wrapper `-DryRun` passed; one wrapper-mediated `W` 250 ms pulse passed. |
| Current truth docs | Updated `docs\recovery\current-truth.md` and `docs\recovery\current-proof-anchor-readback.json` to the resumed wrapper pulse truth. |
| Language/tooling policy | Updated `agents.md` and `docs\assistant-operating-policy.md` to require Python for workflow/helper-app logic, `.cmd` only for dumb launchers, and PowerShell only as legacy leaf adapters. |
| New live-testing plan | Created `docs\live-testing-python-orchestrator-plan.md`. |
| Handoff | This file captures the current progress, implemented MVP surface, and remaining validation gates. |
| Python orchestrator MVP | Added `scripts\live_test.py`, `scripts\rift_live_test\*.py`, `configs\live-test-profiles.json`, `scripts\test_live_test_orchestrator.py`, and dumb `cmd\live-*.cmd` launchers. |
| Safety hardening after review | Added fail-closed retry protection so a live-input profile is not retried after any movement was attempted/sent, and added unit coverage for live-flag, target-mismatch, and refresh-cap gates. |

## New live-testing method to implement

### Core decision

Codex should not act as the real-time controller between live-test steps.

Use this split from now on:

| Layer | Tool | Purpose |
|---|---|---|
| Convenience launchers | `.cmd` | Dumb launchers only: `cd` to repo, call Python, forward `%*`. |
| Workflow/live-test controller | Python | State machine, profiles, JSON parsing, subprocess calls, proof-age timing, summaries, fail-closed labels. |
| Existing proof/input scripts | `.ps1` leaves initially | Temporary adapters called by Python until each brittle leaf is ported. |
| Low-level memory reader | C#/.NET | Keep existing memory/process readback engine. |
| Codex | Planner/reviewer | Choose profile, launch one bounded run, inspect summary, decide next experiment. |

### Practical safety stance

This is **not maximum safety by minimum tiny steps**. That approach is slowing development.

Use **hard boundary invariants** plus larger automated closed-loop experiments:

| Keep hard | Relax for speed |
|---|---|
| Exact PID/HWND target. | Do not ask Codex between proof, dry-run, input, and postcheck. |
| `--live` required for input profiles. | Auto-refresh proof once if stale or age budget is low. |
| No CE unless explicitly reauthorized. | Allow short multi-pulse series profiles after base profiles pass. |
| No SavedVariables as live truth. | Screenshots optional by profile. |
| Profile caps on hold/pulse count. | Failed postcheck stops and reports partial result instead of requiring manual panic. |
| Post-readback after input. | Stronger presets can be enabled once the lower profile is proven. |

## Planned module layout

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

## MVP implementation status

The first Python controller slice now exists and calls current proven `.ps1` leaves. It does not rewrite all leaves first.

Implemented entry points:

| Path | Purpose |
|---|---|
| `scripts\live_test.py` | Main Python profile runner. |
| `scripts\rift_live_test\commands.py` | Subprocess/JSON command adapter using argument lists. |
| `scripts\rift_live_test\profiles.py` | Profile loading, merge, path resolution, and live-input cap validation. |
| `scripts\rift_live_test\runner.py` | MVP state machine: target check, proof refresh, dry-run, gated wrapper, summaries. |
| `scripts\rift_live_test\target.py` | Exact PID/HWND/process-name verification. |
| `scripts\rift_live_test\reports.py` | `run-summary.json` and `run-summary.md` writing. |
| `configs\live-test-profiles.json` | `ProofOnly`, `RecoverAfterPulse`, `Forward250`, `ForwardSeries3x250`. |
| `cmd\live-*.cmd` | Dumb launchers that only call Python and forward `%*`. |

First live command target remains:

```powershell
python .\scripts\live_test.py --profile Forward250 --pid 47560 --hwnd 0x2122E --live
```

Expected internal chain:

1. Verify exact target.
2. Capture fresh API/reference coordinate.
3. Capture RiftScan proof pose.
4. Promote proof anchor.
5. Run dry-run gate.
6. Auto-refresh once if stale/low budget.
7. Send one exact-target `W` 250 ms pulse.
8. Run post-readback.
9. Emit `run-summary.json` and `run-summary.md`.

## Initial profiles

| Profile | Input | Why |
|---|---:|---|
| `ProofOnly` | No | Refresh/prove current anchor without input. |
| `Forward250` | Yes | Current proven wrapper pulse, now automated end-to-end. |
| `RecoverAfterPulse` | No | Rebuild proof after movement without more input. |
| `ForwardSeries3x250` | Yes | First speed multiplier: repeated closed-loop pulse series without Codex delay. |

Add turn/facing profiles only after forward automation is stable.

## Artifact standard

Each Python live-test run should write:

```text
scripts/captures/live-test-<Profile>-YYYYMMDD-HHMMSS/
  run-manifest.json
  profile-effective.json
  run-summary.json
  run-summary.md
  child-outputs/
  recorder/
  screenshots/
```

Codex should inspect `run-summary.json` / `run-summary.md` first and only dig into child outputs when debugging.

## Normalized statuses to implement

| Status | Meaning |
|---|---|
| `passed` | Input/proof/readback succeeded. |
| `passed-proof-only` | No input; proof valid. |
| `blocked-target-mismatch` | PID/HWND wrong or stale. |
| `blocked-live-flag-required` | Input profile requested but `--live` missing. |
| `blocked-proof-expired` | Proof stale and refresh failed/disabled. |
| `blocked-low-age-budget` | Not enough proof time remains. |
| `blocked-dry-run` | Dry-run gate failed. |
| `input-failed` | Input backend failed. |
| `post-readback-failed` | Input attempted but post proof failed. |
| `partial-series-stopped` | Some series steps passed, later gate failed. |
| `failed-internal-error` | Python/controller bug or unexpected exception. |

## Current working tree at handoff

At this handoff update, these files are modified/untracked and not staged:

| File | Status |
|---|---|
| `agents.md` | Modified: new Python-first workflow/helper-app policy. |
| `docs\assistant-operating-policy.md` | Modified: new live-test automation language decision tree. |
| `docs\recovery\current-proof-anchor-readback.json` | Modified: latest resumed wrapper pulse truth. |
| `docs\recovery\current-truth.md` | Modified: latest resumed wrapper pulse truth. |
| `docs\live-testing-python-orchestrator-plan.md` | New: detailed plan for the new method. |
| `docs\handoffs\2026-05-07-101400-python-live-testing-orchestrator-plan-handoff.md` | New: this handoff. |
| `configs\live-test-profiles.json` | New: orchestrator profile config. |
| `cmd\live-proof-only.cmd` | New: dumb launcher for `ProofOnly`. |
| `cmd\live-forward-250.cmd` | New: dumb launcher for `Forward250`. |
| `cmd\live-forward-series.cmd` | New: dumb launcher for `ForwardSeries3x250`. |
| `cmd\live-recover-after-pulse.cmd` | New: dumb launcher for `RecoverAfterPulse`. |
| `scripts\live_test.py` | New: orchestrator CLI. |
| `scripts\rift_live_test\` | New: orchestrator package. |
| `scripts\test_live_test_orchestrator.py` | New: non-live unit tests. |

## Validation done

| Check | Result |
|---|---|
| `git diff --check` | Passed after writing this handoff. |
| `python -m json.tool docs\recovery\current-proof-anchor-readback.json` | Passed after writing this handoff. |
| `python scripts\live_test.py --list-profiles` | Passed; listed `Forward250`, `ForwardSeries3x250`, `ProofOnly`, `RecoverAfterPulse`. |
| `python scripts\live_test.py --validate-profiles` | Passed; 4 profiles valid. |
| `python scripts\test_live_test_orchestrator.py` | Passed; 6 tests. |
| `python -m compileall -q scripts\live_test.py scripts\rift_live_test scripts\test_live_test_orchestrator.py` | Passed. |
| Current-truth artifact path existence check | Passed; all absolute paths found in `docs\recovery\current-proof-anchor-readback.json` existed locally. |
| Live `ProofOnly` | Not run in this update. |
| Live `Forward250 --live` | Not run in this update; requires explicit current target/proof refresh and live input approval. |

## Exact resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read the newest handoff first: C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-07-101400-python-live-testing-orchestrator-plan-handoff.md. Then read C:\RIFT MODDING\RiftReader\docs\live-testing-python-orchestrator-plan.md. The Python live-test orchestrator MVP is implemented in scripts/live_test.py, scripts/rift_live_test, configs/live-test-profiles.json, and cmd/live-*.cmd. Continue with non-live review or run ProofOnly only after rechecking current PID/HWND; run Forward250 with --live only after current exact target/proof gates are refreshed and live input is explicitly approved. Do not use Cheat Engine or SavedVariables live truth.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit the policy, current-truth, plan, handoff, and orchestrator MVP together if desired. | Preserves the live proof and Python controller as one coherent milestone. |
| 2 | Recheck current live PID/HWND before any no-input proof run. | The documented `47560` / `0x2122E` target is session-bound. |
| 3 | Run `python .\scripts\live_test.py --profile ProofOnly --pid <PID> --hwnd <HWND>` next if live readback is approved. | Proves the controller can refresh/read proof without movement input. |
| 4 | Inspect the `run-summary.json` from `ProofOnly`. | Confirms artifact contract before live movement. |
| 5 | Run `Forward250` without `--live` and confirm `blocked-live-flag-required`. | Locks the explicit live-input boundary. |
| 6 | Run `Forward250 --live` only after exact target/proof refresh and approval. | Recreates the current proven one-pulse path without Codex delay. |
| 7 | Defer `ForwardSeries3x250` live testing until `Forward250` passes. | Multi-pulse movement has higher blast radius. |
| 8 | Add mocked child-command tests around `runner.py`. | Expands CI-safe confidence in fail-closed state mapping. |
| 9 | Implement true per-pulse series orchestration after the one-pulse path is proven. | The current series profile delegates `PulseCount=3` to the wrapper, not a richer Python per-pulse loop. |
| 10 | Add recorder/screenshot hooks only after the MVP live path works. | Avoids widening scope before the core controller is validated. |
