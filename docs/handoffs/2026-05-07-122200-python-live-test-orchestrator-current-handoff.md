# Handoff - Python live-test orchestrator current state

_Created: May 7, 2026 12:22 EDT / 16:22 UTC._

## TL;DR

The Python live-test orchestrator work is committed and the working tree was
clean before this handoff file was created.

Latest committed state:

| Commit | Message |
|---|---|
| `ffb5ff7` | `Add live test progress checkpoints` |
| `9c7dfdd` | `Add Python live-test orchestrator` |
| `f3a4344` | `Add gated forward smoke proof workflow` |

Current live-test architecture:

| Layer | Current rule |
|---|---|
| `.cmd` | Dumb launchers only. |
| Python | Workflow/controller/state-machine owner. |
| `.ps1` | Existing proven leaf adapters only. |
| .NET | Existing low-level memory/readback engine. |
| CE / SavedVariables | Not used for live truth. |

## Latest movement truth

| Fact | Value |
|---|---|
| Profile | `ForwardSeries3x250 --live` |
| Status | `passed` |
| Target | PID `47560`, HWND `0x2122E` |
| Pulses | `3` / `3` |
| Movement sent | `true` |
| Auto proof refreshes | `1` |
| Series planar delta | `0.9534727619043354` |
| Series delta | `dX=0.22412109375`, `dY=0.0`, `dZ=-0.9267578125` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260507-145404\run-summary.json` |

## Latest no-input proof truth

| Fact | Value |
|---|---|
| Profile | `ProofOnly` |
| Status | `passed-proof-only` |
| Movement sent | `false` |
| Current coordinate | `X=7437.462890625`, `Y=885.2191772460938`, `Z=3055.73779296875` at `2026-05-07T16:18:16.0931490Z` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-161726\run-summary.json` |
| Run progress | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-161726\run-progress.json` |
| Latest pointer | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-live-test-run.json` |
| Final summary written | `true` |

## What is implemented

| Capability | Status |
|---|---|
| Profile-driven Python CLI | Implemented: `scripts\live_test.py`. |
| Exact PID/HWND verification | Implemented in Python before proof/input. |
| `--live` hard boundary | Implemented; input profiles cannot bypass it. |
| Proof refresh and promotion | Implemented via Python orchestration over existing leaf scripts. |
| Dynamic promotion baseline pool | Implemented: `scripts\rift_live_test\baselines.py`, profile `RefreshBaseline`. |
| Python-owned per-pulse series | Implemented and live-validated for `ForwardSeries3x250`. |
| Interruption progress checkpoint | Implemented: per-run `run-progress.json` plus latest pointer. |
| Handoffs/current truth | Updated through this handoff. |

## Validation already completed

| Check | Result |
|---|---|
| `python -m py_compile ...` | Passed after progress-checkpoint slice. |
| `python scripts\test_live_test_orchestrator.py` | Passed, `16` tests. |
| `python scripts\live_test.py --validate-profiles` | Passed, `5` profiles. |
| `python scripts\live_test.py --profile ProofOnly --pid 47560 --hwnd 0x2122E` | Passed, no input. |
| `python -m json.tool docs\recovery\current-proof-anchor-readback.json` | Passed. |
| `git diff --check` | Passed before `ffb5ff7` commit. |
| Git status before this handoff | Clean. |

## Important operational notes

- If a live test is interrupted, inspect:
  1. `C:\RIFT MODDING\RiftReader\scripts\captures\latest-live-test-run.json`
  2. Its `runProgressFile`
  3. If `finalSummaryWritten=false`, use `states` and `seriesPulses` in `run-progress.json`.
- Do not rerun live input blindly just because Codex was interrupted.
- Future live input should still use exact PID/HWND and `--live`:
  - `python scripts\live_test.py --profile Forward250 --pid 47560 --hwnd 0x2122E --live`
  - `python scripts\live_test.py --profile ForwardSeries3x250 --pid 47560 --hwnd 0x2122E --live`
- For no-input proof refresh:
  - `python scripts\live_test.py --profile ProofOnly --pid 47560 --hwnd 0x2122E`
- For baseline-only capture:
  - `python scripts\live_test.py --profile RefreshBaseline --pid 47560 --hwnd 0x2122E`

## Current recommended next slice

Best next implementation slice: **coordinate recorder around each pulse**.

Reason: the orchestrator already controls proof/dry-run/input/postcheck. A
small Python recorder that samples current proof coordinates before/during/after
pulses would give stronger evidence per live run without requiring Codex to make
real-time decisions.

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read newest handoff only:
C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-07-122200-python-live-test-orchestrator-current-handoff.md

Continue agentically. Current committed tips: ffb5ff7 Add live test progress
checkpoints, 9c7dfdd Add Python live-test orchestrator. Working tree was clean
before this handoff file was created. Do not use Cheat Engine or SavedVariables
as live truth. Keep .cmd wrappers dumb and Python as workflow owner. Next best
slice: add a Python coordinate recorder around each pulse using existing proof
readback surfaces, then validate with no-input tests before any live input.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Add coordinate recorder around each pulse | Highest signal gain with low architecture risk. |
| 2 | Add `--inspect-latest` / `--show-latest` | Fast interruption diagnosis from latest pointer. |
| 3 | Add partial-series resume | Resume after interrupted/partial runs without starting over. |
| 4 | Add optional screenshots per profile | Useful visual evidence when needed. |
| 5 | Add `Forward500` profile | Stronger displacement once 250 ms path is stable. |
| 6 | Add `TurnLeft250` and `TurnRight250` profiles | Opens facing/turn validation. |
| 7 | Add run comparison utility | Compare proof refreshes, deltas, and failures across runs. |
| 8 | Improve stale target messaging | Faster recovery after client/window restart. |
| 9 | Port proof-promotion leaf to Python | Reduces remaining PowerShell brittleness. |
| 10 | Push commits when ready | Preserve validated work remotely. |
