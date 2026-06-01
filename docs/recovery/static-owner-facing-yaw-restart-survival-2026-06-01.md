# Static owner facing/yaw restart survival — 2026-06-01

# **✅ RESULT — STATIC FACING/YAW SURVIVED RESTART**

The promoted static owner facing/yaw chain survived the manual RIFT restart. The heap owner address changed, but the static root RVA and owner-relative offsets remained valid.

| Field | Value |
|---|---|
| Promoted coordinate chain | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Promoted facing/yaw chain | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` |
| Yaw formula | `atan2(facingZ - playerZ, facingX - playerX)` from same-cycle position + facing-target reads |
| Restart survival packet | `C:\RIFT MODDING\RiftReader\scripts\captures\facing-target-restart-survival-packet-20260601-172408-160107\summary.json` |
| Current truth after propagation | `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.json` updated at `2026-06-01T17:33:38Z` |

## Identity transition

| Check | Pre-restart | Post-restart |
|---|---:|---:|
| PID | `41808` | `12664` |
| HWND | `0x2B0A26` | `0x205146C` |
| Process start UTC | `2026-06-01T01:50:50.903773Z` | `2026-06-01T17:19:45.159353Z` |
| Module base | `0x7FF6EE5D0000` | `0x7FF6EE5D0000` |
| Owner address | `0x1E16E8706A0` | `0x1E067A80010` |
| Position offset | `0x320` | `0x320` |
| Facing target offset | `0x30C` | `0x30C` |
| Process start changed | Yes | Proof of restart/relog epoch change |
| Owner address changed | Yes | Confirms no heap address was treated as static |
| Offsets stable | Yes | Static owner-relative layout survived |

## Current post-restart readbacks

| Evidence | Result |
|---|---|
| Static coordinate readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260601-172308-351318\summary.json` — `x=7251.95751953125`, `y=821.4475708007812`, `z=2988.9814453125`; owner `0x1E067A80010`; coordinate address `0x1E067A80330`. |
| Static nav/facing readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260601-172308-370480\summary.json` — yaw `41.29403500816383°`, pitch `-3.5293889576850765°`, planar lookahead `9.980960533731567`, facing target address `0x1E067A8031C` (`owner+0x30C`). |
| RRAPICOORD/API-now reference | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-12664-20260601-172204.json` — API coordinate `7251.96, 821.45, 2988.98`. |
| API-vs-chain tolerance | Max abs delta `0.00248046875003638` <= `0.25`. |
| Navigation dashboard | `C:\RIFT MODDING\RiftReader\.riftreader-local\navigation-pointer-discovery\latest\summary.json` — facing status `promoted-static-owner-facing-yaw-current-pid-readback-passed`; offsetFromOwner `0x30C`. |
| Current-truth apply | `C:\RIFT MODDING\RiftReader\.riftreader-local\current-truth-refresh-apply\latest\summary.json` — `current-truth-refresh-applied`, `trackedTruthWritten=true`, no facing promotion performed by apply helper. |

## Safety / scope

| Surface | Result |
|---|---|
| Live input / movement during restart survival check | None from this packet; restart was manual/operator-owned. |
| Debugger / Cheat Engine | Not used for restart survival. |
| Target memory writes | None. |
| Provider repo writes | None. |
| Proof/facing/actor promotion during propagation | None. Facing/yaw was already promoted by `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-facing-yaw-promoted-2026-06-01.json`; this propagation only refreshed current-PID tracked truth. |
| SavedVariables as live truth | Not used. |

## Interpretation

The important proof is not that the absolute address stayed the same. It did not. The proof is that:

1. `rift_x64+0x32EBC80` reacquired the current owner after restart.
2. The owner heap address changed from `0x1E16E8706A0` to `0x1E067A80010`.
3. Position still resolved at owner `+0x320/+0x324/+0x328`.
4. Facing target still resolved at owner `+0x30C/+0x310/+0x314`.
5. Same-cycle yaw remained sane and came from the facing target vector.
6. Current PID RRAPICOORD/API-now still matched chain-now within tolerance.

## Non-promoted boundaries

- `owner+0x304` remains turn-rate/support only.
- `owner+0x300`, `owner+0x308`, `owner+0x408`, and route-control fields are not promoted.
- Full actor/stat chain is not promoted.
- Proof anchor is not promoted.
- Autonomous route-control automation is not promoted.

## Resume rule

Use the promoted coordinate and facing/yaw resolvers only after exact PID/HWND/process-start/module-base preflight and a fresh static readback. Do not reuse absolute heap addresses across process epochs.
