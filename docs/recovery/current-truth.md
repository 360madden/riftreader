# RiftReader Current Truth

_Last updated: 2026-05-14T20:19:12Z._

## Verdict

**Active RIFT target discovered, but coordinate proof is blocked.** The current window is PID `23496` / HWND `0x2C1024`; however, the former PID `16536` proof pointer `0x21487DF8F64` is historical/stale after game close. `ProofOnly` against PID `23496` blocked with target drift and sent no movement.

Movement remains **blocked** until PID `23496` gets a fresh same-target proof anchor and `ProofOnly` passes.

## Current target candidate

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `23496` |
| HWND | `0x2C1024` |
| Window title | `RIFT` |
| Process start | `2026-05-14T20:02:28.245722Z` |
| Module base | `0x7FF71CD90000` |
| Target-control | `passed-target-control` / `exact-hwnd-foreground` |
| ProofOnly | `blocked-target-drift` |
| Movement allowed | `false` |

## Candidate-only live reference from blocked ProofOnly

| Field | Value |
|---|---|
| Coordinate | `x=7405.1499, y=871.77, z=3028.53` |
| Recorded | `2026-05-14T20:08:04.6985193Z` |
| Artifact | `scripts/captures/post-close-proofonly-current-target-23496-20260514-2007/live-test-ProofOnly-20260514-200725/run-summary.json` |
| Truth status | Candidate/reference only; not movement proof. |
| Issues | `target_drift:current_proof_pointer_pid_mismatch:actual=None;expected=23496; target_drift:current_proof_pointer_hwnd_missing` |

## Historical / stale PID 16536 proof

| Field | Value |
|---|---|
| Former PID/HWND | `16536` / `0x1E0D66` |
| Former candidate | `snapshot-delta-21487DF8F64-xyz` |
| Former address | `0x21487DF8F64` |
| Current status | Historical/stale after game close. |
| Reuse policy | Recovery seed/access-proof history only; do not use as current movement truth. |

## Preserved x64dbg access proof pattern

This is useful structure evidence to guide reacquisition, not a live pointer after process restart.

| Field | Value |
|---|---|
| Access instruction | `rift_x64.exe+0x678A79: movsd qword ptr [rax+0xC4], xmm0` |
| Component base at hit | `rax/rbx = 0x21487DF8EA0` |
| XYZ offsets from component base | X `+0xC4`, Y `+0xC8`, Z `+0xCC` |
| Source/copy context candidate | `rdi = 0x214E38B5A00` |
| Decoded proof | `scripts/captures/owner-access-path-21487DF8F64-currentpid-16536-decoded-access-20260514-1956/decoded-access-summary.json` |

## Current blockers

- `target-drift-current-target-pid23496-proof-anchor-missing`
- `prior-pid16536-proof-pointer-stale-after-game-close`
- `current-pid-family-recovery-required-before-movement`
- `movement-blocked-until-fresh-same-target-proofonly-passes`

## Required before movement/live truth use

1. Use PID `23496` / HWND `0x2C1024` as the next recovery target if it remains active.
2. Rebuild/reacquire current-PID coordinate proof for PID `23496`.
3. Validate API-now vs memory-now against the new proof candidate.
4. Promote only after same-target current proof anchor exists.
5. Rerun `ProofOnly` and require `passed-proof-only`.
