# **✅ HANDOFF — fresh ProofOnly passed for PID 12148**

Updated UTC: `2026-05-27T08:40:30Z`

## TL;DR

A fresh same-target `ProofOnly` refresh was approved and run for RIFT PID `12148`
/ HWND `0x640C0C`. It passed without movement, live input, Cheat Engine, or
x64dbg. The tracked current proof pointer
`docs/recovery/current-proof-anchor-readback.json` was updated to the new
ProofOnly run at `2026-05-27T08:39:18.643106+00:00`.

This clears the previous stale-proof blocker for the current moment, but the
proof freshness budget is short (`60s`). Any future movement attempt must still
run an exact-target preflight immediately beforehand and requires separate
explicit live-input approval.

## Safety

| Item | Status |
|---|---|
| Game input / movement | `not sent` |
| Movement attempted | `false` |
| Cheat Engine | `not used` |
| x64dbg / debugger attach | `not used` |
| Provider repo writes | `none` |
| SavedVariables as live truth | `false` |
| Proof/current-truth promotion beyond pointer refresh | `none` |

## Fresh ProofOnly result

| Field | Value |
|---|---|
| Command | `python C:\RIFT MODDING\RiftReader\scripts\live_test.py --profile ProofOnly --pid 12148 --hwnd 0x640C0C --process-name rift_x64` |
| Status | `passed-proof-only` |
| Run directory | `scripts/captures/live-test-ProofOnly-20260527-083803` |
| Run summary | `scripts/captures/live-test-ProofOnly-20260527-083803/run-summary.json` |
| Readback summary | `scripts/captures/proof-anchor-currentpid-12148-readback-summary-20260527-043909.json` |
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Pointer updated UTC | `2026-05-27T08:39:18.643106+00:00` |
| Candidate | `api-family-hit-000001` |
| Candidate address | `0x23863A26E50` |
| Current coordinate | `X=7261.8330078125`, `Y=821.7017822265625`, `Z=3003.057861328125` |
| Coordinate recorded UTC | `2026-05-27T08:39:17.6660688Z` |

## Post-run gates

| Gate | Result |
|---|---|
| Decision packet | `blocked-safe` for actor/static/debugger blockers |
| Workflow proof freshness at refresh | `fresh` (`35s <= 60s`) |
| Proof preflight at `2026-05-27T08:39:59Z` | `Status=valid`, `MovementAllowed=true` |
| Live triage movement gate | `allowed-current-target-proofonly-passed-route-smoke-passed` |
| Remaining blockers | actor/static chain not promoted; no static resolver; debugger provenance blocked by existing debug object / `DebugActiveProcessStop` access denied |

## Interpretation

- The stale proof-anchor blocker is cleared for this current PID/HWND epoch at
  the recorded timestamp.
- This does not authorize movement by itself; movement/live input is still a
  separate approval gate.
- Because the movement preflight max age is `60s`, any future movement slice must
  re-check proof freshness immediately before input.
- Do not retry the same x64dbg attach/detach path without a new approved tactic.

## Next safe/gated actions

| Action | Gate |
|---|---|
| Commit this proof pointer + handoff evidence | safe local Git after validation |
| Push the evidence commit | requires explicit push approval |
| Live movement validation | requires separate explicit live-input approval and immediate fresh preflight |
| New debugger/process-owner tactic | requires explicit debugger approval |
| Continue no-debug actor/static evidence work | safe only while it remains read-only/no-input/no-provider-write |
