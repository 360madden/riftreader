# Handoff - Python live-testing orchestrator implemented and live-validated

_Created: May 7, 2026 10:44 EDT / 14:44 UTC._

## TL;DR

The live-testing lag problem has been addressed with a Python profile-driven
orchestrator. Codex no longer has to decide between proof refresh, dry-run,
input, and post-readback for the base smoke path. The controller performs the
bounded sequence locally and writes compact summaries.

Latest live result: **`Forward250 --live` passed** for `rift_x64` PID `47560`,
HWND `0x2122E`; one exact-target `W` 250 ms pulse was sent through the existing
gated wrapper; post-readback stayed valid.

## Key implementation files

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\live_test.py` | Main Python CLI entry point. |
| `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\runner.py` | Python state machine for target verify, proof refresh, dry-run, live input, summaries. |
| `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\profiles.py` | Profile loading, defaults merge, live-input cap validation. |
| `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\commands.py` | Subprocess execution and JSON extraction from child output. |
| `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\target.py` | Windows PID/HWND/process-name verification. |
| `C:\RIFT MODDING\RiftReader\configs\live-test-profiles.json` | Presets: `ProofOnly`, `RecoverAfterPulse`, `Forward250`, `ForwardSeries3x250`. |
| `C:\RIFT MODDING\RiftReader\cmd\live-forward-250.cmd` | Dumb launcher; calls Python only. |
| `C:\RIFT MODDING\RiftReader\docs\live-testing-python-orchestrator-plan.md` | Durable plan and current design rules. |

## Language/workflow policy now documented

| Policy | Location |
|---|---|
| `.cmd` files are convenience launchers only | `C:\RIFT MODDING\RiftReader\agents.md` |
| Python owns workflow/helper-app logic | `C:\RIFT MODDING\RiftReader\agents.md` and `docs\assistant-operating-policy.md` |
| PowerShell remains leaf-adapter/legacy only unless justified | `C:\RIFT MODDING\RiftReader\docs\assistant-operating-policy.md` |

## Validation completed

| Check | Result |
|---|---|
| Python compile | Passed: `python -m py_compile scripts\live_test.py scripts\test_live_test_orchestrator.py scripts\rift_live_test\*.py` |
| Unit tests | Passed: `python scripts\test_live_test_orchestrator.py` -> 10 tests OK |
| Profile validation | Passed: `python scripts\live_test.py --validate-profiles` -> 4 profiles valid |
| Profile listing | Passed: profiles are `Forward250`, `ForwardSeries3x250`, `ProofOnly`, `RecoverAfterPulse` |
| No-live input boundary | Passed: `Forward250` without `--live` blocked with `blocked-live-flag-required`, `MovementSent=false` |
| Proof-only run | Passed: `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-144210\run-summary.json` |
| Live run | Passed: `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-144303\run-summary.json` |
| Diff whitespace | `git diff --check` passed before the final doc update; rerun before commit. |

## Latest live evidence

| Fact | Value |
|---|---|
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-144303\run-summary.json` |
| Wrapper summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-144303\gated-forward-smoke-currentpid-47560-summary-20260507-144325.json` |
| Target | `rift_x64` PID `47560`, HWND `0x2122E` |
| Profile | `Forward250` with `--live=true` |
| Status | `passed` |
| Movement | `MovementAttempted=True`, `MovementSent=True` |
| Input | `W`, `250 ms`, `PulseCount=1` |
| Dry-run gate | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-144303\gated-forward-smoke-currentpid-47560-summary-20260507-144320.json` |
| Post-readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260507-104333.json` |
| Current coordinate | `X=7436.35498046875, Y=885.2205810546875, Z=3057.44140625` at `2026-05-07T14:43:38.4287423Z` |
| Delta | `dX=0.04443359375`, `dY=0.0`, `dZ=-0.30126953125`, planar `0.30452861066430975` |
| No CE / SavedVariables | `NoCheatEngine=true`, `SavedVariablesUsedAsLiveTruth=false` |

## Review hardening applied

A sidecar read-only review found real MVP weaknesses. They were patched before
this handoff:

| Finding | Fix |
|---|---|
| Config could theoretically disable the `--live` boundary | Runner now requires `--live` for all input profiles unconditionally; profile loader rejects `requireLiveFlagForInput=false`. |
| Custom `proofAnchorFile` could be promoted but not used by later gates | Python now passes `-ProofCoordAnchorFile` into readback and gated wrapper calls. |
| `processName` override was partial | Python now passes `-ProcessName` into reference, pose, promotion, readback, and gated wrapper calls. |
| PID-specific promotion baseline could fail unclearly after restart | Python now checks baseline `ProcessId`/`ProcessName`/`TargetWindowHandle` before proof refresh and returns `blocked-promotion-reference-mismatch`. |
| Child argv correctness had no tests | Unit tests now cover live-flag hard boundary, proof-anchor propagation, promotion argv, and baseline mismatch detection. |

## Current limits / next unfinished slices

| Limit | Practical next step |
|---|---|
| `ForwardSeries3x250` still delegates `PulseCount=3` to the existing wrapper | Implement richer Python per-pulse loop with post-readback after each pulse. |
| Recorder modules are placeholders | Extract coord sampling / screenshot recorder only after series loop is useful. |
| Promotion baseline is PID/HWND specific | Add a `RefreshBaseline` or `BootstrapBaseline` profile after the current run stabilizes. |
| Captures are ignored by git | Keep summaries referenced in docs; do not commit large capture folders unless intentionally preserving evidence. |

## Resume prompt for next session

```text
Resume in C:\RIFT MODDING\RiftReader. Read newest handoff only:
C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-07-104425-python-live-testing-orchestrator-implementation-handoff.md

Continue agentically on the Python live-testing orchestrator. Do not use Cheat
Engine or SavedVariables as live truth. Keep .cmd launchers dumb and keep
workflow/helper-app logic in Python. First run validation, then implement the
next smallest high-impact slice: Python-owned ForwardSeries3x250 per-pulse loop
with post-readback after each pulse and fail-closed partial summary.
```
