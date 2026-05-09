# Forward series refresh-budget handoff - 3x250 passed

Created: 2026-05-08 22:10:56 -0400
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

Live forward movement is working on the current target through the exact-HWND
`window-message` backend. A first `ForwardSeries3x250` run stopped safely after
2/3 pulses because the proof-anchor age budget was too low and the profile only
allowed one auto-refresh. The smallest fix was to raise only the
`ForwardSeries3x250` profile `maxAutoRefreshAttempts` to `3`.

After that config-only fix, `ForwardSeries3x250 --live` passed all three pulses.
No Cheat Engine was used, no SavedVariables were used as live truth, and all
movement stayed behind the proof/readback gates.

## What changed

| File | Change |
|---|---|
| `C:\RIFT MODDING\RiftReader\configs\live-test-profiles.json` | Added `"maxAutoRefreshAttempts": 3` to `ForwardSeries3x250` only. |
| `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` | Auto-updated earlier by successful same-target `ProofOnly`; dirty working-tree evidence. |
| This handoff | Captures the live movement milestone and root cause. |

## Live validation sequence

| Step | Result |
|---|---|
| Read-only window bind/capture | Bound PID `49504`, HWND `0x5121A`; screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-220019-127.png` |
| `ProofOnly --live --no-gui` | Passed; `movementSent=false`; run `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-015449\run-summary.json` |
| `Forward250 --live --no-gui` | Passed; movement `0.309514567172569m`; run `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-Forward250-20260509-020026\run-summary.json` |
| First `ForwardSeries3x250 --live --no-gui` | Partial stop after 2/3 pulses; total `0.6009107750213364m`; blocker `proof_anchor_remaining_age_budget_too_low:remainingSeconds=13.455;requiredSeconds=20` |
| Config fix validation | `python .\scripts\live_test.py --validate-profiles` passed; `python .\scripts\test_live_test_orchestrator.py` passed 75/75 |
| Second `ForwardSeries3x250 --live --no-gui` | Passed 3/3 pulses; run `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260509-020624\run-summary.json` |
| Post-run visual capture | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-221004-971.png` |
| Milestone review | `ready-for-read-only-proof`; wrote `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-021025.json` and `.md` |

## Latest passed `ForwardSeries3x250` evidence

| Fact | Value |
|---|---|
| Run directory | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260509-020624` |
| Status | `passed` |
| Completed pulses | `3/3` |
| Movement sent | `true` |
| Auto-refresh attempts used | `2` of `3` |
| Final coordinate | `X=7389.37158203125`, `Y=872.916259765625`, `Z=3050.9951171875` at `2026-05-09T02:09:57.2228666Z` |
| Total series planar movement | `1.0194439320789634m` |
| Pulse 1 planar movement | `0.31437805416982195m` |
| Pulse 2 planar movement | `0.31099031086145923m` |
| Pulse 3 planar movement | `0.39407601861960634m` |
| Safety | no CE; no SavedVariables live truth; exact PID/HWND; proof/readback gated; `window-message` backend |

## Current boundaries

| Area | Status |
|---|---|
| Forward movement | Working through proof-gated `Forward250` and `ForwardSeries3x250`. |
| Coordinate currentness | Still requires fresh API-now vs memory-now before treating a coordinate as current-now. Stored coordinates are snapshots. |
| Auto-turn | Still blocked; no promoted turn backend. |
| Route/waypoint smoke | Not yet rerun in this slice after the series refresh-budget fix. |
| RiftScan | Read-only provider boundary preserved; no RiftScan writes. |
| Git | Local `main` is ahead of `origin/main` and has uncommitted changes. |

## Resume prompt

```text
Resume from newest RiftReader handoff:
C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-08-221056-forwardseries-refresh-budget-passed-handoff.md

Current target for the captured live milestone was rift_x64 PID 49504 / HWND 0x5121A. Revalidate the live PID/HWND before using it again. Forward250 passed, then ForwardSeries3x250 initially stopped safely after 2/3 pulses because maxAutoRefreshAttempts=1 was too low for the 60s proof-age budget. The config-only fix set ForwardSeries3x250 maxAutoRefreshAttempts to 3, validation passed, and the rerun passed all 3 pulses with total planar movement 1.0194439320789634m. No CE and no SavedVariables live truth. Auto-turn remains blocked; next safe expansion is route/waypoint smoke only after fresh ProofOnly/preflight.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Review/stage the config fix and this handoff intentionally | Preserves the live-series milestone without broad staging. |
| 2 | Update `docs\recovery\current-truth.md` top section if not already done | Keeps future resume from using the older partial state. |
| 3 | Run `git diff --check` before commit | Catches whitespace/Markdown issues. |
| 4 | Commit/push the coherent slice after review | Local `main` is ahead and now has a validated movement fix. |
| 5 | Before more movement, rerun fresh `ProofOnly` or use self-gated profiles | Proof anchors are short-lived. |
| 6 | Next live expansion should be waypoint smoke, not auto-turn | Forward movement is proven; turn backend is still blocked. |
| 7 | Keep using exact-HWND `window-message` for forward pulses | It is the successful backend for this target. |
| 8 | Improve milestone review warnings for non-ProofOnly latest pointers | Current review warns when latest pointer is a movement profile even after valid movement. |
| 9 | Consider making series refresh budget proportional to pulse count | Avoids profile-specific tuning if pulse count grows. |
| 10 | Do not treat final coordinate as current-now later | It is a recorded snapshot until API-now vs memory-now passes again. |
