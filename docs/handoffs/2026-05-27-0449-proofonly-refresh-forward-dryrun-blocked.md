# **⚠️ HANDOFF — ProofOnly refreshed, forward dry-run blocked by proof age**

Updated UTC: `2026-05-27T08:49:20Z`

## TL;DR

A fresh exact-target `ProofOnly` refresh was run for PID `12148` / HWND
`0x640C0C` and passed with no movement, no live input, no Cheat Engine, and no
x64dbg. The current proof pointer was updated to the run ending at
`2026-05-27T08:48:10.760652+00:00`.

Immediately afterward, the safest bounded movement wrapper was checked in
`-DryRun` mode for a single `W` pulse (`250ms`, C# ScanCode backend). The dry-run
failed closed before any input because the proof-anchor age was already
`62.516s`, exceeding the `60s` movement freshness budget.

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
| Run directory | `scripts/captures/live-test-ProofOnly-20260527-084720` |
| Run summary | `scripts/captures/live-test-ProofOnly-20260527-084720/run-summary.json` |
| Readback summary | `scripts/captures/proof-anchor-currentpid-12148-readback-summary-20260527-044804.json` |
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Pointer updated UTC | `2026-05-27T08:48:10.760652+00:00` |
| Candidate | `api-family-hit-000001` |
| Candidate address | `0x23863A26E50` |
| Current coordinate | `X=7261.8330078125`, `Y=821.7017822265625`, `Z=3003.057861328125` |
| Coordinate recorded UTC | `2026-05-27T08:48:10.0066879Z` |

## Forward smoke dry-run

| Field | Value |
|---|---|
| Wrapper | `scripts/invoke-gated-forward-smoke.ps1` |
| Mode | `-DryRun` |
| Backend | `csharp-scancode` |
| Planned key | `w` |
| Planned hold | `250ms` |
| Planned pulses | `1` |
| Status | `blocked-preflight` |
| Proof issue | `proof_anchor_age_out_of_range_seconds:62.516` |
| Summary file | `scripts/captures/gated-forward-smoke-currentpid-12148-summary-20260527-084901.json` |
| Movement sent | `false` |

## Interpretation

- The exact-target ProofOnly proof refreshed successfully.
- The movement wrapper correctly failed closed once the proof age exceeded the
  `60s` movement budget.
- Any real movement must be run as a tightly sequenced operation: immediate
  fresh ProofOnly/preflight, then one bounded live input pulse before the age
  budget expires.
- A generic autonomy request is not enough for live input. The live-input gate
  must explicitly approve the exact pulse plan.

## Next safe/gated actions

| Action | Gate |
|---|---|
| Commit this proof pointer + handoff evidence | safe local Git after validation |
| Push the evidence commit | requires explicit push approval |
| Run one real `Forward250` / gated forward smoke pulse | requires explicit live-input approval and immediate fresh preflight |
| New debugger/process-owner tactic | requires explicit debugger approval |
| Continue no-debug actor/static evidence work | safe only while read-only/no-input/no-provider-write |
