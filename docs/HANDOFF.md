# RiftReader Handoff — 2026-05-30

**Compact re-entry doc.** Read this first when returning to the project.

## Current state

RIFT automated navigation is in **Phase 0 (correctness)**. Three of four blockers are resolved:

| # | Blocker | Status |
|---|---|---|
| #1 | Static resolver freshness gate | ✅ Done — pre-movement readback gate in runner |
| #2 | Turn-aware route planning (atan2 + 0x304 cross-check) | ✅ Done — `turn_aware_route_plan.py` |
| #3 | Verified turn convergence (pulse-loop detector) | ✅ Done — `turn_completion_detector.py` |
| #4 | Strafe/drift detection | ❌ Remaining |

**Pipeline architecture:**
```
state readback → plan (bearing + 0x304) → turn (pulse-loop verified) → forward (route step) → repeat
```

## Key files (start here)

| File | Purpose |
|---|---|
| `scripts/static_owner_continuous_route_runner.py` | Main loop: plan → turn → forward → repeat |
| `scripts/turn_completion_detector.py` | Pulse-loop turn convergence (Phase 0 #3) |
| `scripts/static_owner_turn_aware_route_plan.py` | Bearing + 0x304 cross-check plan (Phase 0 #2) |
| `scripts/static_owner_nav_route_step.py` | Single forward step with pre/post state analysis |
| `scripts/nav_state_readback.py` | Read yaw, turn rate, facing from promoted static chain |
| `scripts/capture_root_signature.py` | Capture AOB signatures for game-update resilience |
| `docs/workflows/README.md` | Master decision tree (8 scenarios) |
| `docs/workflows/session-startup.md` | "I just logged in, what now?" |

## Promoted static resolver (current truth)

All reads use the promoted static pointer chain at `rift_x64.exe+0x32EBC80`:

| Field | Offset | Notes |
|---|---|---|
| Player X/Y/Z | +0x320/+0x324/+0x328 | 2 ReadProcessMemory calls |
| Facing target | +0x30C/+0x310/+0x314 | Same owner, 20 bytes before coords |
| Turn rate | +0x304 | float, positive=left, negative=right |
| Yaw formula | `atan2(Z@0x314 - PZ, X@0x30C - PX)` | Read both chains in same cycle |

**AOB signature** for game-update resilience: `B5 01 00 00 ?? ?? ?? ??` (stored in `signatures/rift_x64/root_root-player-owner.json`)

## Recent commits (this session)

| Commit | What |
|---|---|
| `dcfadd8` | AOB signature capture + live signature + structured workflow docs (8 new docs) |
| `2cc6ace` | Turn completion detector — verified pulse-loop turn convergence (Phase 0 #3) |

## Decision tree

- **"I just logged in"** → `docs/workflows/session-startup.md`
- **"Game updated, resolver broken"** → `docs/workflows/pointer-chain-reacquisition.md`
- **"Turn isn't working"** → `scripts/turn_completion_detector.py --help`
- **"Navigation stuck"** → Check forward no-progress sub-classification in runner output
- **"Need to capture new signature"** → `python scripts/capture_root_signature.py --rva <hex> --label <name> --pid <pid> --json`

## Safety gates (all must be explicitly approved)

| Flag | Purpose |
|---|---|
| `--turn-approved` | Turn key input |
| `--movement-approved` | Forward movement input |
| `--allow-candidate-turn-control` | Candidate yaw-based turning |

## Quick commands

```powershell
# Read current player state (no input)
python scripts/nav_state_readback.py --use-current-truth --json

# Run full route loop to coordinates
python scripts/static_owner_continuous_route_runner.py \
  --destination-x 7295 --destination-z 2945 \
  --turn-approved --movement-approved --allow-candidate-turn-control --json

# Validate turn completion (standalone)
python scripts/turn_completion_detector.py \
  --direction left --target-bearing-degrees 90 --turn-approved --json

# Run all tests
python -m pytest scripts/ -v
```

## Next steps (priority order)

1. **Phase 0 #4: Strafe/drift detection** — detect `blocked-stationary-no-movement` and `drifted-back-after-initial-progress` sub-classifications, try opposite strafe key before re-attempting forward
2. **Live test turn completion detector** against running RIFT — `@rift-readback` then small signed-delta turn
3. **Move calibration constants** from runner module to test file where they're actually used
4. **Phase 1: Combat bot** — target selection, combat state detection, ability rotation (see `docs/workflows/combat-bot-roadmap.md`)
