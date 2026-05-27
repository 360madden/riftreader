# RiftReader handoff — current PID 12148 candidate found; movement/displacement now recommended

Created local: `2026-05-26T22:19:00-04:00`
Created UTC: `2026-05-27T02:19:00Z`

## Direct result

The no-movement current-PID proof-recovery lane found a candidate coordinate triplet for current PID `12148`. This is still **candidate-only proof-anchor recovery**, not a promoted proof pointer and not a player actor static chain.

Movement/displacement stimulus testing is now the optimal next step because a current-PID candidate JSONL exists and the candidate initially matches fresh ChromaLink API-now coordinates.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Title | `RIFT` |
| Responding | `true` |
| Process start | `2026-05-26T21:17:01.2653526-04:00` |

## Candidate found

| Field | Value |
|---|---|
| Candidate ID | `api-family-hit-000001` |
| Candidate address | `0x23863A26E50` |
| Base address | `0x238639D0000` |
| Offset | `0x56E50` |
| Axis order | `xyz` |
| Memory XYZ | `7260.45947265625`, `821.4298095703125`, `2990.651611328125` |
| Reference XYZ | `7260.46`, `821.43`, `2990.65` |
| Max abs delta | `0.0016113281249090505` |
| Candidate JSONL | `scripts/captures/family-scan-currentpid-12148-20260527-021805-433332/api-family-vec3-candidates.jsonl` |
| Scan summary | `scripts/captures/family-scan-currentpid-12148-20260527-021805-433332/family-scan-summary.json` |

## Recovery run

| Field | Value |
|---|---|
| Run directory | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-021502-376684` |
| Status | `blocked` |
| Blocker | `movement-approval-required-for-displaced-pose-validation` |
| ChromaLink reference | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-021502-376684/02-reference-chromalink/rift-api-reference-currentpid-12148-20260527-021521-220219.json` |
| Scan-plan JSON | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-021502-376684/03-memory-inventory/memory-region-inventory-currentpid-12148-20260527-021521-486154/scan-plan.json` |
| Best scan range | rank `12`, `0x238639D0000`-`0x238649E0000` |
| Scan-plan result | passed with 1 hit, then blocked before movement because movement was not approved |

## Current proof-anchor state

| Item | Status |
|---|---|
| Tracked proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Status | still `blocked-target-drift` |
| Artifact target | historical PID `28248`, HWND `0x2302BC` |
| Live target | PID `12148`, HWND `0x640C0C` |
| Movement allowed | false |
| Current truth updated | false |
| ProofOnly run | false |

## Movement / displacement recommendation

Movement/displacement testing is **now recommended** for multi-pose validation.

Recommended next command shape, only if movement is approved:

```powershell
cd "C:\RIFT MODDING\RiftReader"
python .\scripts\recover_current_pid_coord_anchor_fast.py --pid 12148 --hwnd 0x640C0C --process-name rift_x64 --scan-stride 1 --scan-tolerance 2.0 --scan-plan-top-count 80 --max-seconds-per-scan-range 25 --movement-approved --execute --json
```

Do not add `--allow-current-truth-update` or `--run-proofonly` until multi-pose displacement validation succeeds and promotion is explicitly approved.

## Safety ledger

| Operation | Status |
|---|---|
| Target-control/visual gate | passed |
| ChromaLink API reference | passed |
| Current-PID memory inventory/read | used |
| Candidate scan | passed with 1 hit |
| Movement/game input | not used |
| x64dbg/debugger attach | not used |
| Breakpoints/watchpoints | not used |
| Cheat Engine | not used |
| Memory writes | not used |
| Provider writes | not used |
| Current-truth/proof promotion | not used |
| ProofOnly | not used |
| Git stage/commit/push | not used |

## Top 10 recommended next actions

1. Approve bounded movement/displacement validation if ready.
2. Use only the current PID `12148` / HWND `0x640C0C` target; fail closed on drift.
3. Recheck ChromaLink freshness immediately before movement validation.
4. Validate candidate `0x23863A26E50` across at least two displaced API poses.
5. Reject visual-only movement if API planar displacement is below threshold.
6. Do not promote after a single pose; require same-candidate multi-pose tracking.
7. Keep `--allow-current-truth-update` off until validation passes.
8. Keep `--run-proofonly` off until promotion is approved and complete.
9. Keep actor static-chain promotion separate; this candidate is proof-anchor candidate evidence only.
10. If movement validation fails, inspect whether this is an API-buffer/copy family before using x64dbg.
