# Handoff: RefreshBaseline captured displaced PID 33912 pose; ProofOnly next

Generated: May 8, 2026 00:53 EDT / 04:53 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
HEAD: `5051df0 2026-05-07T19:56:55-04:00 Harden live-test HUD orchestration`

## TL;DR

Current live target is still `rift_x64` PID `33912`, HWND `0xE0DB2`. The user requested `RefreshBaseline` on PID `33912`; it passed with no input and captured a displaced current-session proof pose. The baseline pose is about `3.023m` from the prior blocked `ProofOnly` coordinate.

Movement is still **not allowed yet** because `ProofOnly` has not been rerun after this displaced baseline. The immediate next step is no-input `ProofOnly`; only if it passes should live movement proceed.

## Latest target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `33912` |
| HWND | `0xE0DB2` |
| Last exact bind | `find_game_window(processId=33912, windowHandle="0xE0DB2")` succeeded |
| Safety | no CE; no SavedVariables live truth; no movement sent in latest baseline run |

## Latest RefreshBaseline result

| Item | Value |
|---|---|
| Command | `python scripts\live_test.py --profile RefreshBaseline --pid 33912 --hwnd 0xE0DB2 --no-gui` |
| Status | `passed-baseline-captured` |
| Movement sent | `false` |
| Movement attempted | `false` |
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-RefreshBaseline-20260508-045224\run-summary.json` |
| Run progress | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-RefreshBaseline-20260508-045224\run-progress.json` |
| Readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-RefreshBaseline-20260508-045224\riftscan-proof-RefreshBaseline-attempt-1-20260508-045237\riftscan-riftreader-currentpid-33912-readback-wrapper-summary-20260508-005239.json` |
| Coordinate | `X=7438.64990234375`, `Y=885.2191772460938`, `Z=3049.527587890625` |
| Recorded at | `2026-05-08T04:52:43.0836487Z` |
| Readback evidence | `ReferenceMatchCount=1`, `StableDecodedCandidateCount=1`, `ReadbackTotalRegionReadFailures=0` |
| Displacement from prior blocked proof | `deltaX=0.61767578125`, `deltaZ=-2.959228515625`, planar `3.023m` |

## Prior no-input ProofOnly state

| Item | Value |
|---|---|
| Run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-044728\run-summary.json` |
| Status | `blocked-promotion-reference-mismatch` |
| Issue | `promotion_baseline_unavailable:compatibleDisplacedCount=0` |
| Movement sent | `false` |
| Current coordinate then | `X=7438.0322265625`, `Y=885.2191772460938`, `Z=3052.48681640625` |

This prior block is expected to be stale after the displaced baseline. Rerun `ProofOnly` before drawing any new movement conclusion.

## Current candidate source

| Field | Value |
|---|---|
| RiftScan match file | `C:\RIFT MODDING\Riftscan\reports\generated\currentpid-33912-reacquire-exact16m-20260508-042613-addon-coordinate-matches.json` |
| Candidate ID | `rift-addon-coordinate-candidate-000001` |
| Region/source | `region-012980`, `0x202FE9F0000 + 0x4E180` |
| Absolute address | `0x202FEA3E180` |
| Axis order | `xyz` |

## Files/docs updated for resume

| File | Purpose |
|---|---|
| `docs\recovery\current-proof-anchor-readback.json` | Current pointer now records latest displaced `RefreshBaseline` and says `ProofOnly` is next. |
| `docs\recovery\current-truth.md` | Top-level truth now says baseline advanced but movement is still blocked pending `ProofOnly`. |
| docs\recovery\historical\current-proof-anchor-readback-2026-05-07-pid47560-historical.json | Archive of the previous PID 47560 movement-grade pointer before replacing current pointer with PID 33912 truth. |
| This handoff | Resume checkpoint after successful baseline capture. |

## Validation already available in this worktree

| Check | Result |
|---|---|
| `python -m py_compile scripts\live_test.py scripts\live_test_gui.py scripts\rift_live_test\runner.py scripts\rift_live_test\gui.py scripts\test_live_test_orchestrator.py` | passed earlier in this slice |
| `python scripts\test_live_test_orchestrator.py` | passed earlier, `67` tests |
| `python scripts\live_test.py --validate-profiles` | passed earlier, `5` profiles |
| readback proof-gate/decode PowerShell regressions | passed earlier |
| safe no-input `RefreshBaseline` on PID `33912` / HWND `0xE0DB2` | passed now |

Run `git diff --check` before commit/push.

## Worktree status before this handoff was written

```text
 M configs/live-test-profiles.json
 M docs/live-testing-gui-operator-guide.md
 M docs/live-testing-progress-contract.md
 M docs/live-testing-python-orchestrator-plan.md
 M docs/recovery/current-proof-anchor-readback.json
 M docs/recovery/current-truth.md
 M docs/riftscan-riftreader-coordinate-candidate-workflow.md
 M scripts/invoke-riftscan-coordinate-readback.ps1
 M scripts/rift_live_test/gui.py
 M scripts/rift_live_test/runner.py
 M scripts/test-invoke-riftscan-coordinate-readback-proof-gate.ps1
 M scripts/test_live_test_orchestrator.py
?? cmd/live-gui-inspect-latest-ok.cmd
?? docs/handoffs/2026-05-08-004950-current-pid-33912-proof-blocked-handoff.md
```

## Immediate resume path

1. Re-bind exact game window:

```text
find_game_window(processId=33912, windowHandle="0xE0DB2")
```

2. Run no-input proof promotion:

```powershell
python scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui
```

3. If and only if `ProofOnly` passes, focus and capture the exact game window, then run bounded movement:

```powershell
python scripts\live_test.py --profile Forward250 --pid 33912 --hwnd 0xE0DB2 --live --no-gui
```

4. If `Forward250` passes, consider `ForwardSeries3x250 --live`.

## Ready-to-paste resume prompt

```text
Resume from newest handoff in C:\RIFT MODDING\RiftReader\docs\handoffs. Read docs\handoffs\2026-05-08-005330-post-refreshbaseline-proofonly-needed-handoff.md and docs\recovery\current-proof-anchor-readback.json first. Current target is PID 33912 / HWND 0xE0DB2. Do not use CE. RefreshBaseline has passed with a displaced pose; rerun ProofOnly next. Only if ProofOnly passes, focus/capture exact target and run Forward250 --live.
```

