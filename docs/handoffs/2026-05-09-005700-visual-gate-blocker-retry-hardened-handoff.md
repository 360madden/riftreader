# Visual-gate blocker retry hardening handoff

Created: 2026-05-09 00:57 EDT / 2026-05-09 04:57 UTC  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch: `main`  
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

No live input was sent in this slice. The no-input visual gate was retried and
still failed closed for the current RIFT window, but the blocker output is now
more actionable: the gate records every capture failure class it observes and
emits concrete recovery recommendations in both JSON and Markdown summaries.

Auto-turn/yaw stimulus remains blocked until a future visual gate returns
`readyForLiveInput=true`, followed by fresh `ProofOnly` against the exact
current PID/HWND. No CE was used. SavedVariables were not used as live truth.

## Evidence

| Fact | Value |
|---|---|
| Fresh no-input visual gate | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-005541\visual-gate-status.json` |
| Visual gate status | `blocked-visual-baseline`; `readyForLiveInput=false`; `movementSent=false`; `inputSent=false` |
| Capture failure classes | `desktop-capture-access-denied`, `desktop-copyfromscreen-invalid-handle`, `capture-methods-return-black-or-flat-content` |
| Recovery recommendations now emitted | `restore-interactive-desktop-capture`, `restore-visible-window-content`, `keep-live-input-blocked` |
| Markdown summary | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-005541\visual-gate-status.md` |
| Code hardening | `scripts\rift_live_test\visual_gate_status.py` now preserves multiple capture failure classifications and writes recovery recommendations. |
| Regression coverage | `scripts\test_visual_gate_status.py` covers passed gates, target blockers, multi-capture blockers, and no-input recovery guidance. |
| Milestone review | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0057-visual-gate-blocker-hardened.json`; status `ready-for-read-only-proof`; movement allowed by review `false`. |

## Validation performed

| Check | Result |
|---|---|
| Visual-gate unit tests | Passed: `python .\scripts\test_visual_gate_status.py` (`6` tests). |
| Python compile check | Passed: `python -m py_compile .\scripts\rift_live_test\visual_gate_status.py .\scripts\test_visual_gate_status.py`. |
| Fresh no-input visual gate | Failed closed with richer blocker output; no input sent. |
| RiftScan milestone review | Passed; `ready-for-read-only-proof`; review is not movement permission. |

## Resume rules

| Rule | Detail |
|---|---|
| No live input yet | Current visual gate is blocked; do not send movement, yaw, or turn stimulus. |
| Restore desktop capture first | Unlock/reconnect the interactive desktop or restart the capture host/session, make Rift visible/unobscured, then rerun the full visual gate. |
| Visual gate command | `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full` |
| Proof second | After visual gate passes, rerun `python .\scripts\live_test.py --profile ProofOnly --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui`. |
| Candidate screen | Only use `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-currentpid-49504-20260509-0035\player-orientation-candidate-search-proofcoord.json` if the target/process epoch remains current and fresh proof still matches. Regenerate after movement/restart. |
| No CE / no SavedVariables live truth | Do not use Cheat Engine or SavedVariables as current live truth unless explicitly reauthorized by the user. |

## Suggested next milestone

Restore visual capture access, rerun the no-input visual gate, and only if it
passes rerun fresh `ProofOnly` before attempting the bounded actor-yaw candidate
stimulus. Do not combine yaw proof with route execution.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read
`docs\recovery\current-truth.md`, `docs\recovery\README.md`, and
`docs\handoffs\2026-05-09-005700-visual-gate-blocker-retry-hardened-handoff.md`
first. The current live target is `rift_x64` PID `49504`, HWND `0x5121A`.
The visual gate was retried at
`C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-005541\visual-gate-status.json`
and is still `blocked-visual-baseline`, but now reports all observed capture
failure classes plus recovery recommendations. No live input was sent. Before
any movement/yaw stimulus, restore desktop/window capture, rerun the full visual
gate, and rerun fresh `ProofOnly`. Do not use CE, do not use SavedVariables as
live truth, and do not use auto-turn until actor-facing/turn-backend truth is
promoted for the current session.
