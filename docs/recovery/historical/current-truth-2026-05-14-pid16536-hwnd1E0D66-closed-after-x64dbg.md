# RiftReader Current Truth

_Last updated: 2026-05-14T18:36:23Z._

## Verdict

**Current coordinate proof is promoted for PID `16536` / HWND `0x1E0D66`.** The current proof pointer is **`snapshot-delta-21487DF8F64-xyz` at `0x21487DF8F64`** and latest same-target `ProofOnly` passed at `2026-05-14T17:46:22.783527+00:00` with `movementSent=false`.

PID `2928` / HWND `0xC0994` is now **historical/stale only**. Its prior `api-family-hit-000001` / `0x268E2BC09E0` state was candidate-only and displacement-gate-blocked; do not use that PID `2928` state as current coordinate proof or movement truth.

## Current target epoch

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `16536` |
| HWND | `0x1E0D66` |
| Window title | `RIFT` |
| Process start | `2026-05-14T14:10:35.2003782Z` |
| Module base | `0x7FF71CD90000` |
| Proof pointer status | `current-target-proofonly-passed` |
| Proof pointer updated | `2026-05-14T17:46:22.792929+00:00` |

## Current coordinate proof pointer

| Field | Value |
|---|---|
| Candidate | `snapshot-delta-21487DF8F64-xyz` |
| Address | `0x21487DF8F64` |
| Source base / offset | `0x21487DF0000` / `0x8F64` |
| Axis order | `xyz` |
| Candidate file | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/candidate-vec3.json` |
| Candidate JSONL | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/candidate-vec3.jsonl` |
| Readback summary | `scripts/captures/proof-anchor-currentpid-16536-readback-summary-20260514-134617.json` |
| Proof anchor cache | `scripts/captures/telemetry-proof-coord-anchor.json` |
| Current coordinate | `x=7404.44091796875, y=871.7135009765625, z=3028.63232421875` |
| Coordinate recorded | `2026-05-14T17:46:22.1910144Z` |
| Stable readback samples | `true` (`DecodedSampleCount=3`, `MaxAbsDeltaAcrossReadbackSamples=0.0`) |
| Movement allowed by coordinate proof gate | `true` |
| Latest ProofOnly movement sent | `false` |
| Cheat Engine used | `false` |
| SavedVariables used as live truth | `false` |

## Fresh validation

| Check | Result | Artifact |
|---|---|---|
| Same-target `ProofOnly` | `passed-proof-only` | `scripts/captures/live-test-ProofOnly-20260514-174521/run-summary.json` |
| Target control | `passed-target-control` / `exact-hwnd-foreground` | `scripts/captures/live-test-ProofOnly-20260514-174521/target-control/target-control-status.json` |
| Current proof-anchor readback | `valid` / `MovementAllowed=true` | `scripts/captures/proof-anchor-currentpid-16536-readback-summary-20260514-134617.json` |
| Coordinate proof route | `api-memory-match` | `scripts/captures/coordinate-proof-route-20260514-163509-016518/coordinate-proof-route.json` |
| Promotion batch | `promotion-candidate-found` | `scripts/captures/current-pid-coordinate-anchor-batch-16536-live-approved-route-20260514-163620/coordinate-anchor-batch-summary.json` |
| Grouped three-pose family snapshot | `passed` | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/summary.json` |
| Delta analysis | `passed` | `scripts/captures/family-snapshot-sequence-currentpid-16536-live-approved-threepose-20260514-122550-422022/delta-analysis/delta-summary.json` |
| Prior bounded movement smoke | `Forward250` artifact retained as prior proof evidence | `scripts/captures/live-test-Forward250-20260514-164220/run-summary.json` |

## Historical / stale PID 2928 state

| Item | Historical status | Reuse policy |
|---|---|---|
| PID `2928` / HWND `0xC0994` current-truth state | **historical / stale** | Audit and broad reacquisition-history context only. |
| Prior best candidate | `api-family-hit-000001` at `0x268E2BC09E0` | Do **not** use as current proof. |
| Prior movement state | `blocked-promotion-readiness`; movement blocked | Superseded by PID `16536` proof pointer. |
| Historical current-truth archive | `docs/recovery/historical/current-truth-2026-05-14-pid2928-hwndC0994-historical.md` | Human-readable stale snapshot. |
| Historical current-truth JSON archive | `docs/recovery/historical/current-truth-2026-05-14-pid2928-hwndC0994-historical.json` | Machine-readable stale snapshot. |
| Historical proof-pointer archive | `docs/recovery/historical/current-proof-anchor-readback-2026-05-14-pid2928-hwndC0994-historical.json` | Stale target-epoch pointer archive only. |

## Freshness invariant

PID/HWND/process-start matching is targeting preflight only. Current coordinate truth requires a fresh proof surface and same-target readback. The canonical current coordinate source is now the PID `16536` proof-anchor readback above. If PID/HWND changes, proof age expires, or `ProofOnly` fails, this pointer becomes stale and movement must fail closed until the current-PID family recovery path promotes a new proof pointer.

## Live testing boundary

| Lane | Status | Notes |
|---|---|---|
| Read-only API/runtime coordinate refresh | Allowed | Continue to use live runtime/API surfaces; never SavedVariables as live truth. |
| Same-target `ProofOnly` | Allowed and required before new movement if freshness is uncertain | Latest passed for PID `16536`. |
| Coordinate proof movement gate | **Satisfied for PID `16536`** | Proof pointer says `MovementAllowed=true`; latest ProofOnly itself sent no movement. |
| Movement / navigation input | Requires per-run safety gates | Exact target and profile-specific visual/input gates still apply. |
| CE/x64dbg attach/watchpoints | Blocked unless explicitly reauthorized | No CE/x64dbg was used for this promotion. |
| Actor-facing / auto-turn truth | Not promoted by this coordinate update | Re-prove separately before auto-turn. |

## Still-valid local visual fact

The native RIFT screenshot keybind remains `NUM PAD *` / `VK_MULTIPLY` / `0x6A` for this machine. This is **visual evidence only**, not coordinate or movement truth.

## Canonical artifacts

| Artifact | Path |
|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` |
| Current truth JSON | `docs/recovery/current-truth.json` |
| Current handoff | `docs/handoffs/2026-05-14-1711-current-pid-coordinate-proof-restored.md` |
| Current discovery tutorial HTML | `docs/recovery/current-pid-coordinate-proof-anchor-discovery-2026-05-14.html` |
| Current discovery tutorial Markdown | `docs/recovery/current-pid-coordinate-proof-anchor-discovery-2026-05-14.md` |
| Historical proof-anchor timeline HTML | `docs/recovery/historical-coordinate-proof-anchor-discovery-timelines-2026-05.html` |
| Historical proof-anchor timeline Markdown | `docs/recovery/historical-coordinate-proof-anchor-discovery-timelines-2026-05.md` |
| Historical proof-anchor timeline machine Markdown | `docs/recovery/historical-coordinate-proof-anchor-discovery-timelines-2026-05.machine.md` |

## Current blockers / cautions

- No active coordinate-proof-anchor blocker for PID `16536` as of latest `ProofOnly`.
- Before any new movement run, re-check exact target and rerun `ProofOnly` if proof age or target identity is not fresh.
- This coordinate proof does not promote actor-facing, auto-turn, or static owner-chain truth.

## Next recommended action

Use PID `16536` / HWND `0x1E0D66` as the current coordinate proof target. Before any new live movement, rerun `ProofOnly` if target identity or proof age is not fresh, and keep PID `2928` artifacts historical/stale only.
