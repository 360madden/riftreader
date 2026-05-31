# RiftReader Handoff — 2026-05-30

**Compact re-entry doc.** Read this first when returning to the project.

## Current state

RIFT automated navigation is in **Phase 0 (correctness)**. Four of four
correctness blockers now have offline/code-level coverage; live route validation
and any strafe recovery execution remain explicitly gated.

| # | Blocker | Status |
|---|---|---|
| #1 | Static resolver freshness gate | ✅ Done — pre-movement readback gate in runner |
| #2 | Turn-aware route planning (atan2 + 0x304 cross-check) | ✅ Done — `turn_aware_route_plan.py` |
| #3 | Verified turn convergence (pulse-loop detector) | ✅ Done via `mouse-look` backend; keyboard input also works after chat focus is cleared |
| #4 | Strafe/drift detection | ✅ Done offline — route summaries classify stationary block/drift-back and emit advisory recovery plan |

**Pipeline architecture:**
```
state readback → plan (bearing + 0x304) → turn (mouse-look pulse-loop verified) → forward (route step) → repeat
```

## Key files (start here)

| File | Purpose |
|---|---|
| `scripts/static_owner_continuous_route_runner.py` | Main loop: plan → turn → forward → repeat |
| `scripts/turn_completion_detector.py` | Pulse-loop turn convergence (Phase 0 #3) |
| `scripts/static_owner_mouse_turn_probe.py` | Exact-target right-mouse-look yaw probe/calibration |
| `scripts/static_owner_turn_input_probe.py` | Keyboard/backend input probe; use to rule out chat/UI focus swallowing keys |
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

## Latest live finding — 2026-05-31

| Finding | Evidence |
|---|---|
| Forward movement still works through exact PID/HWND SendInput | `static-owner-nav-route-step-20260531-110018-508811` reduced distance from `5.00m` to `3.50m`. |
| Turn detector now exact-targets SendInput instead of title-only matching | `turn-completion-detector-20260531-110947-987388` child pulses all used PID `25668` / HWND `0x320CB0`. |
| Chat input focus can swallow movement/turn keys and mimic terrain blockage | Screenshot `tools/rift-game-mcp/.runtime/screenshots/capture-20260531-075721-244.png` showed chat active with typed probe characters after route/key tests. Treat no-progress results as input-focus suspect until ruled out. |
| Exact-target Escape cleared chat focus | After focus/capture, `escape` produced screenshot `tools/rift-game-mcp/.runtime/screenshots/capture-20260531-075808-939.png` with chat closed. Escape is not idempotent; only send it when chat/menu focus is visually confirmed. |
| Keyboard input works once chat focus is cleared | `static-owner-turn-input-probe-20260531-115821-551526` showed `w` planar movement `2.90m`, `s` `1.45m`, `a` yaw delta `79.06°`, and `d` yaw delta `81.88°`. |
| Mouse-look turns are live-valid | `static-owner-mouse-turn-probe-20260531-113550-179711` validated 6/6 exact-target mouse-look attempts: 40px ≈ `5.65°` left / `7.06°` right, 80px ≈ `16.94°`, 160px ≈ `50–52°`, with zero coordinate drift. |
| Turn completion detector now supports `--turn-backend mouse-look` | `turn-completion-detector-20260531-114052-609533` converged a +15° right turn in 2 mouse pulses: yaw `62.47° → 76.59°`, final error `0.88°`. |
| Continuous route loop can execute mouse turns; earlier forward no-progress was not confirmed terrain | `static-owner-continuous-route-20260531-114251-242356` and `static-owner-continuous-route-20260531-114509-094476` both completed mouse-look turns while chat was likely active, then classified forward `W` as `blocked-stationary-no-movement`. Treat as chat/UI-focus suspect until ruled out. |
| Mouse arc recovery succeeds after chat focus is cleared | `static-owner-mouse-arc-recovery-20260531-115937-707432` passed on offset `0.0°`: planar movement `2.90m`, destination distance `2.55m → 0.40m`, progress `2.15m`. |
| Continuous route loop passes with chat focus ruled out | `static-owner-continuous-route-20260531-121254-529672` routed to an ahead-4m destination with no chat input active: initial distance `4.00m`, progress `3.73m`, arrived in 1 forward step, no blockers. |
| Defensive chat-focus preclear is now opt-in | `static_owner_nav_route_step.py`, `static_owner_continuous_route_runner.py`, and `static_owner_mouse_arc_recovery_probe.py` support `--clear-ui-focus-before-input`; it sends one exact-target Escape where applicable and records a warning because Escape is not idempotent. |
| No-progress reporting now keeps the focus hazard explicit | Route-step/route-loop no-progress paths warn that chat/UI focus is not ruled out before treating `blocked-stationary-no-movement` as terrain; recovery gates now include visual focus hygiene. |
| Mouse arc recovery is wired into route-loop recovery advice | `static_owner_continuous_route_runner.py` now emits `recoveryHelper` metadata pointing to `static_owner_mouse_arc_recovery_probe.py` with candidate-only notes and required live gates. |


## Fresh live verification — 2026-05-31 12:41–12:42 UTC

| Check | Evidence |
|---|---|
| Exact current PID static readback passed | `scripts\captures\static-owner-coordinate-chain-readback-20260531-124243-250543\summary.json`: PID `25668`, HWND `0x320CB0`, module base matched, coordinate `7262.338, 821.694, 3002.999`. |
| Exact current PID nav-state readback passed | `scripts\captures\static-owner-nav-state-20260531-124244-004288\summary.json`: yaw `85.06°`, no blockers. |
| Keyboard turn backend produced yaw delta | `scripts\captures\static-owner-turn-input-probe-20260531-124139-909597\summary.json`: key `a`, signed yaw delta `-12.71°`, zero coordinate drift. |
| Mouse-look turn backend produced yaw delta | `scripts\captures\static-owner-mouse-turn-probe-20260531-124158-803473\summary.json`: right 40px, signed yaw delta `+5.65°`, zero coordinate drift. |
| Turn completion detector converged with mouse-look | `scripts\captures\turn-completion-detector-20260531-124210-709153\summary.json`: +10° signed target, 1 pulse, final error `2.94°`. |
| Bounded movement probe passed | `scripts\captures\static-owner-mouse-arc-recovery-20260531-124230-635784\summary.json`: offset `0°`, 300ms `W`, planar movement `1.82m`, no blockers. |

## Validation timing ledger — 2026-05-31 13:49 UTC

Future repair/testing lanes should use the timestamped validation ledger so long
test runs show UTC timestamps, durations, heartbeats, and durable logs.

| Check | Evidence |
|---|---|
| Full local validation passed | `.riftreader-local\validation-runs\20260531-134923-272027\summary.md` |
| Total duration | `367.943s` |
| Longest command | `unittest-discover` at `341.273s` |
| Slow-budget warnings | None; `unittest-discover` stayed under its `420s` warning budget. |
| Immediate smoke command | `python tools\riftreader_workflow\validation_ledger.py --tier smoke` |

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

# Run full route loop to coordinates using the live-valid mouse-look turn backend
python scripts/static_owner_continuous_route_runner.py `
  --destination-x 7295 --destination-z 2945 `
  --turn-backend mouse-look --mouse-pixels-per-pulse 40 `
  --turn-approved --movement-approved --allow-candidate-turn-control --json

# Same route loop with one opt-in Escape preclear if chat/menu focus is visually confirmed
python scripts/static_owner_continuous_route_runner.py `
  --destination-x 7295 --destination-z 2945 `
  --turn-backend mouse-look --mouse-pixels-per-pulse 40 `
  --clear-ui-focus-before-input `
  --turn-approved --movement-approved --allow-candidate-turn-control --json

# Validate turn completion (standalone mouse-look)
python scripts/turn_completion_detector.py `
  --direction left --target-bearing-degrees 90 `
  --turn-backend mouse-look --mouse-pixels-per-pulse 40 --turn-approved --json

# Run all tests
python -m unittest discover -s scripts -p "test_*.py"

# Preferred timed validation smoke check
python tools\riftreader_workflow\validation_ledger.py --tier smoke

# Preferred timed full local validation before push
python tools\riftreader_workflow\validation_ledger.py --tier full-local
```

## Next steps (priority order)

1. **Route-loop rerun with chat-focus ruled out** — use visual preflight or the opt-in `--clear-ui-focus-before-input` flag only when focus is confirmed.
2. **Implement bounded lateral/strafe recovery** — if true terrain blockage remains after focus is ruled out, use exact-target short `A/D` or mouse+strafe probes.
3. **Calibrate mouse-look turn pulse sizing** — 40px is safe for 5–7° pulses; record a small calibration table in route docs/tests.
4. **Refresh route fixtures with the new live artifacts** — preserve mouse-turn success, chat-focus hazard, post-Escape movement success, and route-loop pass.
5. **Clean/commit remaining local slices** — keep explicit paths only; review mixed pre-existing changes separately.
6. **Phase 1: Combat bot** — target selection, combat state detection, ability rotation (see `docs/workflows/combat-bot-roadmap.md`).
