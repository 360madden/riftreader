# Handoff - Crash checkpoint after recorder validation

_Created: May 7, 2026 12:43 EDT / 16:43 UTC._

## Verdict

**LIVE WORK IS HALTED. Do not send more input or run more live memory/API scans until the operator restarts RIFT and explicitly resumes.**

The user reported that the game crashed after the recorder validation sequence. A read-only process check found no running `rift_x64` process.

## Exact live sequence before halt

| Step | Result |
|---|---|
| Target before live run | PID `47560`, HWND `0x2122E`, title `RIFT`. |
| `Forward250 --live` | Passed; one bounded 250 ms `W` pulse sent. |
| Recorder output | Produced 9 coordinate samples across dry-run, live-preflight, and live-post-readback. |
| `ForwardSeries3x250 --live` | Failed before any series movement; `MovementSent=false`, `MovementAttempted=false`. |
| User report | Game crashed after the failed series/reference-capture attempt. |
| Process check after report | No `rift_x64` process returned by `Get-Process rift_x64`. |

## Last successful live artifact

| Field | Value |
|---|---|
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-163612\run-summary.json` |
| Status | `passed` |
| Movement sent | `true` |
| Coordinate delta | planar `0.225977833842375`, `dX=0.0517578125`, `dY=0.0`, `dZ=-0.219970703125` |
| Final coordinate | `X=7437.5146484375`, `Y=885.2191772460938`, `Z=3055.517822265625` at `2026-05-07T16:38:15.4855135Z` |
| Coordinate samples | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-163612\recorder\coord-samples.ndjson` |
| Per-pulse recorder summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260507-163612\recorder\coord-pulse-001-summary.json` |

## Failed run artifact

| Field | Value |
|---|---|
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260507-163830\run-summary.json` |
| Status before offline hardening | `failed-internal-error` |
| Movement sent | `false` |
| Movement attempted | `false` |
| Failure state | `capture-reference` during proof refresh, before dry-run/input. |
| Child envelope | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260507-163830\child-outputs\001-capture-reference.json` |
| Child stderr | `No usable RRAPICOORD1 marker was found ... Required fields: status=pass, source=rift-api, savedVariablesUse=none, numeric x/y/z.` |
| Scan files | `rift-api-reference-scan-currentpid-47560-20260507-163831.json`, `...163853-attempt2.json`, `...163907-attempt3.json` under the failed run directory. |

## Crash/log evidence

| Check | Result |
|---|---|
| `Get-Process rift_x64` after report | No process found. |
| Application event log search | No clear current `rift_x64` application crash event found in the last 45 minutes. |
| WER events found | Older `LiveKernelEvent` entries at `2026-05-07 12:23 EDT`; not clearly tied to the `12:38-12:39 EDT` RIFT crash report. |
| Leftover helper processes | Some older `dotnet` and `pwsh` processes exist; do not assume they are safe to kill without operator confirmation. |

## Code changes made before/after crash

| Slice | Status |
|---|---|
| Coordinate recorder | Implemented and unit-validated. |
| One-pulse live recorder validation | Passed. |
| Reference-capture failure classification | Offline patch added after crash report: future marker-unavailable failures map to `blocked-reference-capture` instead of `failed-internal-error`. |

## Validation after offline hardening

| Command | Result |
|---|---|
| `python -m py_compile ...` | Passed. |
| `python scripts\test_live_test_orchestrator.py` | Passed, `18` tests. |
| `python scripts\live_test.py --validate-profiles` | Passed, `5` profiles. |
| `git diff --check` | Passed with CRLF warnings only. |

## Resume boundary

Do **not** retry `Forward250`, `ForwardSeries3x250`, `ProofOnly`, `RefreshBaseline`, or `capture-rift-api-reference-coordinate.ps1` until RIFT is restarted and the operator explicitly approves a new read-only proof reacquisition attempt.

Recommended restart sequence after operator confirmation:

1. Verify new `rift_x64` PID/HWND only.
2. Inspect whether the addon/API marker is expected to be live before scanning.
3. Run the smallest read-only proof/reference diagnostic first.
4. Do not send movement until the crash-adjacent reference-capture behavior is understood.

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read this handoff first:
C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-07-124304-crash-checkpoint-after-recorder-validation.md

The game crashed after recorder validation. Do not run live input or live memory/API scans until I restart RIFT and explicitly approve. Preserve no-CE and no-SavedVariables-live-truth boundaries. Start read-only: inspect current git diff, the Forward250 recorder pass at live-test-Forward250-20260507-163612, and the failed ForwardSeries reference capture at live-test-ForwardSeries3x250-20260507-163830. Future marker-unavailable failures should classify as blocked-reference-capture, not internal-error.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Stop all live testing until RIFT is manually restarted | Prevent repeated crash loops. |
| 2 | Preserve the failed series run directory | It contains the exact crash-adjacent reference scans. |
| 3 | Review `001-capture-reference.json` before any retry | It identifies the fail-closed marker issue. |
| 4 | Commit the recorder + blocked-reference-capture patch after review | Keeps the safe offline hardening durable. |
| 5 | After restart, verify PID/HWND only first | Confirms target identity without scanning or input. |
| 6 | Add a no-scan target-inspection profile | Gives a safer post-crash first check. |
| 7 | Add reference-capture diagnostics that summarize marker candidates compactly | Avoids huge raw scan inspection. |
| 8 | Gate series profiles behind a fresh marker-available precheck | Prevents jumping straight into multi-step runs when API marker is absent. |
| 9 | Consider lowering scan intensity or adding backoff after marker misses | Reduces crash-adjacent stress. |
| 10 | Only resume movement after one read-only proof path is clean post-restart | Keeps movement blocked until proof is stable again. |

