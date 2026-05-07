# Handoff - Python-owned ForwardSeries3x250 live validation

_Created: May 7, 2026 10:57 EDT / 14:57 UTC._

## TL;DR

`ForwardSeries3x250` is now a Python-owned per-pulse loop and passed live.
The orchestrator sent three separate exact-target `W` 250 ms pulses through the
existing gated wrapper, with a dry-run before each pulse and post-readback after
each pulse. Pulse 3 correctly hit low proof-age budget, auto-refreshed proof,
retried dry-run, then passed live.

## Latest result

| Fact | Value |
|---|---|
| Command | `python scripts\live_test.py --profile ForwardSeries3x250 --pid 47560 --hwnd 0x2122E --live` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260507-145404\run-summary.json` |
| Status | `passed` |
| Completed pulses | `3` / `3` |
| Auto proof refreshes | `1` |
| Series delta | planar `0.9534727619043354`, `dX=0.22412109375`, `dY=0.0`, `dZ=-0.9267578125` |
| Final coordinate | `X=7436.6025390625`, `Y=885.2205810546875`, `Z=3056.416259765625` at `2026-05-07T14:55:56.3626433Z` |
| No CE / SavedVariables | `NoCheatEngine=true`, `SavedVariablesUsedAsLiveTruth=false` |

## Files changed in this slice

| File | Change |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\runner.py` | Added Python per-pulse series loop, series pulse summaries, aggregate series delta, refresh sequencing. |
| `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\reports.py` | Added markdown summary table for series pulses. |
| `C:\RIFT MODDING\RiftReader\scripts\test_live_test_orchestrator.py` | Added tests for one-wrapper-call-per-pulse and partial series stop. |
| `C:\RIFT MODDING\RiftReader\docs\live-testing-python-orchestrator-plan.md` | Documented series live validation. |
| `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` | Promoted latest series truth. |
| `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` | Promoted latest series pointer. |

## Validation completed

| Check | Result |
|---|---|
| `python -m py_compile ...` | Passed before live series. |
| `python scripts\test_live_test_orchestrator.py` | Passed, 12 tests. |
| `python scripts\live_test.py --validate-profiles` | Passed, 4 profiles. |
| `ForwardSeries3x250` without `--live` | Correctly blocked with `blocked-live-flag-required`, `MovementSent=false`. |
| `ForwardSeries3x250 --live` | Passed, 3/3 pulses. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read newest handoff only:
C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-07-105700-python-series-live-test-handoff.md

Continue agentically on the Python live-testing orchestrator. Current latest
truth: ForwardSeries3x250 passed live with 3/3 per-pulse gated W 250 ms pulses.
Do not use Cheat Engine or SavedVariables as live truth. Next best slice is a
Python baseline/bootstrap refresh profile so future runs are not tied to a
PID/HWND-specific promotion baseline artifact.
```
