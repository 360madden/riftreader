# Handoff: Current PID 33912 proof gate blocked pending displaced pose

Generated: May 8, 2026 00:49 EDT / 04:49 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
HEAD: `5051df0` (`Harden live-test HUD orchestration`)

## TL;DR

The live RIFT window is back and exact-target verification works for `rift_x64` PID `33912`, HWND `0xE0DB2`. Current-PID coordinate readback is productive and stable, but live movement remains blocked by design because the current session only has same-position proof poses. `ProofOnly` correctly fails closed with `promotion_baseline_unavailable:compatibleDisplacedCount=0`.

No Codex-sent movement/input was sent in the current PID `33912` lane. The user has approved forward movement live testing now/future, but the project proof gate still requires a second displaced same-target pose before Codex sends movement.

## Current live target

| Field | Value |
|---|---|
| Process name | `rift_x64` |
| PID | `33912` |
| HWND | `0xE0DB2` |
| Window title | `RIFT` |
| Latest exact bind | `find_game_window(processId=33912, windowHandle="0xE0DB2")` succeeded |
| Latest client size | `639x354` |

Before any future input, re-run exact `find_game_window`, then `focus_game_window`, then `capture_game_window` per the Rift window control skill.

## Latest proof / movement state

| Item | Value |
|---|---|
| Latest runtime pointer | `C:\RIFT MODDING\RiftReader\scripts\captures\latest-live-test-run.json` |
| Latest run summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-044728\run-summary.json` |
| Latest run progress | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-044728\run-progress.json` |
| Latest status | `blocked-promotion-reference-mismatch` |
| Primary issue | `promotion_baseline_unavailable:compatibleDisplacedCount=0` |
| Movement sent | `false` |
| Movement attempted | `false` |
| Latest child command | `capture-proof-pose`, exit `0`, JSON status `captured` |
| Readback summary | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-044728\riftscan-proof-ProofOnly-attempt-1-20260508-044755\riftscan-riftreader-currentpid-33912-readback-wrapper-summary-20260508-004756.json` |
| Promotion selection | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-044728\promotion-baseline-selection.json` |
| Current coordinate | `X=7438.0322265625`, `Y=885.2191772460938`, `Z=3052.48681640625` at `2026-05-08T04:48:00.8122818Z` |
| Readback evidence | `ReferenceMatchCount=1`, `StableDecodedCandidateCount=1`, `ReadbackTotalRegionReadFailures=0` |
| Compatible displaced baselines | `0` |
| Candidate count in selection diagnostics | `12` |

## Current candidate source

| Field | Value |
|---|---|
| RiftScan root | `C:\RIFT MODDING\Riftscan` |
| Inventory | `C:\RIFT MODDING\Riftscan\reports\generated\currentpid-33912-inventory-20260508-042443.json` |
| Session | `C:\RIFT MODDING\Riftscan\sessions\currentpid-33912-reacquire-exact16m-20260508-042613` |
| Truth summary | `C:\RIFT MODDING\Riftscan\reports\generated\currentpid-33912-riftreader-api-truth-20260508-042613.json` |
| Match file | `C:\RIFT MODDING\Riftscan\reports\generated\currentpid-33912-reacquire-exact16m-20260508-042613-addon-coordinate-matches.json` |
| Candidate ID | `rift-addon-coordinate-candidate-000001` |
| Source region | `region-012980` |
| Base + offset | `0x202FE9F0000 + 0x4E180` |
| Absolute address | `0x202FEA3E180` |
| Axis order | `xyz` |
| Support | `3` samples, best max abs distance `0` |

## What changed in this slice

| File | Change |
|---|---|
| `scripts\invoke-riftscan-coordinate-readback.ps1` | Fixed StrictMode scalarization by normalizing decoded samples to an array before count checks. |
| `scripts\test-invoke-riftscan-coordinate-readback-proof-gate.ps1` | Added regression coverage for decoded-sample normalization. |
| `configs\live-test-profiles.json` | Changed default `scanContextBytes` from `4096` to `16384`; current May 8 session showed 4096 can miss usable `RRAPICOORD1` context. |
| `docs\riftscan-riftreader-coordinate-candidate-workflow.md` | Documented the 16384-byte context preference. |
| `scripts\rift_live_test\runner.py` | Preserves blocked proof-pose `summaryFile` and `currentCoordinate` in final summaries, and records explicit latest-pointer movement flags. |
| `scripts\test_live_test_orchestrator.py` | Added regression coverage for blocked proof summary observability and latest-pointer movement flags. |
| `docs\recovery\current-proof-anchor-readback.json` | Updated to current PID `33912`, latest candidate, latest blocked run, and manual-move requirement. |
| `docs\recovery\current-truth.md` | Updated top-level current-truth snapshot for current PID `33912`. |
| `scripts\rift_live_test\gui.py`, GUI docs, and `cmd\live-gui-inspect-latest-ok.cmd` | Existing uncommitted GUI/latest-pointer inspection hardening from the active worktree remains present. |

## Validation already run

| Validation | Result |
|---|---|
| `python -m py_compile scripts\live_test.py scripts\live_test_gui.py scripts\rift_live_test\runner.py scripts\rift_live_test\gui.py scripts\test_live_test_orchestrator.py` | passed |
| `python scripts\test_live_test_orchestrator.py` | passed, `67` tests |
| `python scripts\live_test.py --validate-profiles` | passed, `5` profiles |
| `pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\test-invoke-riftscan-coordinate-readback-proof-gate.ps1` | passed |
| `pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts\test-invoke-riftscan-coordinate-readback-decode.ps1` | passed |
| JSON parse of `docs\recovery\current-proof-anchor-readback.json` | passed |
| `git diff --check` | passed; CRLF warnings only |
| Safe no-input `ProofOnly` on PID `33912` / HWND `0xE0DB2` | ran; blocked by design; no input sent |

## Current worktree state at handoff

Modified/untracked files observed:

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
```

This handoff file itself will add another untracked/modified doc path after creation.

## Safety boundaries

- Do not use Cheat Engine, CE Lua, CE debugger attach, watchpoints, or `cheatengine-exec.ps1` unless the user explicitly reauthorizes CE in the current conversation after acknowledging crash risk.
- Do not use `ReaderBridgeExport.lua` / SavedVariables as live truth.
- Do not send Codex movement until current PID proof promotion passes and a fresh preflight is green.
- User approval for forward movement is recorded, but the proof gate is still authoritative.
- The old PID `47560` proof anchor / movement truth is historical only and invalid for current PID `33912`.

## Immediate resume path

1. Ask/confirm whether the user has manually moved the character at least about `1m` from the latest coordinate. If they say it is moved, proceed.
2. Re-bind exact live target with `find_game_window(processId=33912, windowHandle="0xE0DB2")`.
3. Run no-input displaced baseline capture:

```powershell
python scripts\live_test.py --profile RefreshBaseline --pid 33912 --hwnd 0xE0DB2 --no-gui
```

4. Run no-input proof promotion:

```powershell
python scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui
```

5. Only if `ProofOnly` passes, focus/capture the window and run a bounded forward pulse:

```powershell
python scripts\live_test.py --profile Forward250 --pid 33912 --hwnd 0xE0DB2 --live --no-gui
```

6. If `Forward250` passes, consider `ForwardSeries3x250 --live` for repeated movement confirmation.

## Ready-to-paste resume prompt

```text
Resume from newest handoff in C:\RIFT MODDING\RiftReader\docs\handoffs. Use current PID 33912 / HWND 0xE0DB2. Do not use CE. Read docs\handoffs\2026-05-08-004950-current-pid-33912-proof-blocked-handoff.md and docs\recovery\current-proof-anchor-readback.json first. If I have manually moved the character at least ~1m, run RefreshBaseline then ProofOnly. Only send live movement if ProofOnly passes and exact target/focus/capture are green.
```
