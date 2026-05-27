# **🛑 COMPACT HANDOFF — live input gate, clean remote baseline**

Updated UTC: `2026-05-27T08:58:30Z`

## TL;DR

`main` is clean, synced with `origin/main`, and CI-green at
`6879b51 Document forward dry-run proof gate`. Live recovery is blocked at the
explicit live-input gate. The current RIFT target still matches PID `12148` /
HWND `0x640C0C`, but the latest ProofOnly pointer is stale for movement
(`587s > 60s` at the latest workflow status refresh).

Do not infer live movement approval from generic autonomy text. The next useful
live step requires an exact approval for a fresh ProofOnly/preflight followed by
one bounded `Forward250` pulse.

## Current repo state

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Remote state | `main...origin/main` |
| HEAD | `6879b51 Document forward dry-run proof gate` |
| Worktree | `clean` |
| Latest handoff before this | `docs/handoffs/2026-05-27-0449-proofonly-refresh-forward-dryrun-blocked.md` |

## Current live target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Target verdict | `artifact-pid-running` |
| Candidate | `api-family-hit-000001` |
| Candidate address | `0x23863A26E50` |

## Latest proof / movement gate

| Field | Value |
|---|---|
| Current proof status | `current-target-proofonly-passed` |
| Proof pointer timestamp | `2026-05-27T08:48:10.760652+00:00` |
| Proof freshness at latest status | `stale`, `587s > 60s` |
| Movement gate | `blocked-proof-anchor-age-out-of-range` |
| Last dry-run | `gated-forward-smoke-currentpid-12148-summary-20260527-084901.json` |
| Dry-run result | `blocked-preflight`; no input sent |
| Dry-run blocker | `proof_anchor_age_out_of_range_seconds:62.516` |

## Safety status

| Item | Status |
|---|---|
| Movement / input in latest checks | `not sent` |
| Cheat Engine | `not used` |
| x64dbg / debugger attach | `not used` |
| Provider repo writes | `none` |
| SavedVariables as live truth | `false` |
| Proof/current-truth promotion | `none beyond tracked ProofOnly pointer refreshes` |

## Remaining blockers

| Blocker | Meaning |
|---|---|
| `proof-anchor-stale-for-movement` | Any movement requires immediate fresh ProofOnly/preflight first |
| `actor-static-chain-not-promoted` | Actor/static resolver is not proven/promoted |
| `no-static-resolver-promoted` | No static resolver is available for restart-grade actor chain |
| `not-restart-validated-for-static-actor-chain` | Current candidate is not restart-validated |
| `blocked-no-debugger-access-provenance` | No-debug evidence is candidate-only |
| `x64dbg-attach-blocked-existing-debug-object` | Existing debug object blocks the prior attach path |
| `debugactiveprocessstop-access-denied-winerr-5` | Prior detach attempt failed; do not loop the same tactic |

## Exact next approval required

Live input is the next meaningful action. The required approval text is:

```text
I explicitly approve one bounded live Forward250 pulse for PID 12148 / HWND 0x640C0C:
fresh ProofOnly/preflight, then one W pulse for 250ms via C# ScanCode, record post-readback, then stop.
```

If approved, run only that bounded plan and stop after the single pulse.

## Resume commands

| Purpose | Command |
|---|---|
| Compact status | `scripts\riftreader-workflow-status.cmd --compact-json --write` |
| Decision packet | `scripts\riftreader-decision-packet.cmd --compact-json --write` |
| Strategy gate | `python scripts\riftscan_milestone_review.py --compact-json --write-summary` |
| Read-only actor status | `python scripts\actor_chain_no_debug_status.py --json` |
| Fresh ProofOnly only | `python scripts\live_test.py --profile ProofOnly --pid 12148 --hwnd 0x640C0C --process-name rift_x64` |
| Live pulse after explicit approval only | `python scripts\live_test.py --profile Forward250 --pid 12148 --hwnd 0x640C0C --process-name rift_x64 --live` |
