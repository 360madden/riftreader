# RiftReader handoff — current PID 12148 candidate reconfirmed; movement gate reached

Created local: `2026-05-27T01:58:00-04:00`
Created UTC: `2026-05-27T05:58:00Z`

## Direct result

The policy patch was committed first as `54b6a0b Document no-movement current-PID recovery lane`.

After that commit, the no-movement current-PID proof-recovery lane was resumed for
the live RIFT target and reconfirmed the same current-PID coordinate candidate:
`api-family-hit-000001` at `0x23863A26E50`.

The helper stopped correctly at
`movement-approval-required-for-displaced-pose-validation`. This is still
**candidate-only proof-anchor recovery**, not a promoted proof pointer, not a
ProofOnly pass, and not a player actor static chain.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12148` |
| HWND | `0x640C0C` |
| Title | `RIFT` |
| Responding | `true` |
| Process start | `2026-05-26T21:17:01.2653526-04:00` |
| Visible target count | `1` |

## Latest no-movement recovery run

| Field | Value |
|---|---|
| Run directory | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-055324-598784` |
| Status | `blocked` |
| Blocker | `movement-approval-required-for-displaced-pose-validation` |
| Summary JSON | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-055324-598784/summary.json` |
| Summary Markdown | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-055324-598784/summary.md` |
| ChromaLink reference | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-055324-598784/02-reference-chromalink/rift-api-reference-currentpid-12148-20260527-055350-672935.json` |
| Scan-plan JSON | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-12148-20260527-055324-598784/03-memory-inventory/memory-region-inventory-currentpid-12148-20260527-055350-936452/scan-plan.json` |
| Candidate JSONL | `scripts/captures/family-scan-currentpid-12148-20260527-055521-760269/api-family-vec3-candidates.jsonl` |
| Scan summary | `scripts/captures/family-scan-currentpid-12148-20260527-055521-760269/family-scan-summary.json` |

## Candidate reconfirmed

| Field | Value |
|---|---|
| Candidate ID | `api-family-hit-000001` |
| Candidate address | `0x23863A26E50` |
| Base address | `0x238639D0000` |
| Offset | `0x56E50` |
| Axis order | `xyz` |
| Memory XYZ | `7259.1396484375`, `821.6771240234375`, `2987.29736328125` |
| Delta X/Y/Z | `-0.0003515625003274181`, `-0.002875976562449978`, `-0.002636718750181899` |
| Max abs delta | `0.002875976562449978` |
| Best scan range | rank `8`, `0x238639D0000`-`0x238649E0000` |
| Scan-plan result | passed with `1` hit, then blocked before movement because movement was not approved |

## Current proof-anchor state

| Item | Status |
|---|---|
| Tracked proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Status | still `blocked-target-drift` |
| Artifact target | historical PID `28248`, HWND `0x2302BC` |
| Live target | PID `12148`, HWND `0x640C0C` |
| Movement allowed | `false` |
| Current truth updated | `false` |
| ProofOnly run | `false` |

## RiftScan strategy checkpoint

`scripts/riftscan_milestone_review.py` was run after the commit/recovery
milestone with the current PID/HWND. It remained read-only and wrote
RiftReader-owned summaries only.

| Field | Value |
|---|---|
| Status | `blocked` |
| Decision | `block` |
| Main blockers | missing selected RiftScan candidate; current proof pointer target mismatch |
| Pointer mismatch | artifact `28248` / `0x2302BC` vs requested `12148` / `0x640C0C` |
| Summary JSON | `scripts/captures/riftscan-milestone-review-20260527-055547.json` |
| Summary Markdown | `scripts/captures/riftscan-milestone-review-20260527-055547.md` |

This checkpoint does **not** invalidate the local current-PID candidate. It means
RiftScan provider evidence is not currently a promotion/readiness source for
this target, and the tracked proof pointer is still stale.

## Movement / displacement recommendation

Movement/displacement testing is now the next required evidence step for
multi-pose validation. It requires explicit approval before running.

Recommended command shape, only if movement is approved:

```powershell
cd "C:\RIFT MODDING\RiftReader"
python .\scripts\recover_current_pid_coord_anchor_fast.py --pid 12148 --hwnd 0x640C0C --process-name rift_x64 --scan-stride 1 --scan-tolerance 2.0 --scan-plan-top-count 80 --max-seconds-per-scan-range 25 --movement-approved --execute --json
```

Do not add `--allow-current-truth-update` or `--run-proofonly` until displaced
multi-pose validation succeeds and promotion is explicitly approved.

## Safety ledger

| Operation | Status |
|---|---|
| Policy patch commit | `54b6a0b` |
| Target discovery | passed |
| Target-control/visual gate | passed |
| ChromaLink API reference | passed |
| Current-PID memory inventory/read | used |
| Candidate scan | passed with `1` hit |
| Movement/game input | not used |
| x64dbg/debugger attach | not used |
| Breakpoints/watchpoints | not used |
| Cheat Engine | not used |
| Memory writes | not used |
| Provider writes | not used |
| Current-truth/proof promotion | not used |
| ProofOnly | not used |
| Git push | not used |

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Approve bounded movement/displacement validation if ready. | The no-movement lane has reconfirmed a current candidate and is now blocked at the correct movement gate. |
| 2 | Keep the exact current target `12148` / `0x640C0C`; fail closed on drift. | The tracked proof pointer is still for historical PID `28248`. |
| 3 | Re-run the fast helper with `--movement-approved` only, not promotion or ProofOnly flags. | Movement validation, proof promotion, and ProofOnly remain separate gates. |
| 4 | Require at least two displaced API-coordinate poses before promotion. | A single-pose match is candidate evidence only. |
| 5 | Reject any run where visual change occurs without API planar displacement. | It prevents camera/UI changes or blocked movement from being mistaken for coordinate proof. |
| 6 | Promote only if the same candidate address tracks API-now after displacement. | This proves the candidate is tied to the live coordinate source across poses. |
| 7 | After successful multi-pose validation, ask separately before `--allow-current-truth-update`. | Current proof pointer updates are repo truth changes. |
| 8 | After promotion, ask separately before `--run-proofonly`. | ProofOnly is its own live proof gate. |
| 9 | Keep RiftScan read-only unless separately authorized. | The milestone review shows no current selected provider candidate for this PID/HWND. |
| 10 | Keep actor static-chain work separate from this proof-anchor candidate lane. | This candidate is a current-PID proof-anchor candidate, not actor static-chain truth. |
