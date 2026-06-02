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
       ├── 0x304 scalar     ────► candidate diagnostics only
       └── facing (0x30C)         route plan output
```

## Quick commands

### Read player position + orientation
```powershell
python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --nav-state --json
```

### Emit consumer-safe position + yaw contract
```powershell
scripts\riftreader-navigation-consumer-state.cmd --json --write
```

### Dry-run route plan (no movement)
```powershell
python scripts/static_owner_turn_aware_route_plan.py `
  --destination-waypoint-json <waypoint.json> `
  --json
```

### Dry-run continuous waypoint sequence (no movement/input)
```powershell
python scripts/static_owner_continuous_route_runner.py `
  --waypoint-sequence-json <waypoints.json> `
  --dry-run `
  --json
```

`--dry-run` is a consumer-safe planning/readback mode: it does not require
`--turn-approved`, `--movement-approved`, or `--allow-candidate-turn-control`
because it stops before turn or forward input can be sent.
For waypoint sequences, dry-run advances across waypoints that are already
within arrival radius, then stops after the first unreached leg plan; it does
not simulate movement or claim later waypoints were reached.
The route planning/execution scripts default to
`--current-truth-json docs/recovery/current-truth.json`; pass an explicit
`--current-truth-json <path>` only when using a different target packet.

### Validate a saved continuous dry-run for consumers
```powershell
scripts\static-owner-continuous-route-sequence-contract.cmd `
  <sequence-summary.json> `
  --json
```

Use this before handing a sequence dry-run to another project. It accepts only
saved summaries with `operator.dryRun=true`, no movement/input, no route-control
promotion, and no simulated multi-waypoint arrival claims.

### One-command waypoint readiness for consumers
```powershell
scripts\riftreader-navigation-waypoint-readiness.cmd `
  --waypoint-sequence-json <waypoints.json> `
  --json
```

This command normalizes waypoint files, canonicalizes `arrivalRadius`, generates
missing IDs, blocks duplicate IDs or bad coordinates, runs a no-input sequence
dry-run, and validates the saved sequence contract report. Use `--skip-dry-run`
for offline lint-only normalization when no RIFT target should be read.

### Validate saved navigation JSON schema for consumers
```powershell
scripts\riftreader-navigation-schema-validate.cmd `
  --input <summary.json> `
  --json
```

The validator checks saved JSON artifacts against tracked schemas in
`docs\schemas\navigation\`. It infers the schema from `kind` or
`provenance.kind` and reads saved JSON only; it performs no live target reads,
input, movement, debugger/CE attach, provider writes, or promotion.

### Build downstream consumer demo/readiness report
```powershell
scripts\riftreader-navigation-consumer-demo.cmd `
  --waypoint-readiness-json <readiness-summary.json> `
  --json
```

This saved-artifact-only report combines the latest consumer pose, normalized
waypoints, sequence dry-run, contract report, and schema checks into one
external-consumer decision: render route, use dry-run contract, queue a gated
live-run request, or refresh stale pose/proof first. It never authorizes live
execution by itself.

### Refresh consumer pose and rerun downstream readiness
```powershell
scripts\riftreader-navigation-consumer-refresh.cmd `
  --waypoint-readiness-json <readiness-summary.json> `
  --json
```

This no-input workflow refreshes the read-only consumer pose, then reruns the
downstream consumer demo against that fresh pose. It may read target memory via
the consumer-state helper, but it sends no input/movement and still never
authorizes live route execution.

### Execute single route step
```powershell
python scripts/static_owner_nav_route_step.py `
  --destination-waypoint-json <waypoint.json> `
  --movement-approved `
  --json
```

### Execute continuous multi-step route
```powershell
python scripts/static_owner_continuous_route_runner.py `
  --waypoint-sequence-json <waypoints.json> `
  --turn-backend mouse-look `
  --mouse-pixels-per-pulse 40 `
  --turn-approved `
  --movement-approved `
  --allow-candidate-turn-control `
  --json
```

### Execute a direct coordinate route
```powershell
python scripts/static_owner_continuous_route_runner.py `
  --destination-x 7295 `
  --destination-z 2945 `
  --turn-backend mouse-look `
  --mouse-pixels-per-pulse 40 `
  --turn-approved `
  --movement-approved `
  --allow-candidate-turn-control `
  --json
```

---

## Turn-aware routing

The route planner computes bearing from player position to waypoint, derives yaw from the
facing target chain, and determines turn direction:

1. **Bearing:** `atan2(waypointZ - playerZ, waypointX - playerX)`
2. **Yaw:** `atan2(Z_at_0x314 - playerZ, X_at_0x30C - playerX)` (from promoted resolver)
3. **Turn delta:** normalized angle difference between yaw and bearing
4. **Diagnostic cross-check:** `owner+0x304` is candidate-only. The latest
   semantics review classified it as a yaw-adjacent scalar (`Δ0x304 ≈
   -radians(Δyaw)`), not an active turn-rate resolver. Use it only for
   diagnostics unless a future dedicated turn-rate proof supersedes this.

If delta > threshold: route plan outputs turn direction (left/right) and degrees.
If delta ≤ threshold: player is aligned, proceed to forward movement.

**Blocker:** `turn-direction-mismatch` only when `owner+0x304` has been promoted
by a dedicated turn-rate gate and disagrees with atan2. As of 2026-06-01,
`owner+0x304` is still candidate-only and yaw-adjacent; a mismatch is a
diagnostic warning. Promoted position plus promoted facing/yaw remains the hard
route-planning source.

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
| Turn completion verification | ✅ #3 done | `turn_completion_detector.py` exact-targets PID/HWND and supports `--turn-backend key` or live-valid `--turn-backend mouse-look` |
| Strafe/drift detection | ✅ #4 offline done | Route summaries classify stationary blocks and drift-back; chat/UI focus must be ruled out before terrain conclusions |
| Facing target zero-vector after zone-in | ✅ Guard #2 | `navStateError: facing-target-zero-vector` |
| Stale module base after restart | ✅ Guard #1 | `moduleBaseCheck` freshness gate |

## Route file format

```json
{
  "schemaVersion": 1,
  "waypoints": [
    {"x": 7265.0, "y": 821.5, "z": 3010.0, "arrivalRadius": 0.75},
    {"x": 7270.0, "y": 821.5, "z": 3020.0, "arrivalRadius": 0.75}
  ]
}
```

`arrivalRadius` is the canonical per-waypoint radius field. Legacy files using
`radius` are also accepted by `static_owner_continuous_route_runner.py` when
`arrivalRadius` is absent.

## Movement safety gates

All live movement requires:
1. `--movement-approved` flag (explicit human approval each session)
2. Module base freshness gate passes (live module base matches `current-truth.json`)
3. Facing target non-zero (zone-in state blocked)
4. Exact PID/HWND/process-start match to `current-truth.json`
5. Turn input approval via `--turn-approved` when route execution may turn
6. Candidate-yaw control approval via `--allow-candidate-turn-control`
7. Optional `--clear-ui-focus-before-input` only after visual confirmation of chat/menu focus
8. No Cheat Engine, no x64dbg, no SavedVariables-as-live-truth

## Anti-patterns

| Don't | Use instead |
|---|---|
| Move without fresh chain readback | Always `--nav-state` before any W/S key |
| Trust old PID proof anchors | Module-RVA resolver (`0x32EBC80`) survives restarts |
| Send title-only turn keys without convergence check | `turn_completion_detector.py` with exact PID/HWND target resolution |
| Treat a strafe recommendation as permission | Execute only after explicit movement approval and fresh exact-target readback |
| Treat `ReaderBridgeExport.lua` as live IPC | SavedVariables update only on `/reloadui`/logout |

## Related docs

> **Note:** Legacy route/turn contracts live under `docs/workflow/` (singular),
> predating this `docs/workflows/` directory. They remain authoritative for
> their specific contracts.

- Turn-aware route contract: `docs/workflow/static-owner-turn-aware-route-contract.md`
- Route step contract: `docs/workflow/static-owner-nav-route-contract.md`
- Turn stimulus contract: `docs/workflow/static-owner-turn-stimulus-contract.md`
- Consumer state contract: `docs/workflows/navigation-consumer-contract.md`
