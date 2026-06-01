# RiftReader compact handoff — facing-target promotion readiness

Generated UTC: `2026-06-01T01:47Z`

# **⚠️ BLOCKED-SAFE — ROUTE-ACTIONABLE CANDIDATE, NOT PROMOTION-READY**

This handoff preserves the current navigation-discovery state after the formal
promotion-readiness packet for the closest candidate:

`[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`

The candidate is **route-actionable in the current target epoch**, but remains
**candidate-only**. No current-truth update, proof promotion, actor-chain
promotion, provider write, Cheat Engine, x64dbg attach, or memory write was
performed.

## Repo state before this handoff file

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Pre-handoff HEAD | `1f162be` — `Document camera yaw continuation state` |
| Remote state | `main...origin/main [ahead 4]` before this handoff commit |
| Worktree before writing handoff | Clean |

Newest local commits before this handoff:

| Commit | What |
|---|---|
| `1f162be` | Document camera yaw continuation state |
| `5145e46` | Add camera yaw multipose report mode |
| `60cd32a` | Index camera yaw classification in decision packet |
| `37f60d0` | Add camera yaw handoff next actions |
| `1807db7` | Add camera yaw classification helper |

## Current target and candidate

| Item | Current value |
|---|---|
| Target PID/HWND | PID `25668`, HWND `0x320CB0`, process `rift_x64` |
| Module base | `0x7FF6EE5D0000` |
| Owner root | `[rift_x64+0x32EBC80]` / owner `0x1B53D7806A0` |
| Promoted coordinate chain | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Candidate facing target | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` |
| Candidate turn-rate support | `[rift_x64+0x32EBC80]+0x304` |
| Final readback position | `7264.45068359375, 821.7743530273438, 3005.03125` |
| Final candidate yaw | `49.76603270101203°` |
| Latest candidate facing target | `7270.8857421875, 822.6356811523438, 3012.636962890625` |

## Formal readiness packet

| Artifact | Path |
|---|---|
| JSON packet | `C:\RIFT MODDING\RiftReader\scripts\captures\facing-target-promotion-readiness-20260601-014341-188150\summary.json` |
| Markdown packet | `C:\RIFT MODDING\RiftReader\scripts\captures\facing-target-promotion-readiness-20260601-014341-188150\summary.md` |

Packet result:

| Field | Value |
|---|---|
| Status | `blocked` |
| Verdict | `candidate-route-actionable-but-not-promotion-ready` |
| Gates passed | `6 / 10` |
| Promotion allowed | `false` |
| Promotion performed | `false` |

## Evidence that passed in the current epoch

| Evidence | Result |
|---|---|
| Exact target current PID/HWND | Passed |
| Promoted owner root RVA | Passed |
| Candidate facing offset readback | Passed current epoch |
| Camera/yaw stimulus correlation | Passed current epoch |
| Turn-control convergence | Passed current epoch |
| Route-forward progress | Passed current epoch |

Route-forward progress evidence summarized in the packet:

| Run | Initial distance | Final distance | Progress | Artifact |
|---:|---:|---:|---:|---|
| 1 | `9.962773091846216` | `8.282270278698343` | `1.6805028131478732` | `scripts\captures\static-owner-nav-route-step-20260601-013317-471988\summary.json` |
| 2 | `9.962773091846216` | `8.42438490911677` | `1.538388182729447` | `scripts\captures\static-owner-nav-route-step-20260601-013422-127269\summary.json` |
| 3 | `9.962773091850035` | `8.447021032776163` | `1.515752059073872` | `scripts\captures\static-owner-nav-route-step-20260601-013512-336471\summary.json` |

## Remaining promotion blockers

| Blocker | Meaning |
|---|---|
| `requires-static-root-reference-proof-for-facing-subfields` | Direct refs to `+0x30C/+0x310/+0x314` are still weak/missing; root sweeps did not produce a promotion-ready independent field resolver. |
| `requires-restart-relog-survival` | Need to restart/relog and prove the candidate survives a new target epoch. |
| `requires-formal-three-pose-displacement-gate-packaging` | The three route-forward passes exist but need a dedicated gate packet. |
| `current-truth-json-stale-do-not-promote-from-current-index-alone` | Current truth is stale by dashboard age and must not be treated as promotion evidence. |
| `separate-promotion-approval-and-current-truth-write-not-performed` | Promotion/current-truth write remains a separate gate. |

## Safety boundary

| Boundary | State |
|---|---|
| Packet generation input/movement | None |
| Prior source evidence includes live movement/input | Yes, approved bounded route-step evidence |
| Current-truth write | Not performed |
| Facing/turn-rate promotion | Not performed |
| Actor-chain promotion | Not performed |
| Cheat Engine / x64dbg | Not used |
| Provider writes | None |
| Target memory writes | None |

## Resume checklist

1. Start with this handoff and the readiness packet above.
2. Refresh local status:
   ```powershell
   cd "C:\RIFT MODDING\RiftReader"
   git --no-pager status --short --branch
   cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write
   ```
3. If continuing toward promotion, run restart/relog survival first for
   `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`.
4. After restart/relog, refresh exact-target readbacks and regenerate the
   readiness packet before any promotion discussion.
5. Do not update `docs\recovery\current-truth.*`, run ProofOnly, promote actor
   chains, attach x64dbg/CE, or write provider repos unless that exact boundary
   is explicitly opened.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Run restart/relog survival for the facing-target chain. | Biggest blocker before promotion. |
| 2 | Regenerate the readiness packet after restart/relog. | Confirms evidence survives the new target epoch. |
| 3 | Build a formal three-pose route-progress gate from the three passes. | Converts current movement evidence into a reusable gate. |
| 4 | Re-run pointer-family and owner-batch scans after restart. | Checks whether subfield references remain stable or become discoverable. |
| 5 | Keep `+0x304` as support-only. | Useful cross-check, but ambiguous as a promotion target. |
| 6 | Do one paired turn+forward proof after restart. | Verifies yaw and forward progress still agree. |
| 7 | Refresh current truth only after survival/gate evidence passes. | Prevents candidate evidence from becoming truth prematurely. |
| 8 | Preserve all packet paths in the next current handoff. | Keeps resume context deterministic. |
| 9 | Keep actor-chain work paused. | Facing target is closest to navigation usefulness. |
| 10 | Promote only through a separate proof/promotion gate. | Avoids accidental candidate-to-truth promotion. |

## Handoff boundary

This file is a tracked resume artifact only. It does not authorize future live
input by itself and does not promote any non-coordinate chain.
