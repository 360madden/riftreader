# Visual-gate focus blocker handoff

Created: 2026-05-09 01:05 EDT / 2026-05-09 05:05 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

No live input was sent in this slice. The visual gate was hardened again after
the latest blocked artifact showed a subtle safety bug: the focus helper could
exit `0` while the returned window snapshot still had `isForeground=false`.

The gate now requires the focus attempt to confirm foreground ownership before
`readyForLiveInput` can become true. A fresh no-input retry now explicitly
reports `focusConfirmedForeground=false` and blocker
`focus-window-not-foreground` alongside the capture failures.

Auto-turn/yaw stimulus remains blocked until a future visual gate returns
`readyForLiveInput=true`, followed by fresh `ProofOnly` for the exact target.

## Evidence

| Fact | Value |
|---|---|
| Fresh no-input visual gate | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-010348\visual-gate-status.json` |
| Visual gate status | `blocked-visual-baseline`; `readyForLiveInput=false`; `focusConfirmedForeground=false`; `movementSent=false`; `inputSent=false` |
| Blockers | `focus-window-not-foreground`, `desktop-capture-access-denied`, `desktop-copyfromscreen-invalid-handle`, `capture-methods-return-black-or-flat-content` |
| Recovery recommendations | `restore-focus`, `restore-interactive-desktop-capture`, `restore-visible-window-content`, `keep-live-input-blocked` |
| Focus evidence | `focus-window` attempt returned exit `0`, but JSON still reported `isForeground=false`. |
| Code hardening | `scripts\rift_live_test\visual_gate_status.py` now treats exit `0` focus as insufficient unless the returned window JSON confirms `isForeground=true`. |
| Regression coverage | `scripts\test_visual_gate_status.py` now covers focus exit-0/non-foreground rejection and avoids adding a misleading generic `focus-window-failed` when the specific `focus-window-not-foreground` blocker is present. |
| Milestone review | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0105-visual-gate-focus-hardened.json`; status `ready-for-read-only-proof`; movement allowed by review `false`. |

## Validation performed

| Check | Result |
|---|---|
| Visual-gate unit tests | Passed: `python .\scripts\test_visual_gate_status.py` (`9` tests). |
| Python compile check | Passed: `python -m py_compile .\scripts\rift_live_test\visual_gate_status.py .\scripts\test_visual_gate_status.py`. |
| Fresh no-input visual gate | Failed closed with explicit `focus-window-not-foreground`; no input sent. |
| RiftScan milestone review | Passed; `ready-for-read-only-proof`; review is not movement permission. |

## Resume rules

| Rule | Detail |
|---|---|
| No live input yet | Current visual gate is blocked; do not send movement, yaw, turn, screenshot-key, or other live input. |
| Restore focus/capture first | Bring the exact Rift window foreground on the interactive desktop, then restore capture access/visibility. |
| Visual gate command | `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full` |
| Proof second | After visual gate passes, rerun `python .\scripts\live_test.py --profile ProofOnly --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui`. |
| Candidate screen | Only use `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-currentpid-49504-20260509-0035\player-orientation-candidate-search-proofcoord.json` if target/process epoch remains current and fresh proof still matches. Regenerate after movement/restart. |
| No CE / no SavedVariables live truth | Do not use Cheat Engine or SavedVariables as current live truth unless explicitly reauthorized by the user. |

## Suggested next milestone

After the operator/desktop restores foreground + capture access, rerun the full
visual gate. If it passes, immediately rerun fresh `ProofOnly`, then proceed to
the bounded actor-yaw candidate stimulus only. Do not combine yaw proof with
route execution.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read
`docs\recovery\current-truth.md`, `docs\recovery\README.md`, and
`docs\handoffs\2026-05-09-010500-visual-gate-focus-blocker-handoff.md` first.
The current live target is `rift_x64` PID `49504`, HWND `0x5121A`. The latest
visual gate retry at
`C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-010348\visual-gate-status.json`
is still `blocked-visual-baseline`, now explicitly showing
`focusConfirmedForeground=false` and blocker `focus-window-not-foreground`
plus capture blockers. No live input was sent. Before any movement/yaw stimulus,
restore foreground/capture, rerun the full visual gate, and rerun fresh
`ProofOnly`. Do not use CE, do not use SavedVariables as live truth, and do not
use auto-turn until actor-facing/turn-backend truth is promoted for the current
session.
