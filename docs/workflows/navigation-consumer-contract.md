# Navigation consumer state contract

## Purpose

`scripts\riftreader-navigation-consumer-state.cmd` emits a small read-only JSON
contract for other local projects that need RiftReader's current navigation
pose. It is the preferred consumer surface before another project builds route
logic on top of this repo.

## Command

```powershell
scripts\riftreader-navigation-consumer-state.cmd --json --write
```

The helper reads the promoted static owner coordinate resolver and promoted
static owner facing/yaw resolver through current-truth preflight. It writes the
latest optional summary to:

```text
.riftreader-local\navigation-consumer-state\latest\summary.json
```

## Stable consumer fields

| Field | Meaning | Consumer rule |
|---|---|---|
| `status` | `passed`, `blocked`, or `failed` | Reject anything except `passed`. |
| `target.processId` / `target.targetWindowHandle` | Exact target identity | Re-check before any live input. |
| `target.processStartUtc` / `target.moduleBase` | Restart/module drift guard | Re-check before any live input. |
| `navigation.position.coordinate` | Current player coordinate from `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` | Usable for route planning when status is `passed`. |
| `navigation.orientation.yawDegrees` | Current yaw from `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` | Usable for bearing/delta planning when status is `passed`. |
| `navigation.diagnostics.turnRate0x304` | Candidate yaw-adjacent scalar | Diagnostic only; never route-control authority. |
| `consumerContract.maxConsumerAgeSeconds` | Freshness budget for consumers | Reject stale payloads. |

## Safety boundary

This helper:

- sends no live input or movement;
- does not attach Cheat Engine or x64dbg;
- does not write target memory;
- does not write provider repos;
- does not apply current truth;
- does not promote proof, actor, facing, or turn-rate truth;
- does not authorize route control.

It may read target memory through the already-promoted resolver to produce a
fresh pose.

## Consumer rule

External projects can use this payload for current position/yaw and dry-run
route planning. They must keep actual movement, turn input, target selection,
ProofOnly, actor-chain promotion, and Git/provider writes behind their own
explicit gates.
