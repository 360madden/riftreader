# 2026-05-13 19:15 EDT — Same-target candidate + stale-cache guard handoff

## ✅ Result

RiftReader is now safer against stale coordinate proof data after the PID/HWND change.
The stale promoted pointer was already invalidated in `docs/recovery/current-proof-anchor-readback.json`; this slice also prevents the stale runtime proof-anchor cache from shadowing the current live target during proof preflight.

## Current live target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Process start UTC | `2026-05-13T16:17:56.208370Z` |
| Module base | `0x7FF71CD90000` |
| Movement | **Blocked** |
| Cheat Engine | **Not used** |
| Input/movement sent in this slice | **No** |

## What changed

| Area | Change |
|---|---|
| Same-target candidate synthesis | Added `scripts/rift_live_test/same_target_candidate_synth.py` and wrapper `scripts/same_target_candidate_synth.py` to convert current-PID readback evidence into an importable candidate file. |
| Coordination strategy | `riftscan_coordination.py` and `riftscan_feedback.py` now recognize latest RiftReader same-target candidate files as a read-only proof source when provider-side RiftScan files are unavailable. |
| Stale proof-anchor cache guard | `assert-current-proof-coord-anchor.ps1` now ignores no-CE proof-anchor cache documents whose PID/HWND do not match the requested target and reports `ignored_stale_cache` warnings. |
| Readback reporting | `invoke-riftscan-coordinate-readback.ps1` now propagates proof-anchor warnings into top-level summaries so stale-cache rejection is visible. |
| Docs | `docs/recovery/current-truth.md` updated with current candidate/proof state and stale-cache behavior. |

## Best current candidate evidence

| Artifact | Verdict |
|---|---|
| `scripts/captures/same-target-candidate-synth-20260513-230531-602926/same-target-candidates.json` | Contains 3 same-target current-PID candidates. Candidate-only, not movement truth. |
| Selected candidate | `same-target-268DF21ED30-xyz` at `0x268DF21ED30` |
| Offset-corrected delta | `0.0024121093747453415` |
| Direct delta | about `5.0027`, so not direct coordinate proof yet |
| Latest milestone review | `scripts/captures/riftscan-milestone-review-20260513-231429.json` = `ready-for-read-only-proof`, movement still false |
| Latest explicit candidate readback | `scripts/captures/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-191349.json` |

## Stale-data fix evidence

Latest explicit readback shows the old runtime cache was not accepted as current proof:

```text
proof_anchor_cache_pid_mismatch:anchor=57656;target=2928:ignored_stale_cache
proof_anchor_cache_hwnd_mismatch:anchor=0x5417BC;target=0xC0994:ignored_stale_cache
```

The preflight then attempted the current resolver path and stayed blocked because the coord-trace anchor does not match the current live process. That is correct fail-closed behavior.

## Current blocker

Fresh reference/proof anchor is still missing:

- proof-pose attempt `scripts/captures/riftscan-proof-pose-20260513-230600/` blocked with `blocked-reference-unavailable` because no usable `RRAPICOORD1` marker was captured;
- candidate readback is stable but has `ReferenceCoordinate=null`;
- `MovementAllowed=false` and no `ProofOnly` pass exists for PID `2928` / HWND `0xC0994`.

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/recovery/current-truth.md and this handoff first. Current target is rift_x64 PID 2928 HWND 0xC0994. Do not use CE and do not send movement/input. Continue the coordinate proof recovery from same-target candidate file scripts/captures/same-target-candidate-synth-20260513-230531-602926/same-target-candidates.json. The stale proof-anchor cache for PID 57656/HWND 0x5417BC must remain historical only; assert-current-proof-coord-anchor.ps1 should report ignored_stale_cache if it sees it. Next objective: capture fresh API/reference evidence for the current target, prove one of the same-target candidates across poses, promote a current proof anchor only after same-target proof, then run ProofOnly. Movement remains blocked until ProofOnly passes.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Fix/refresh the RRAPICOORD reference capture path for PID `2928`. | Proof-pose is blocked on missing fresh reference, not candidate readback. |
| 2 | Rerun read-only proof-pose with the same-target candidate file after reference capture works. | Converts stable candidate evidence into API-now vs memory-now proof evidence. |
| 3 | Use at least two displaced poses before promotion. | One pose cannot prove movement-grade coordinate truth. |
| 4 | Keep stale cache warnings visible in summaries. | Prevents future accidental reuse of old PID/HWND proof anchors. |
| 5 | Promote only if the same candidate matches current API/reference across poses. | Avoids promoting offset-copy or nearby-family artifacts. |
| 6 | Run `ProofOnly` immediately after promotion for PID `2928` / HWND `0xC0994`. | Same-target gate is required before movement/navigation. |
| 7 | If reference capture stays blocked, widen family snapshot deltas around `0x268DF21E000`. | Keeps the primary method broad/family-based instead of stale narrow probing. |
| 8 | Preserve the current candidate packet as candidate-only evidence. | It is useful seed data but not current movement truth. |
| 9 | Re-run `scripts/riftscan_milestone_review.py` after each proof milestone. | Keeps the RiftReader/RiftScan boundary and movement gate honest. |
| 10 | Update `current-truth.md` immediately after any promotion or proof failure. | Prevents stale docs from becoming stale workflow logic. |
