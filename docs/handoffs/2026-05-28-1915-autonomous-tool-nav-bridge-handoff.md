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
| Tool workflow | `scripts\riftreader-tool-catalog.cmd --compact-json` reports `26` known tools, `26` existing, `0` missing. |
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

## Additional pushed slices from this handoff continuation

| File | Change |
|---|---|
| `scripts\static_owner_nav_route_run.py` | Route-run reports can now attach checked turn-forward experiment summaries via `--turn-forward-summary-json`. |
| `scripts\test_static_owner_nav_route_run.py` | Added coverage for accepted turn-forward evidence and invalid-path fail-closed behavior. |
| `tools\riftreader_workflow\tool_catalog.py` | Catalogs route-run report as a safe-read-only navigation-report tool and inserts it into the recommended workflow before route reruns. |
| `tools\riftreader_workflow\status_packet.py` | Adds route-run report to compact workflow bridge commands. |

## Post-handoff pushed commits

| Commit | Summary |
|---|---|
| `4215c2f` | Surface static owner readback freshness |
| `d19c5e7` | Assert turn-forward route report output |
| `a19f38f` | Catalog static owner route reports |
| `2690ce3` | Add autonomous tool nav bridge handoff |
| `5966068` | Add turn-forward evidence to route reports |

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
| `python -m unittest scripts.test_status_packet` | Passed: `4` tests after static-owner readback freshness surfacing |
| `python -m unittest scripts.test_tool_catalog scripts.test_status_packet scripts.test_decision_packet` | Passed: `67` tests |
| `python -m unittest scripts.test_status_packet scripts.test_tool_catalog scripts.test_decision_packet` | Passed: `68` tests after static-owner readback freshness surfacing |
| Route-run report CLI with `--turn-forward-summary-json` fixture | Passed; `turnForwardEvidenceCount=1`, contract `passed` |
| `cmd /c scripts\riftreader-tool-catalog.cmd --compact-json` | Passed; `26/26` tools present |
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
| Git remote mutation | Coherent slices were committed and pushed after validation. Latest code pushed head before this docs refresh was `4215c2f`. |

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
| 1 | Continue actor-chain no-debug read-only discovery | It is the next safe pointer-chain lane while proof promotion is blocked. |
| 2 | Add a saved route-report fixture if report evidence expands again | Keeps report replay reviewable without live reruns. |
| 3 | Add current static-readback freshness to compact status if useful | Makes PID `34176` readback evidence easier to see at a glance. |
| 4 | Keep multi-step turn route loops blocked | Prevents candidate yaw from silently becoming full navigation control truth. |
| 5 | Run `riftscan_milestone_review.py` through `python` after every milestone | Required strategy gate after discovery/commit/push. |
| 6 | Keep route-run report review before any route rerun | Avoids wasting live attempts when saved evidence already answers the question. |
| 7 | Tighten actor-chain candidate summaries around proof blockers | Clarifies why actor/stat promotion is not yet allowed. |
| 8 | Refresh static coordinate readback before any movement attempt | Confirms the promoted static chain is still current. |
| 9 | Reacquire fresh proof anchor only with explicit approval | Proof promotion and debugger/watchpoint work remain hard-gated. |
| 10 | If live movement resumes, exact-target and fresh-readback first | Avoids using stale PID/HWND or old proof artifacts as current movement truth. |
