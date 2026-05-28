# RiftReader compact handoff — autonomous tool and navigation bridge lane

Created UTC: `2026-05-28T19:15:00Z`

# **✅ CURRENT RESULT**

Autonomous safe/offline work continued after the tool audit. The repo is using
the local Python-first control-plane workflow, the live-input surfaces are now
classified with recommended dispositions, static-owner navigation readback is
exposed through the canonical status/tool surfaces, and actor-chain work is kept
separate from promoted coordinate navigation.

| Area | Current state |
|---|---|
| Tool workflow | `scripts\riftreader-tool-catalog.cmd --compact-json` reports `25` known tools, `25` existing, `0` missing. |
| Canonical safe bridge commands | Tool catalog, workflow status, decision packet, live-input audit, static-owner readback, turn-aware planner, actor-chain no-debug status. |
| Promoted coordinate resolver | Static owner coordinate chain remains the promoted navigation coordinate source. |
| Facing / yaw | Candidate-only; usable for bounded turn experiments and dry-run planning, not actor/facing truth promotion. |
| Multi-step turn-aware routing | Fail-closed unless separately designed; dry-run with `--max-route-steps 2` blocks as `multi-step-turn-aware-routing-not-enabled`. |
| Actor/stat chain | Separate no-debug status helper reports candidate evidence only and blocks promotion on `current-proof-anchor-not-passed`. |
| Latest local target evidence | Static owner readback and nav-now helpers can read PID `34176` / HWND `0x3D1544` without input. |
| Historical proof pointer | PID `12148` / HWND `0x640C0C`; stale/superseded, not valid current movement truth. |

## Latest pushed commit stack before this handoff

| Commit | Summary |
|---|---|
| `a681249` | Add actor chain no-debug status bridge |
| `a860858` | Block multi-step turn-aware routing |
| `ca14b55` | Add static owner readback bridge |
| `b2d2003` | Add live-input audit dispositions |
| `c3c463f` | Add RiftReader tool catalog |
| `ce0f1d6` | Add turn forward live proof fixture |
| `fc5abea` | Add static owner turn-aware route experiment |
| `859873f` | Add static owner turn stimulus lane |
| `7234695` | Add compact static owner route run handoff |
| `4d776f1` | Add static owner route run validator |

## Current additional unpushed slice in this handoff

| File | Change |
|---|---|
| `scripts\static_owner_nav_route_run.py` | Route-run reports can now attach checked turn-forward experiment summaries via `--turn-forward-summary-json`. |
| `scripts\test_static_owner_nav_route_run.py` | Added coverage for accepted turn-forward evidence and invalid-path fail-closed behavior. |

## Important commands

| Purpose | Command |
|---|---|
| Compact decision packet | `cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write` |
| Compact workflow status | `cmd /c scripts\riftreader-workflow-status.cmd --compact-json` |
| Tool catalog | `cmd /c scripts\riftreader-tool-catalog.cmd --compact-json` |
| No-input static readback | `cmd /c scripts\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json` |
| No-input nav/facing readback | `cmd /c scripts\static-owner-nav-now.cmd` |
| Dry-run turn-aware plan | `cmd /c scripts\static-owner-turn-aware-route-plan.cmd --destination-x 7256.371343 --destination-z 3005.467139 --destination-label prior-turn-forward-target --arrival-radius 2.0 --alignment-threshold-degrees 15 --json` |
| Actor-chain no-debug status | `cmd /c scripts\riftreader-actor-chain-no-debug-status.cmd --json` |
| Route-run report with turn-forward evidence | `cmd /c scripts\static-owner-nav-report-route-run.cmd scripts\navigation\testdata\static-owner-nav-route-run-summary-arrived.json --turn-forward-summary-json scripts\navigation\testdata\static-owner-turn-forward-experiment-summary-progress.json --json` |

## Validation evidence in this lane

| Validation | Result |
|---|---|
| `python -m unittest scripts.test_static_owner_nav_route_run` | Passed: `14` tests |
| Route-run report CLI with `--turn-forward-summary-json` fixture | Passed; `turnForwardEvidenceCount=1`, contract `passed` |
| `cmd /c scripts\riftreader-tool-catalog.cmd --compact-json` | Passed earlier in lane; `25/25` tools present |
| `cmd /c scripts\riftreader-workflow-status.cmd --compact-json` | Passed; worktree clean before this slice, latest pushed HEAD `a681249` |
| `cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write` | Passed; safe next action was compact workflow status |

## Safety ledger

| Boundary | Status |
|---|---|
| Live movement/input in this slice | Not sent. |
| Cheat Engine / x64dbg / debugger attach | Not used. |
| Provider repo writes | Not done. |
| ProofOnly / proof promotion | Not run. |
| Actor/facing promotion | Not done. |
| SavedVariables as live truth | Not used. |
| Git remote mutation | Previous coherent slices were pushed after validation; this handoff slice is ready for validation/commit/push. |

## Current blockers / guardrails

| Blocker | Meaning |
|---|---|
| `current-proof-anchor-not-passed` | Actor/stat chain remains candidate-only until proof gates are current. |
| `multi-step-turn-aware-routing-not-enabled` | Multi-step route-loop turn control is intentionally blocked, even with candidate turn-control approval. |
| Historical proof pointer stale | Do not reuse PID `12148` / HWND `0x640C0C` for live truth. |
| Candidate yaw only | `+0x30C/+0x310/+0x314` can guide dry-run/experiment evidence but is not promoted facing truth. |

## Recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Validate and commit the route-run report turn-forward evidence slice | It makes the latest turn-forward proof reviewable without live reruns. |
| 2 | Run broad nav/recovery tests after commit candidate | Catches import/circular-contract regressions around report/turn helpers. |
| 3 | Refresh `riftreader-decision-packet` with safe checks | Ensures the control plane still sees a coherent commit-ready state. |
| 4 | Run `riftscan_milestone_review.py` through `python` | Required strategy gate after major discovery/commit milestones. |
| 5 | Keep multi-step turn route loops blocked | Prevents candidate yaw from silently becoming full navigation control truth. |
| 6 | Add a route-run replay fixture that includes turn-forward evidence | Lets report output stay regression-safe. |
| 7 | Add richer route report Markdown assertions | Ensures operator-facing evidence stays compact and complete. |
| 8 | Continue actor-chain no-debug read-only discovery | It is the next safe pointer-chain lane while proof promotion is blocked. |
| 9 | Reacquire fresh proof anchor only with explicit approval | Proof promotion and debugger/watchpoint work remain hard-gated. |
| 10 | If live movement resumes, exact-target and fresh-readback first | Avoids using stale PID/HWND or old proof artifacts as current movement truth. |
