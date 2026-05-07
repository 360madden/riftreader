# Handoff - Dynamic promotion baseline pool validated

_Created: May 7, 2026 12:03 EDT / 16:03 UTC._

## TL;DR

The Python live-test orchestrator no longer relies only on one static
`promotionReferenceReadbackSummary`. It now records proof-pose summaries into a
Python-managed baseline pool and selects compatible same-target displaced
summaries before proof promotion.

Latest no-input validation passed:

| Fact | Value |
|---|---|
| Baseline capture | `RefreshBaseline` passed, no input sent |
| Baseline run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-RefreshBaseline-20260507-160159\run-summary.json` |
| Proof refresh | `ProofOnly` passed through dynamic baseline selection |
| Proof run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-160239\run-summary.json` |
| Selection diagnostics | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260507-160239\promotion-baseline-selection-attempt-1.json` |
| Baseline pool | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-promotion-baselines.json` |
| Selected summaries | `3` |
| Compatible displaced count | `2` |
| Latest proof pose count | `3` |
| No CE / SavedVariables | true |

## Main code changes

| File | Change |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\baselines.py` | New baseline pool/selection helpers. |
| `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\runner.py` | Records fresh proof-pose summaries, selects promotion baselines dynamically, adds `baseline-only` mode. |
| `C:\RIFT MODDING\RiftReader\configs\live-test-profiles.json` | Adds `RefreshBaseline`, `promotionBaselinePoolFile`, and `maxPromotionBaselineCandidates`. |
| `C:\RIFT MODDING\RiftReader\cmd\live-refresh-baseline.cmd` | Dumb `.cmd` launcher for baseline capture. |
| `C:\RIFT MODDING\RiftReader\scripts\test_live_test_orchestrator.py` | Adds baseline selection tests. |

## Validation completed

| Check | Result |
|---|---|
| `python -m py_compile ...` | Passed before live-read validation. |
| `python scripts\test_live_test_orchestrator.py` | Passed, 14 tests. |
| `python scripts\live_test.py --validate-profiles` | Passed, 5 profiles. |
| `RefreshBaseline` no-input live-read | Passed. |
| `ProofOnly` with dynamic baseline selection | Passed. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read newest handoff only:
C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-07-120330-python-baseline-pool-handoff.md

Continue agentically on the Python live-testing orchestrator. Current latest
movement truth: ForwardSeries3x250 passed live with 3/3 per-pulse gated W 250 ms
pulses. Current latest no-input proof truth: dynamic baseline pool RefreshBaseline
+ ProofOnly validation passed. Do not use Cheat Engine or SavedVariables as live
truth. Next best slice: partial-series resume/recovery or coordinate recorder.
```
