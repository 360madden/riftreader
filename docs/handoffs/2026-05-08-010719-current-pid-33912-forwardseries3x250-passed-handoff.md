# Handoff: Current PID 33912 ForwardSeries3x250 passed live

Generated: May 8, 2026 01:07 EDT / 05:07 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
HEAD at resume start: `0402eb1 Harden live proof resume handoff`

## TL;DR

Current live target `rift_x64` PID `33912`, HWND `0xE0DB2` is now movement-grade for the current session. The resumed handoff path completed: no-input `ProofOnly` passed, bounded `Forward250 --live` passed, and `ForwardSeries3x250 --live` passed all 3 proof-gated pulses.

Further movement should still re-bind exact PID/HWND and run a fresh proof/preflight because proof anchors are age-gated.

## Latest target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `33912` |
| HWND | `0xE0DB2` |
| Exact bind | `find_game_window(processId=33912, windowHandle="0xE0DB2")` succeeded and target was foreground |
| Safety | no CE; no SavedVariables live truth; exact target required |

## Completed resume actions

| Step | Command / Action | Result |
|---|---|---|
| 1 | Read newest handoff `docs\handoffs\2026-05-08-005330-post-refreshbaseline-proofonly-needed-handoff.md` | Required next step was `ProofOnly` |
| 2 | `python scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui` | `passed-proof-only`; `movementSent=false` |
| 3 | Focus/capture exact Rift window through `rift_game` MCP | focused/captured PID `33912`, HWND `0xE0DB2` |
| 4 | `python scripts\live_test.py --profile Forward250 --pid 33912 --hwnd 0xE0DB2 --live --no-gui` | `passed`; `movementSent=true`; planar delta `0.326128836893223m` |
| 5 | Visual frame-change check after `Forward250` | changed `20.5548%` vs pre-input screenshot |
| 6 | Focus/capture exact Rift window again | focused/captured PID `33912`, HWND `0xE0DB2` |
| 7 | `python scripts\live_test.py --profile ForwardSeries3x250 --pid 33912 --hwnd 0xE0DB2 --live --no-gui` | `passed`; `3/3` pulses; series planar delta `0.9811914219956779m` |
| 8 | Visual frame-change check after series | changed `29.0871%` vs pre-series screenshot |

## Key artifacts

| Artifact | Path |
|---|---|
| ProofOnly run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-050153\run-summary.json` |
| Forward250 run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260508-050245\run-summary.json` |
| ForwardSeries3x250 run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260508-050351\run-summary.json` |
| ForwardSeries3x250 progress | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260508-050351\run-progress.json` |
| Latest runtime pointer | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-live-test-run.json` |
| Current proof pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| Current truth doc | `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` |

## Movement result details

| Metric | Forward250 | ForwardSeries3x250 |
|---|---:|---:|
| Status | `passed` | `passed` |
| Movement sent | `true` | `true` |
| Completed pulses | `1/1` | `3/3` |
| Auto refresh attempts | `0` | `1` |
| Final X | `7436.28759765625` | `7436.48828125` |
| Final Y | `885.2191772460938` | `885.2191772460938` |
| Final Z | `3060.85595703125` | `3059.8955078125` |
| Planar delta | `0.326128836893223m` | `0.9811914219956779m` |

## Updated durable docs

| File | Update |
|---|---|
| `docs\recovery\current-proof-anchor-readback.json` | Current PID `33912` status promoted to `movement-grade-current-session-forwardseries3x250-passed` |
| `docs\recovery\current-truth.md` | Top-level truth now says current-session movement proof passed on PID `33912`; prior blocked May 8 state is historical |
| This handoff | Resume checkpoint for the passing current-PID movement proof |

## Validation run in this resume slice

| Check | Result |
|---|---|
| Exact target bind | passed |
| `ProofOnly --no-gui` | passed |
| `Forward250 --live --no-gui` | passed |
| post-Forward250 visual change check | passed |
| `ForwardSeries3x250 --live --no-gui` | passed |
| post-series visual change check | passed |

## Immediate resume path from here

1. Re-bind exact target:

```text
find_game_window(processId=33912, windowHandle="0xE0DB2")
```

2. Run a fresh proof/preflight before any further input; proof is age-gated even though the latest series passed.
3. Next safest expansion is a tiny waypoint/navigation smoke using the current Python proof-gated path, not a blind longer forward run.
4. Do not use CE or SavedVariables as live truth.

## Ready-to-paste resume prompt

```text
Resume from newest handoff in C:\RIFT MODDING\RiftReader\docs\handoffs. Read docs\handoffs\2026-05-08-010719-current-pid-33912-forwardseries3x250-passed-handoff.md and docs\recovery\current-proof-anchor-readback.json first. Current target was PID 33912 / HWND 0xE0DB2. Do not use CE. ProofOnly, Forward250 --live, and ForwardSeries3x250 --live all passed with no SavedVariables live truth. Before any further movement, re-bind exact target and run fresh proof/preflight; next safe expansion is a tiny waypoint/navigation smoke.
```
