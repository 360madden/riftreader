# RiftReader Handoff — static facing/yaw restart survival propagated — 2026-06-01 17:34 UTC

# **✅ CURRENT RESULT**

Static owner facing/yaw survived the manual RIFT restart and has been propagated into tracked current truth. This was a current-PID reacquisition/update, not a new promotion.

## Repo / Git

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| HEAD before this documentation slice | `f451c14` — `Add post-promotion restart handoff` |
| Worktree state during handoff creation | Dirty by intended propagation/docs/test/helper changes |

## Current target after restart

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `12664` |
| HWND | `0x205146C` |
| Process start UTC | `2026-06-01T17:19:45.159353Z` |
| Module base | `0x7FF6EE5D0000` |
| Owner address | `0x1E067A80010` |

## Proven/promoted chains

| Purpose | Chain / formula | Current status |
|---|---|---|
| Position | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` | Promoted; current PID readback passed |
| Facing target vector | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` | Promoted; restart survival passed |
| Yaw | `atan2(facingZ - playerZ, facingX - playerX)` | Current post-restart yaw `41.29403500816383°` |

## Key evidence

| Evidence | Path / value |
|---|---|
| Restart survival packet | `scripts\captures\facing-target-restart-survival-packet-20260601-172408-160107\summary.json` |
| Coordinate readback | `scripts\captures\static-owner-coordinate-chain-readback-20260601-172308-351318\summary.json` |
| Nav/facing readback | `scripts\captures\static-owner-nav-state-20260601-172308-370480\summary.json` |
| API reference | `scripts\captures\rift-api-reference-currentpid-12664-20260601-172204.json` |
| API-vs-chain max abs delta | `0.00248046875003638` <= `0.25` |
| Navigation dashboard | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Current truth apply | `.riftreader-local\current-truth-refresh-apply\latest\summary.json` |
| Strong recovery doc | `docs\recovery\static-owner-facing-yaw-restart-survival-2026-06-01.md` |
| Workflow study doc | `docs\workflow\static-owner-facing-yaw-discovery-workflow.md` |

## What changed in propagation

| Surface | Result |
|---|---|
| Dashboard facing address | Now derives current `owner+0x30C` when nav-state readback has owner/offset but no explicit facing address. Post-restart address is `0x1E067A8031C`. |
| Current-truth refresh planner | Allows already-promoted facing/yaw dashboard state instead of blocking on `facing-target-promotion-unexpectedly-allowed`. |
| Current truth | Updated from PID `41808` to PID `12664`; facing latest reacquisition status is `promoted-current-pid-refresh`; `promotionState=already-promoted`; `promotionPerformed=false`. |
| Docs | Strong restart-survival evidence doc, workflow study doc, current-truth front matter, and handoff index updated. |

## Safety

- No live input/movement was sent by this propagation slice.
- No x64dbg/Cheat Engine attach, breakpoints, or watchpoints were used.
- No target memory writes were performed.
- No provider repo writes were performed.
- No new proof/facing/actor promotion was performed by the current-truth apply helper.
- Restart was manual/operator-owned.

## Resume checklist

```powershell
cmd /c scripts\riftreader-launcher-inspection.cmd --json
cmd /c scripts\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json
cmd /c scripts\static-owner-nav-now.cmd
cmd /c scripts\riftreader-navigation-pointer-discovery.cmd --json --write
cmd /c scripts\riftreader-workflow-status.cmd --compact-json --write
cmd /c scripts\riftreader-decision-packet.cmd --compact-json --write
```

## Next recommended direction

Use the promoted static owner coordinate and facing/yaw resolvers after exact PID/HWND/process-start/module-base preflight. Keep turn-rate, actor/stat chains, proof anchors, and autonomous route-control automation separate until their own gates pass.
