# RiftReader handoff — current PID 28248 proof anchor and readiness restored

Created UTC: `2026-05-23T05:55:00Z`

## Direct result

The coordinate proof/readiness blocker is resolved for the current live target:

- Process: `rift_x64`
- PID: `28248`
- HWND: `0x2302BC`
- Window geometry: `640x360 / P360C`
- Current proof anchor: `0x2D409F3BBE0`
- Candidate ID: `api-family-hit-000001`
- Proof pointer: `docs/recovery/current-proof-anchor-readback.json`
- Current-truth status: `current_pid_28248_proof_anchor_passed_riftscan_readiness_ready_actor_static_chain_not_promoted`

## What changed

- Refreshed `docs/recovery/current-proof-anchor-readback.json` to the current PID/HWND after approved recovery.
- Refreshed `docs/recovery/current-truth.json` and `docs/recovery/current-truth.md` to make PID `28248` the current truth epoch.
- Archived the prior PID `67680` truth/proof state under `docs/recovery/historical/`.
- Fixed RiftScan/RiftReader coordination parsing so a single-object `api-family-vec3-candidates.jsonl` proof-pointer candidate is treated as a supported candidate when it has the required candidate fields.
- Added regression coverage for that single-object candidate-file case.

## Key artifacts

| Purpose | Artifact |
|---|---|
| Recovery summary | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-28248-20260523-053152-550559/summary.json` |
| Final ProofOnly | `scripts/captures/recover-currentpid-coord-anchor-fast-execute-28248-20260523-053152-550559/07-proofonly/live-test-ProofOnly-20260523-053732/run-summary.json` |
| Proof anchor readback | `scripts/captures/proof-anchor-currentpid-28248-readback-summary-20260523-013808.json` |
| Candidate file | `scripts/captures/family-scan-currentpid-28248-20260523-053403-077701/api-family-vec3-candidates.jsonl` |
| RiftScan milestone review | `scripts/captures/riftscan-milestone-review-20260523-054443.json` |
| Coordinate readiness gate | `scripts/captures/coordinate-proof-readiness-gate-20260523-054451-435504/summary.json` |
| Actor-chain no-debug status | `scripts/captures/actor-chain-no-debug-status-20260523-055040-185416/summary.json` |
| Historical PID 67680 truth JSON | `docs/recovery/historical/current-truth-2026-05-23-pid67680-hwnd120CBE-historical-before-pid28248-proof-refresh.json` |
| Historical PID 67680 truth Markdown | `docs/recovery/historical/current-truth-2026-05-23-pid67680-hwnd120CBE-historical-before-pid28248-proof-refresh.md` |
| Historical PID 67680 proof pointer | `docs/recovery/historical/current-proof-anchor-readback-2026-05-23-pid67680-hwnd120CBE-historical.json` |

## Validation

Passed:

- `python -m unittest scripts.test_riftscan_milestone_review`
- `python -m unittest scripts.test_riftscan_milestone_review scripts.test_riftscan_coordination scripts.test_riftscan_feedback scripts.test_coordinate_proof_readiness_gate`
- `python .\scripts\validate_current_truth.py --json`
- `python .\scripts\coordinate_recovery_status.py --json`
- `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json`
- `git --no-pager diff --check`
- JSON parse checks for current and archived proof/truth files

ChromaLink provider preflight passed:

- `scripts\Ensure-ChromaLinkFresh.cmd --status --wait-fresh --timeout-seconds 20 --json`
- Result: provider fresh, player position fresh, classifier `known-good-p360c`, player position approximately `7371.42, 868.09, 2997.31`.

## Safety ledger

| Operation | Status |
|---|---|
| Cheat Engine | Not used |
| x64dbg/live debugger attach | Not used |
| Breakpoints/watchpoints | Not used |
| Memory writes | Not used |
| Provider writes | Not used |
| Git stage/commit/push | Not used for this handoff |
| Movement/input | Bounded movement was used only in the approved recovery displacement proof; final ProofOnly sent no movement |
| Secrets/private tokens | No key/token/password-like material found in the changed diff; only expected prose matched `authorization` |

## Remaining blockers

Coordinate proof/readiness is no longer blocked. Remaining blockers are actor/static-chain blockers:

- `actor-static-chain-not-reacquired-for-current-pid-28248`
- `blocked-no-debugger-access-provenance`
- `no-module-rva-static-owner-resolver-promoted`
- `no-static-resolver-promoted`
- `not-restart-validated`

## Recommended next action

Continue from the current proof anchor as the safe coordinate baseline. For actor-chain work, reacquire a current-PID actor/static-chain candidate with the lowest-risk no-debug/read-only tools first. Do not promote an actor static chain until resolver, multi-pose API-now vs chain-now, restart/relog, and final ProofOnly gates pass.
