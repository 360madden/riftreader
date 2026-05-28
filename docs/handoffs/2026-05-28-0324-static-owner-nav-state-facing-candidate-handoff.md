# RiftReader handoff — static owner nav-state + facing candidate

Created UTC: `2026-05-28T03:24:07Z`

# **✅ DIRECT RESULT**

The promoted static coordinate resolver is now wired into a repeatable navigation-state readback, and the strongest yaw/facing candidate has live turn-response evidence.

This handoff is intentionally scoped as **resolver-backed navigation polling and facing discovery**. It does **not** promote a full actor/stat chain.

## Current truth snapshot

| Need | Current state |
|---|---|
| Current position | Promoted static resolver: `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Facing / yaw | Candidate-only readback: `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` as a facing-target coordinate |
| Yaw formula | `atan2((owner+0x314)-(owner+0x328), (owner+0x30C)-(owner+0x320))` |
| Movement response | Partially proven by live forward displacement and turn-only yaw response |
| Stuck detection | Not integrated yet; polling analysis now exposes deltas needed for it |
| Arrival detection | Not implemented yet; should use resolver-backed polling loop |
| Route control | Not implemented yet; requires exact-target preflight + fresh readback per loop |
| Safety stop / key release | Still hard-gated; no route automation promoted |

## Live target used for this slice

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `34176` |
| HWND | `0x3D1544` |
| Process start UTC | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` |
| Window title | `RIFT` |

## What changed

| Commit | Summary |
|---|---|
| `0660245` | Added `state` mode to `scripts/static_owner_facing_discovery.py`, producing current position + candidate yaw/facing with exact target checks and sample analysis. |
| `886a4fc` | Recorded the live nav-state turn-response evidence in `docs/recovery/static-owner-nav-state-readback-2026-05-28.*`. |

Key command now available:

```powershell
python scripts\static_owner_facing_discovery.py state --samples 5 --interval-seconds 0.1 --expect-stationary --json
```

## Evidence summary

| Evidence | Result |
|---|---|
| No-input nav-state poll | Passed: stable coordinate, stable yaw, no blockers |
| Before turn state | `x=7260.65576171875, y=821.4660034179688, z=2989.657470703125`, yaw `83.64698580993692` |
| Stimulus | `right` for `250` ms, exact-target window-message input |
| Frame change | `60.7778%` |
| After turn state | `x=7260.65576171875, y=821.4660034179688, z=2989.657470703125`, yaw `131.64771257433102` |
| Yaw delta | `48.0007267643941` degrees |
| Coordinate planar drift during turn | `0.0` |
| Lookahead distance | Before `9.99914895549015`, after `9.999296488453382` |

Interpretation: the candidate facing target changes strongly on turn input while position remains stationary, which is the expected signal for yaw/facing.

## Artifacts

| Artifact | Path |
|---|---|
| Facing candidate report | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-facing-candidate-2026-05-28.json` |
| Nav-state response JSON | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-nav-state-readback-2026-05-28.json` |
| Nav-state response Markdown | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-nav-state-readback-2026-05-28.md` |
| Latest before-state summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260528-031944-060785\summary.json` |
| Latest after-state summary | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260528-032009-849296\summary.json` |

## Validation already run

| Validation | Result |
|---|---|
| `python -m py_compile scripts\static_owner_coordinate_chain_readback.py scripts\static_owner_facing_discovery.py scripts\test_static_owner_coordinate_chain_readback.py scripts\test_static_owner_facing_discovery.py` | Passed |
| `python -m unittest scripts.test_static_owner_coordinate_chain_readback scripts.test_static_owner_facing_discovery scripts.test_static_chain_promotion_readiness scripts.test_coordinate_recovery_status` | Passed: `26 tests OK` |
| `python -m json.tool docs\recovery\static-owner-nav-state-readback-2026-05-28.json` | Passed |
| `git --no-pager diff --check` | Passed; only LF/CRLF warnings before commit |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed |
| `python tools\riftreader_workflow\decision_packet.py --json` | Passed; warning remains `proof-anchor-stale-superseded-by-promoted-static-resolver` |
| `python scripts\riftscan_milestone_review.py --pid 34176 --hwnd 0x3D1544 --process-name rift_x64 --compact-json` | Blocked as expected for RiftScan/proof-pointer strategy: stale proof pointer still targets PID `12148` / HWND `0x640C0C`; do not use that pointer for this live target. |

## Safety ledger

| Operation | Status |
|---|---|
| Live input | Sent with approval: bounded turn pulse only after exact PID/HWND bind/focus/capture |
| Route control | Not used |
| Continuous movement loop | Not used |
| Cheat Engine | Not used |
| x64dbg/debugger attach | Not used |
| Breakpoints/watchpoints | Not used |
| Target memory writes | Not used |
| Provider writes | Not used |
| Facing/yaw promotion | Not done |
| Full actor/stat-chain promotion | Not done |

## Newest 10 commits reviewed for resume context

| # | Commit |
|---:|---|
| 1 | `886a4fc Record static owner nav-state response evidence` |
| 2 | `0660245 Add static owner nav-state readback` |
| 3 | `c4be34c Expand static owner coordinate readback polling` |
| 4 | `af93de8 Add compact static resolver promotion handoff` |
| 5 | `e00b56c Promote static player coordinate resolver` |
| 6 | `81fd0ba Add static chain refresh approval request` |
| 7 | `13b7b35 Surface RRAPICOORD scan evidence in readiness` |
| 8 | `a97e631 Add RRAPICOORD scan diagnostic step` |
| 9 | `1d849ac Fix API reference capture defaults` |
| 10 | `537788e Document reloadui hotbar refresh gate` |


## Git state at handoff creation

```text
## main...origin/main [ahead 2]
```

Head before this handoff commit: `886a4fc Record static owner nav-state response evidence`

## Resume guidance

1. Treat `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` as the promoted current-position resolver.
2. Treat `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` as the strongest **candidate** facing/yaw source, not promoted truth.
3. Before any live input or route loop, exact-target PID/HWND/process-start/module-base and run a fresh state readback.
4. Do not promote full actor/stat chain from this evidence.
5. Do not use CE/x64dbg unless explicitly re-authorized.
6. Do not consume the historical `current-proof-anchor-readback.json` pointer for this target; it still records PID `12148` / HWND `0x640C0C` and is superseded by the promoted static resolver.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Run one more bounded left/right/forward repeat with `state` before promotion | Gives final multi-stimulus proof for yaw/facing. |
| 2 | Promote only the facing/yaw candidate after explicit approval | Keeps truth narrow and prevents accidental full actor-chain promotion. |
| 3 | Add a small `position+yaw now` wrapper over the `state` command | Gives navigation code a stable, simple entrypoint. |
| 4 | Add signed yaw-delta normalization to the state output | Route control needs shortest-turn calculations. |
| 5 | Add velocity/speed fields from consecutive coordinate samples | Enables movement response and stuck detection. |
| 6 | Implement stuck/overshoot/timeout thresholds in the polling layer | Prevents runaway route behavior. |
| 7 | Build a dry-run route controller that consumes recorded state samples | Tests control logic without live input risk. |
| 8 | Validate one tiny live waypoint only after exact-target preflight and hard key-release gate | Proves closed-loop navigation safely. |
| 9 | Keep API/RRAPICOORD as independent audit, not primary nav source | Static resolver is primary; API remains drift/freshness check. |
| 10 | After push, verify remote HEAD and preserve this handoff as newest resume artifact | Ensures the next session starts from current evidence. |
