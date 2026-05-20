# Character login restart handoff — PID 51016 / HWND 0x4613F0

## TL;DR

The game was restarted and is reacquired at the character selection screen as RIFT PID `51016`, HWND `0x4613F0`. No click/key/movement was sent. The latest screenshot is blocked by a Command Prompt overlay, so Play-click automation is **not high-confidence** and remains blocked.

## Current target

| Field | Value |
|---|---|
| Updated UTC | `2026-05-20T19:06:25Z` |
| Process | `rift_x64` |
| PID / HWND | `51016` / `0x4613F0` |
| Process start UTC | `2026-05-20T18:55:37.6710595Z` |
| Module base | `0x7FF7B77A0000` |
| Window title | `RIFT` |
| Client size | `640x360` |
| State | Character selection, not in-world |
| Movement gate | Blocked |

## Evidence collected

| Evidence | Status | Path |
|---|---|---|
| Clean character-select classifier | Passed, confidence `1.0` | `.riftreader-local\character-login-screen-state\run-20260520-185843-765426\character-login-screen-state-summary.json` |
| Clean screenshot | Shows selected `ATANK` on `Deepwood` | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-145745-653.png` |
| Character-select env capture | Passed read-only; world-entry visually available but not permitted | `.riftreader-local\character-select-automation-env\run-20260520-185900-605658\character-select-automation-env-summary.json` |
| Launcher inspection | Game child of Glyph; launcher minimized/offscreen; no launcher buttons safe | `.riftreader-local\launcher-inspection\run-20260520-185719-537492\launcher-inspection-summary.json` |
| Character-select plan | Planned, dry-run only | `.riftreader-local\character-select-automation-plan\run-20260520-190522-012595\character-select-automation-plan-summary.json` |
| Login resilience plan | Planned, dry-run only | `.riftreader-local\character-login-resilience-plan\run-20260520-190522-428657\character-login-resilience-plan-summary.json` |
| Executor contract | Blocked: source env does not permit world entry and approval is missing | `.riftreader-local\character-login-executor-contract\run-20260520-190522-904425\character-login-executor-contract-summary.json` |
| Readiness packet | Packet ready, but execution blockers remain | `.riftreader-local\character-login-readiness-packet\run-20260520-190523-313119\character-login-readiness-packet-summary.json` |
| Supervisor | Blocked: executor not ready | `.riftreader-local\character-login-supervisor\run-20260520-190523-757189\character-login-supervisor-summary.json` |
| Latest visual gate | Blocked by Command Prompt overlay; click targets not safe | `.riftreader-local\character-login-screen-state\run-20260520-190625-436699\character-login-screen-state-summary.json` |
| Redacted wrapper summary | No raw stdout persisted by wrapper | `.riftreader-local\turn-20260520-restart-pid51016-gates\redacted-helper-sequence-summary.json` |
| Workflow status | Blocked, live PID matches artifact PID | `.riftreader-local\workflow-status\20260520-191003Z\compact-sitrep.json` |

## Stale/historical state

| Epoch | Status | Policy |
|---|---|---|
| PID `86740`, HWND `0x414F8` | Historical after restart | Preserved at `docs\recovery\historical\current-proof-anchor-readback-2026-05-20-pid86740-hwnd414F8-character-select-approved-click-historical.json`; do not reuse old approval/click/proof state |
| PID `1948`, HWND `0x3C0D58` | Historical in-world proof | Do not use absolute coordinate proof until current in-world target passes same-target ProofOnly |

## Current blockers

| Blocker | Why it matters |
|---|---|
| Non-game overlay covers Play/shard/center landmarks | Prevents high-confidence click point validation; no Play click should be sent |
| Character selection is not in-world | No player coordinate proof exists for PID `51016` |
| Explicit current-run world-entry approval still required | Old approval tokens are invalid after restart/PID drift |
| Same-target ProofOnly not possible until world load | Movement remains blocked after login until proof is rebuilt |

## Resume sequence

1. Clear or avoid the overlay and recapture the bound RIFT window.
2. Rerun `scripts\riftreader-character-login-screen-state.cmd --expect-character-select --json` against the fresh screenshot.
3. Rerun environment capture/supervisor/readiness for PID `51016` / HWND `0x4613F0`.
4. Only if the same-run visual gate and executor gate pass, ask for/confirm explicit one-click Play approval.
5. If Play is clicked, send at most one click, wait for frame change, recapture, and classify post-click state.
6. After world entry, rediscover exact PID/HWND/process start and run same-target ProofOnly before movement.

## Latest 10 commits at handoff time

| Commit | Subject |
|---|---|
| `2b19501` | Harden MCP click input contract |
| `5e88719` | Record approved Play click result |
| `39d1adc` | Harden character relogin automation artifacts |
| `5dc7ad9` | Add guarded character login and launcher workflows |
| `c80cd92` | Add MCP final maintenance handoff |
| `ffb0bd0` | Align MCP final gate maintenance action |
| `11857e8` | Clarify MCP release handoff baseline |
| `d99648b` | Update MCP final release handoff |
| `6da92b7` | Complete MCP final progress dashboard |
| `3b064da` | Add MCP final readiness handoff |

## Safety notes

- No launcher buttons were pressed.
- No Play click was sent during this restart reacquisition.
- No keys, movement, Cheat Engine, x64dbg attach, provider writes, or live memory reads were used.
- Approval-token values are intentionally not written in this handoff.
