# Navigation & Route Execution

**What this covers:** Route planning, turn-aware routing, and executing multi-step
navigation routes using the promoted static resolver and C# SendInput.

**When to use:** Any live navigation — waypoint following, route execution,
movement smoke tests.

---

## Architecture

```
Readback pipeline              Route pipeline              Input pipeline
    (read-only)                 (plan + execute)           (SendInput)
       │                            │                          │
static_owner_coordinate     static_owner_turn_          RiftReader.SendInput
_chain_readback.py          aware_route_plan.py          (ScanCode keys)
       │                            │                          │
       ├── coords (0x320)    ────► bearing calc     ────► W/S keys
       ├── yaw (atan2)       ────► turn direction     ────► A/D keys
       ├── turn rate (0x304) ────► turn cross-check      (key press pulse)
       └── facing (0x30C)         route plan output
```

## Quick commands

### Read player position + orientation
```bash
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --nav-state --json
```

### Dry-run route plan (no movement)
```bash
python scripts/static_owner_turn_aware_route_plan.py \
  --use-current-truth --waypoint-file <route.json> --json
```

### Execute single route step
```bash
python scripts/static_owner_nav_route_step.py \
  --use-current-truth --route-file <route.json> --json
```

### Execute continuous multi-step route
```bash
python scripts/static_owner_continuous_route_runner.py \
  --use-current-truth --route-file <route.json> --movement-approved --json
```

---

## Turn-aware routing

The route planner computes bearing from player position to waypoint, derives yaw from the
facing target chain, and determines turn direction:

1. **Bearing:** `atan2(waypointZ - playerZ, waypointX - playerX)`
2. **Yaw:** `atan2(Z_at_0x314 - playerZ, X_at_0x30C - playerX)` (from promoted resolver)
3. **Turn delta:** normalized angle difference between yaw and bearing
4. **Engine cross-check:** 0x304 turn rate sign must agree with atan2 direction

If delta > threshold: route plan outputs turn direction (left/right) and degrees.
If delta ≤ threshold: player is aligned, proceed to forward movement.

**Blocker:** `turn-direction-mismatch` — atan2 says "left" but engine 0x304 turn rate
says "right". This means the player is mid-turn or the facing data is ambiguous.

---

## Route step execution

Each step:
1. Read current position + yaw (fresh chain readback)
2. Compute bearing to waypoint
3. If bearing not aligned → send turn key, verify convergence
4. If aligned → send W key for configured duration
5. Re-read position, check progress toward waypoint
6. If arrived (within radius) → next waypoint
7. If no progress → block with terrain sub-classification

---

## Current limitations

| Limitation | Status | Mitigation |
|---|---|---|
| Turn completion not verified | 🔴 #3 pending | Pulse-loop convergence check needed |
| No stuck-state recovery | 🟡 Planned | Back up + strafe on terrain block |
| Facing target zero-vector after zone-in | ✅ Guard #2 | `navStateError: facing-target-zero-vector` |
| Stale module base after restart | ✅ Guard #1 | `moduleBaseCheck` freshness gate |

## Route file format

```json
{
  "schemaVersion": 1,
  "waypoints": [
    {"x": 7265.0, "y": 821.5, "z": 3010.0, "radius": 0.75},
    {"x": 7270.0, "y": 821.5, "z": 3020.0, "radius": 0.75}
  ]
}
```

## Movement safety gates

All live movement requires:
1. `--movement-approved` flag (explicit human approval each session)
2. Module base freshness gate passes (live module base matches `current-truth.json`)
3. Facing target non-zero (zone-in state blocked)
4. Exact PID/HWND/process-start match to `current-truth.json`
5. No Cheat Engine, no x64dbg, no SavedVariables-as-live-truth

## Anti-patterns

| Don't | Use instead |
|---|---|
| Move without fresh chain readback | Always `--nav-state` before any W/S key |
| Trust old PID proof anchors | Module-RVA resolver (`0x32EBC80`) survives restarts |
| Send turn keys without convergence check | #3 turn completion detector (pending) |
| Treat `ReaderBridgeExport.lua` as live IPC | SavedVariables update only on `/reloadui`/logout |

## Related docs

> **Note:** Legacy route/turn contracts live under `docs/workflow/` (singular),
> predating this `docs/workflows/` directory. They remain authoritative for
> their specific contracts.

- Turn-aware route contract: `docs/workflow/static-owner-turn-aware-route-contract.md`
- Route step contract: `docs/workflow/static-owner-nav-route-contract.md`
- Turn stimulus contract: `docs/workflow/static-owner-turn-stimulus-contract.md`
