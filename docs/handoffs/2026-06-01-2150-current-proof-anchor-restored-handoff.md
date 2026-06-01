# Current proof anchor restored — 2026-06-01 21:50 UTC

## Result

The current proof anchor was rebuilt for the active RIFT target and same-target
`ProofOnly` now passes.

| Item | Value |
|---|---|
| Target | `rift_x64` PID `12664`, HWND `0x205146C` |
| Process start | `2026-06-01T17:19:45.159353Z` |
| Module base | `0x7FF6EE5D0000` |
| Proof candidate | `api-family-hit-000001 @ 0x1E067A80330` |
| Static coordinate chain | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| ProofOnly status | `passed-proof-only` |
| Current proof pointer | `docs\recovery\current-proof-anchor-readback.json` status `current-target-proofonly-passed` |
| Current truth | `docs\recovery\current-truth.json` updated `2026-06-01T21:52:01Z` |

## Evidence

| Evidence | Path / result |
|---|---|
| Target-drift invalidation | `scripts\captures\live-test-ProofOnly-20260601-212856\run-summary.json` blocked old PID `12148` / HWND `0x640C0C` |
| Historical stale proof pointer archive | `docs\recovery\historical\current-proof-anchor-readback-2026-06-01-pid12148-hwnd640C0C-historical.json` |
| Targeted current-PID family scan | `scripts\captures\family-scan-currentpid-12664-20260601-214049-071751\family-scan-summary.json` |
| Top candidate | `api-family-hit-000001 @ 0x1E067A80330`; max API delta `0.004418749999786087` |
| Displaced pose batch | `scripts\captures\current-pid-coordinate-anchor-batch-12664-owner-static-20260601-2141\coordinate-anchor-batch-summary.json` |
| Displacement proof | 3 captured poses, 2 exact-HWND `W` pulses, max planar displacement `5.691534591829909`, same candidate support count `3` |
| Promotion helper | `scripts\captures\proof-anchor-promote-currentpid-12664-20260601-174508` |
| Promotion assert | `valid`, movement gate `True`, anchor `0x1E067A80330` |
| Final ProofOnly | `scripts\captures\live-test-ProofOnly-20260601-214524\run-summary.json` |
| Final static readback | `scripts\captures\static-owner-coordinate-chain-readback-20260601-214731-659925\summary.json` |
| Final API reference | `scripts\captures\rift-api-reference-currentpid-12664-20260601-214732.json` |
| API vs chain max abs delta | `0.003935546875027285 <= 0.25` |
| Current-truth apply summary | `.riftreader-local\current-truth-refresh-apply\latest\summary.json` |
| Fresh nav-state readback | `scripts\captures\static-owner-nav-state-20260601-215149-160022\summary.json` |
| Actor no-debug status | `scripts\captures\actor-chain-no-debug-status-20260601-214643-169924\summary.json`; blockers `[]` |
| Navigation dashboard | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |

## Safety notes

- Bounded live input was sent only by the proof-pose batch: two exact-HWND
  `W` pulses of `750ms` each, both with foreground PID/HWND checks passing.
- Final ProofOnly sent no movement and no input.
- No Cheat Engine, x64dbg attach, breakpoints/watchpoints, target memory writes,
  provider writes, push, or branch rewrite were performed.
- `docs\recovery\current-proof-anchor-readback.json` is current for this PID/HWND
  only; old PID `12148` proof-pointer evidence is historical only.
- `tools\riftreader_workflow\current_truth_refresh_plan.py` now updates the
  legacy `currentCoordinateFromPromotedStaticResolver` alias so tracked current
  truth cannot keep a stale coordinate under a current-sounding field.

## Current state

| Surface | State |
|---|---|
| Coordinate resolver | Promoted and current; post-movement readback/API-now agreement passed. |
| Facing/yaw resolver | Promoted static owner chain remains `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`. |
| Proof anchor | Restored for PID `12664` / HWND `0x205146C`; same-target ProofOnly passed. |
| Actor/stat chain | Still not promoted; no-debug status has no proof-anchor blocker now. |
| Turn-rate/support fields | Candidate-only; no turn-rate promotion. |
| Git push | Not performed; branch remains ahead of origin pending explicit push approval. |

## Recommended resume

Resume from `docs\recovery\current-truth.json`,
`docs\recovery\current-proof-anchor-readback.json`, and this handoff. If the
RIFT process restarts, treat `0x1E067A80330` as stale absolute proof evidence
and rerun current-PID proof-anchor recovery rather than reusing it.
