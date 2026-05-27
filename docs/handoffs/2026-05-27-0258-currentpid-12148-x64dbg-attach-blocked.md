# **⚠️ HANDOFF — PID 12148 route smoke green, x64dbg attach blocked**

Generated UTC: `2026-05-27T06:58:00Z`
Repo: `C:\RIFT MODDING\RiftReader`

## Verdict

| Item | Current status |
|---|---|
| Live RIFT target | PID `12148`, HWND `0x640C0C`, title `RIFT` |
| Process start UTC | `2026-05-27T01:17:01.2653526Z` |
| Module base | `0x7FF77AF40000` |
| Route smoke | `passed`; observed-forward 2m route arrived in `1` pulse |
| Current proof anchor | `api-family-hit-000001` at `0x23863A26E50` |
| Static actor chain | Not promoted |
| x64dbg no-attach readiness | `passed` |
| x64dbg stop-context attach | `failed-before-debug-session` |
| Primary new blocker | Existing debug object/debug port on PID `12148` |

Route smoke remains current proof-anchor truth for this live process epoch. It
is not actor/static-chain truth.

## What changed in this slice

| Area | Result |
|---|---|
| No-attach readiness helper | Added `--ignore-rift-error-handler` passthrough so the packet can reuse the preflight behavior after confirming the normal RIFT child crash handler. |
| Regression coverage | Added a unit test proving the flag is passed to preflight and recorded in the packet safety state. |
| x64dbg readiness | Regenerated a no-attach readiness packet for PID `12148`; status `passed`, readiness `ready-for-current-turn-approval`. |
| Live x64dbg attempt | Ran one approved `stop-context` attempt only; no breakpoint/watchpoint, no input, no memory writes. |
| Debug-state diagnosis | Read-only recovery found an existing debug object/debug port, explaining attach rejection. |
| Current truth | Updated current truth JSON/Markdown to record x64dbg status and blockers. |

## Evidence artifacts

| Evidence | Path |
|---|---|
| No-attach readiness packet | `scripts/captures/x64dbg-no-attach-readiness-packet-20260527-065241-005785/summary.json` |
| Attach environment probe | `scripts/captures/x64dbg-attach-environment-probe-20260527-065315-816903/summary.json` |
| Stop-context attempt | `scripts/captures/x64dbg-live-access-capture-20260527-065357-522442/summary.json` |
| Post-attempt preflight | `scripts/captures/x64dbg-target-preflight-20260527-065416-506755/summary.json` |
| Read-only debug-state recovery | `scripts/captures/x64dbg-target-recovery-20260527-065545-618096/summary.json` |
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Current truth | `docs/recovery/current-truth.json` |

## x64dbg attach details

The approved `stop-context` attempt launched x64dbg automation and tried the
bounded attach command variants. Every attach command was rejected before a
debug session started:

| Command | Accepted | Debugging |
|---|---:|---:|
| `attach 0x2f74` | `false` | `false` |
| `attach 2f74` | `false` | `false` |
| `AttachDebugger 2f74` | `false` | `false` |

Read-only target recovery then reported:

| Debug-state field | Value |
|---|---|
| `processDebugPort` | `0xFFFFFFFFFFFFFFFF` |
| `processDebugFlags` | `0` |
| `processDebugObjectHandle` | `0x250` |
| `processDebugFlagsIndicatesDebugger` | `true` |
| `debuggerLikelyAttached` | `true` |

Interpretation: x64dbg attach is blocked because PID `12148` already has a
debug object/debug port. The visible debugger-class process scan still reports
zero x64dbg/CE processes; the known `rifterrorhandler_x64.exe` child exists and
was confirmed as the normal child handler for this exact PID.

## Safety ledger

| Operation | Status |
|---|---|
| Cheat Engine | Not used |
| x64dbg live attach | Attempted once, blocked before debug session |
| Breakpoints/watchpoints | Not set |
| Memory writes | Not used |
| Game input/movement during x64dbg attempt | Not sent |
| Provider writes | Not used |
| Proof/static-chain promotion | Not performed |
| Post-attempt target state | PID/HWND still visible/responding; preflight passed |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile .\scripts\rift_live_test\x64dbg_no_attach_readiness_packet.py .\scripts\x64dbg_no_attach_readiness_packet.py .\scripts\test_x64dbg_no_attach_readiness_packet.py` | Passed |
| `python -m unittest .\scripts\test_x64dbg_no_attach_readiness_packet.py` | Passed, 9 tests |
| `python .\scripts\x64dbg_preflight.py ... --ignore-rift-error-handler --json` | Passed after attach attempt |
| `python -m rift_live_test.x64dbg_target_recovery ... --json` | Captured, target responding before/after |

## Current blockers

- `actor-static-chain-not-promoted`
- `blocked-no-debugger-access-provenance`
- `x64dbg-attach-blocked-existing-debug-object`
- `no-static-resolver-promoted`
- `not-restart-validated-for-static-actor-chain`

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit the validated helper/current-truth patch | Preserve the exact blocker and reproducible readiness fix. |
| 2 | Do not retry the same x64dbg attach command sequence | It already failed with command-level evidence and a debug-object explanation. |
| 3 | Ask before `DebugActiveProcessStop` or detaching the existing debug object | This crosses a live debugger/process-state boundary. |
| 4 | If approved, run a read-only pre-detach packet first | Ensures exact PID/HWND/start/module and post-detach recovery plan are captured. |
| 5 | After any detach action, immediately run target recovery and ProofOnly | Verifies the client is responsive and proof gate remains current. |
| 6 | Prefer no-debug actor/static evidence if detach is not approved | Keeps progress moving without changing live process debug state. |
| 7 | Keep proof-anchor and actor/static-chain lanes separate | Prevents promoting coordinate-copy evidence as restart-stable actor truth. |
| 8 | Do not use `memory-access` mode without a new approval | It is broader than the allowed stop-context/hardware-read default. |
| 9 | Do not push without explicit approval | Remote mutation remains a separate gate. |
| 10 | Re-run `scripts\riftscan_milestone_review.py` after the commit | Refreshes the strategy gate before expanding live/debugger scope. |
