# RiftReader handoff — PID 28248 proof ready, x64dbg attach currently blocked

Created UTC: `2026-05-23T06:30:00Z`

## Direct result

The current live coordinate proof/readiness remains good for PID `28248` / HWND `0x2302BC`, but the actor/static-chain access-provenance lane is now blocked at x64dbg attach.

- Current proof anchor: `0x2D409F3BBE0`
- Current candidate ID: `api-family-hit-000001`
- Current proof pointer: `docs/recovery/current-proof-anchor-readback.json`
- Current-truth status: `current_pid_28248_proof_anchor_passed_riftscan_readiness_ready_x64dbg_attach_blocked_actor_static_chain_not_promoted`
- Post-attempt recovery: `python .\scripts\coordinate_recovery_status.py --json` passed at `2026-05-23T06:25:48Z`

## What changed since the prior 05:55 handoff

- Added command-level x64dbg attach diagnostics to `scripts/rift_live_test/x64dbg_live_access_capture.py`.
- Added unit coverage for the new attach diagnostic/fallback behavior in `scripts/test_x64dbg_live_access_capture.py`.
- Retried one bounded `stop-context` x64dbg capture against PID `28248`; it failed before a debug session started.
- Updated `docs/recovery/current-truth.json` and `docs/recovery/current-truth.md` so they no longer claim x64dbg was unused after the retry.
- Preserved the provider/consumer boundary; ChromaLink files were not edited.

## x64dbg attach evidence

| Evidence | Artifact |
|---|---|
| Environment probe | `scripts/captures/x64dbg-attach-environment-probe-20260523-061423-261651/summary.json` |
| Manual attach retry diagnostic | `scripts/captures/x64dbg-manual-attach-retry-diagnostic-20260523-021754/summary.json` |
| Command-line `-p` diagnostic | `scripts/captures/x64dbg-commandline-pid-attach-diagnostic-20260523-021930/summary.json` |
| Final patched attach retry | `scripts/captures/x64dbg-live-access-capture-20260523-062455-703468/summary.json` |

Final patched retry result:

- x64dbg launched and automation responded (`debuggerVersion=25`).
- Attach command variants were rejected before debug session start:
  - `attach 0x6e58`
  - `attach 6e58`
  - `AttachDebugger 6e58`
- The x64dbg helper session was terminated after failed attach.
- No breakpoints/watchpoints were set.
- No target memory writes were made.
- No movement/game input was sent by the x64dbg retry.

## Current proof/readiness still valid

- `python .\scripts\coordinate_recovery_status.py --json` passed after the attach retry.
- Current PID/HWND still match the proof pointer.
- The current proof anchor remains movement-safety evidence only; it is not a promoted actor/static chain.

## Safety ledger

| Operation | Status |
|---|---|
| Cheat Engine | Not used |
| x64dbg/live debugger attach | Attempted, but failed before debug session start |
| Breakpoints/watchpoints | Not used |
| Memory writes | Not used |
| Provider writes | Not used |
| Movement/input in x64dbg retry | Not used |
| Git stage/commit/push | Not yet used for this handoff |
| Secrets/private tokens | No key/token/password-like material found in changed diff; do not publish raw private data |

## Remaining blockers

- `actor-static-chain-not-reacquired-for-current-pid-28248`
- `x64dbg-stop-context-attach-command-rejected-current-pid-28248`
- `blocked-no-debugger-access-provenance`
- `no-module-rva-static-owner-resolver-promoted`
- `no-static-resolver-promoted`
- `not-restart-validated`

## Top 10 recommended next actions

1. Treat PID `28248` proof anchor/readiness as current safe baseline, not a static chain.
2. Prefer no-debug/read-only actor candidate reacquisition next; the immediate x64dbg route is blocked.
3. If x64dbg must continue, diagnose attach rejection at the environment/target level without breakpoints or watchpoints first.
4. Keep verifying `coordinate_recovery_status.py --json` after every live debugger attempt.
5. Keep ChromaLink preflight at `640x360 / P360C` before any consumer proof or movement test.
6. Do not run broad debugger scans or breakpoint loops; stay bounded to stop-context/access provenance only.
7. Do not promote any actor/static chain until owner layout, module/RVA resolver, API-now vs chain-now, restart/relog, and ProofOnly gates pass.
8. Preserve PID `67680` actor-like evidence as historical only.
9. Package the current code/docs fix as a local commit after validation and secret scan if the tree is coherent.
10. After commit, continue with the next no-debug reacquisition slice or produce an attach-rejection diagnostic packet for external review.
