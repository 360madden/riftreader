# Live-Test Fast-Lane Triage

Created: 2026-05-17
Scope: Offline classification of the current RiftReader live-test blocker from
repo artifacts and safe status helpers.

## Verdict

The fast-lane triage helper answers: **what failed, which stage failed, what
artifact proves it, and what is the next safest action?** It does not send live
input, run movement, attach CE/x64dbg, write provider repos, stage, commit, or
push.

## Command

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-live-triage.cmd --json --write
```

Expected while RIFT is offline:

| Field | Value |
|---|---|
| `status` | `blocked` |
| `failedStage` | `live-target` |
| `blockerCategory` | `no-live-process` |
| Next action | Load RIFT into character/world, rediscover PID/HWND, rerun status triage. |

Expected when RIFT is online but the proof artifact still points at an old PID:

| Field | Value |
|---|---|
| `status` | `blocked` |
| `failedStage` | `live-target` |
| `blockerCategory` | `artifact-pid-stale` |
| Next action | Keep movement blocked, do not reuse the stale proof, and run safe current-target reacquisition/status refresh before ProofOnly or movement. |

## Output

The helper writes ignored artifacts under:

```text
.riftreader-local\live-test-triage\<timestamp>\
```

Files:

| File | Purpose |
|---|---|
| `live-test-triage-summary.json` | Machine-readable triage result. |
| `LIVE_TEST_TRIAGE.md` | Pasteable human summary. |
| `STATUS_PACKET.md` | Optional expanded status packet when `--include-status-packet` is passed. |

## Stage classification order

| Priority | Stage | Meaning |
|---:|---|---|
| 1 | `status-packet` | The status packet itself failed. |
| 2 | `live-target` | No live target, stale artifact PID, or missing artifact PID. |
| 3 | `proof-target-drift` | Current proof pointer belongs to a stale target epoch. |
| 4 | `movement-gate` | Movement gate is closed. |
| 5 | `proof-validation` | Latest proof validation is blocked or failed. |
| 6 | `proofonly` | Latest ProofOnly is blocked or failed. |
| 7 | recovery stage phase | Latest blocked recovery-profile stage. |
| 8 | `unknown-blocker` | Generic blocker remains. |

## Safety

This helper is read-only except for `.riftreader-local` reports. It preserves
the current stale-proof boundary: old PID/HWND/address artifacts are historical
only until fresh current-PID recovery and same-target `ProofOnly` pass.
