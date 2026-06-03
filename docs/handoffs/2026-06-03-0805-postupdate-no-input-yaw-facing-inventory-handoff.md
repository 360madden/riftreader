# Post-update no-input yaw/facing inventory handoff — 2026-06-03 08:05 UTC

## Verdict

The first safe/no-input recovery pass is complete. The old promoted static root
remains blocked, the refreshed coordinate candidate did **not** reacquire on the
current target epoch, and the new status surfaces now expose post-update
yaw/facing seeds as candidate-only inventory.

No live input, movement, route execution, `/reloadui`, screenshot key, x64dbg/CE
attach, target memory write, provider write, current-truth update, ProofOnly,
proof promotion, actor-chain promotion, Git commit, or Git push was performed.

## Current target epoch

| Field | Value |
|---|---|
| Live process | `rift_x64.exe` |
| PID | `77152` |
| HWND | `0x17A0DB2` |
| Process start | `2026-06-02T15:45:29.2617327Z` |
| Module base | `0x7FF7211C0000` |
| Binary path | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| Manifest version | `STABLE-1-1152-a-1256395` |
| Manifest SHA1 | `a8ba8748ea752e4e5581cea34188dc702469c923` |

## Recovery evidence

| Surface | Result |
|---|---|
| Decision packet | `.riftreader-local\decision-packet\latest\decision-packet-compact.json` remains `status=blocked`; blocker `latest-static-owner-readback-root-pointer-null`; safe next action `postupdate-owner-root-rediscovery`. |
| Coordinate candidate refresh | `scripts\captures\postupdate-global-container-coordinate-readback-20260603-074657-625756\summary.json` blocked safely with `global-container-coordinate-leads-missing`; no samples were read. |
| Static access-chain refresh | `scripts\captures\postupdate-static-access-chain-20260603-074712-201893\summary.json` blocked safely with `process-start-mismatch`; it preserved the current game epoch hash/manifest. |
| Rollup | `scripts\captures\postupdate-owner-root-rediscovery-20260603-074732-196871\summary.json` blocked with `no-owner-root-hypothesis-yet` and `process-start-mismatch`. |
| Old promoted root | Preserved blocker: `[rift_x64+0x32EBC80] == 0x0`; do not use old promoted coordinate/facing truth for navigation. |
| Yaw/facing inventory | `postUpdateRecovery.yawFacingCandidates.status=candidate`, `candidateRootCount=1`, `fieldCandidateCount=8`, `routeControlAuthorized=false`, `actionableForNavigation=false`. |
| Candidate root | `rift_x64+0x335F508`, classified `orientation-matrix-root-not-position-root`; keep it as an orientation/facing seed only. |
| Historical facing chain | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` is explicitly `blocked-post-update-old-root-null`. |
| Consumer state | `.riftreader-local\navigation-consumer-state\latest\summary.json` is blocked, surfaces the yaw/facing inventory, and keeps `canExecuteLiveNavigation=false`. |
| Navigation discovery | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` now includes explicit route-control flags: `canExecuteLiveNavigation=false`, `routeControlAuthorized=false`, and `candidateFieldsAuthorizeMovement=false`. |

## Code/status changes

| File | Change |
|---|---|
| `tools\riftreader_workflow\decision_packet.py` | Added `postUpdateRecovery.yawFacingCandidates`, compact counts, and explicit no-route-control flags. |
| `scripts\navigation_consumer_state.py` | Loads the latest post-update yaw/facing inventory into consumer state while preserving candidate-only semantics. |
| `tools\riftreader_workflow\navigation_pointer_discovery.py` | Adds explicit non-authorizing route-control flags to `navigationControlChains`. |
| `docs\schemas\navigation\navigation-consumer-state.schema.json` | Allows `canExecuteLiveNavigation=false` and candidate-only `yawFacingCandidates`. |
| Tests | Added coverage for yaw/facing inventory and route-control blocking. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\decision_packet.py tools\riftreader_workflow\navigation_pointer_discovery.py scripts\navigation_consumer_state.py scripts\test_decision_packet.py scripts\test_navigation_consumer_state.py scripts\test_navigation_pointer_discovery.py` | Passed. |
| `python -m unittest scripts.test_postupdate_global_container_coordinate_readback scripts.test_postupdate_owner_root_rediscovery scripts.test_postupdate_static_access_chain` | Passed: `27` tests. |
| `python -m unittest scripts.test_decision_packet scripts.test_navigation_consumer_state scripts.test_navigation_pointer_discovery` | Passed: `100` tests. |
| `python scripts\navigation_schema_validate.py --schema-key navigation-consumer-state --input .riftreader-local\navigation-consumer-state\latest\summary.json --json` | Passed; `validationErrorCount=0`; summary `scripts\captures\navigation-schema-validation-20260603-080931-942659\summary.json`. |
| `ruff check tools\riftreader_workflow\decision_packet.py tools\riftreader_workflow\navigation_pointer_discovery.py scripts\navigation_consumer_state.py scripts\test_decision_packet.py scripts\test_navigation_consumer_state.py scripts\test_navigation_pointer_discovery.py` | Passed. |
| `git --no-pager diff --check` | Passed. |
| `python tools\riftreader_workflow\validation_ledger.py --tier targeted --command "python -m unittest scripts.test_postupdate_global_container_coordinate_readback scripts.test_postupdate_owner_root_rediscovery scripts.test_postupdate_static_access_chain scripts.test_decision_packet scripts.test_navigation_consumer_state scripts.test_navigation_pointer_discovery"` | Passed in `31.002s`; ledger `.riftreader-local\validation-runs\20260603-080950-908985\summary.md`. |

## Blockers

| Blocker | Meaning |
|---|---|
| `latest-static-owner-readback-root-pointer-null` | Old promoted coordinate/facing root is unusable after the update. |
| `global-container-coordinate-leads-missing` | The 0x32DD7E8 coordinate candidate did not produce usable leads on the current no-input refresh. |
| `process-start-mismatch` | Static-access and rollup helpers still compare against stale 2026-06-01 target metadata while the live PID is the 2026-06-02 process. |
| `no-owner-root-hypothesis-yet` | No replacement owner/root chain is ready for readback, proof, or promotion. |
| `postupdate-yaw-facing-requires-current-readback-and-live-proof` | The 0x335F508 inventory is not route-actionable. |
| `postupdate-yaw-facing-requires-restart-relog-survival-before-promotion` | Restart/relog survival remains gated and should be performed manually by the user first. |

## Next gated action

Do **not** promote or update `current-truth`. The next safe local slice is to
fix the target-epoch mismatch in the post-update static/access helpers so the
current PID/HWND/process-start/module-base can be bound consistently without
movement. After a candidate resolves and matches API/memory within tolerance,
ask before any movement/displacement proof. Restart/relog survival should wait
for a manual user restart/relog.
