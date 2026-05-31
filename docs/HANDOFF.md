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
| `059832a` | Surface truth refresh plan in workflow status |
| `f5f8bc2` | Document current truth refresh plan |
| `a539850` | Add current truth refresh plan helper |
| `16f9323` | Document navigation pointer status workflow |
| `c6fad32` | Refresh handoff with navigation discovery status |
| `6f9dcc7` | Surface navigation discovery dashboard in compact workflow status |
| `7cc2587` | Refine navigation discovery freshness guidance |
| `a9b062c` | Add navigation discovery freshness classification |
| `32367d7` | Document navigation pointer discovery dashboard |
| `0100434` | Add navigation pointer discovery dashboard |

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

## Pointer-chain discovery refresh — 2026-05-31 14:19–14:23 UTC

| Check | Evidence |
|---|---|
| Exact target reacquired | PID `25668`, HWND `0x320CB0`, module base `0x7FF6EE5D0000`, owner `0x1B53D7806A0`. |
| Baseline static-owner snapshot | `scripts\captures\static-owner-facing-snapshot-baseline-20260531-20260531-141907-660274\summary.json` |
| Mouse-look right yaw stimulus | `scripts\captures\static-owner-mouse-turn-probe-20260531-141920-662365\summary.json`: right `160px`, yaw delta `+49.410772°`, planar drift `0.0`. |
| Mouse-look left yaw stimulus | `scripts\captures\static-owner-mouse-turn-probe-20260531-141934-149919\summary.json`: left `320px`, yaw delta `-111.529978°`, planar drift `0.0`. |
| Facing comparison | `scripts\captures\static-owner-facing-comparison-20260531-141949-380215\summary.json`: top relative target `owner+0x30C/+0x310/+0x314`, yaw deltas `+49.410772°` and `-62.119206°` from baseline, coordinate drift `0.0`. |
| Pointer neighborhood | `scripts\captures\pointer-owner-neighborhood-inspector-20260531-142006-017134\summary.json`: read-only owner neighborhood passed; heap-near-target references only, no promotion. |
| Memory-region scan plan | `scripts\captures\memory-region-inventory-currentpid-25668-20260531-142058-445123\scan-plan.json` |
| Bounded movement-family snapshot | `scripts\captures\family-snapshot-sequence-currentpid-25668-20260531-142159-332736\summary.json`: exact-target `W` 350ms, movement/input sent, no CE/x64dbg/provider writes. |
| Current coordinate candidate reacquired | Delta summary `scripts\captures\family-snapshot-sequence-currentpid-25668-20260531-142159-332736\delta-analysis\delta-summary.json`: best candidate `0x1B53D7809C0` / owner+`0x320`, tracking max abs `0.006398926`, API planar `2.267577m`, memory planar `2.269441m`. |
| Post-run static readback | `scripts\captures\static-owner-coordinate-chain-readback-20260531-142312-924000\summary.json`: coordinate `7264.431641, 821.697205, 3003.875732`, stationary, no blockers. |
| Post-run nav-state readback | `scripts\captures\static-owner-nav-state-20260531-142312-943158\summary.json`: yaw `22.940854°`, pitch `-4.941195°`, turn rate `1.171186`, no blockers. |

Outcome: current coordinate/facing pointer-chain evidence is reacquired for PID `25668`; `docs\recovery\current-truth.*` now records the fresh current API-now validation. No new actor/stat chain or proof promotion was performed.

## Safe-local dashboard/status refresh — 2026-05-31 15:19 UTC

| Check | Evidence |
|---|---|
| Compact workflow status now embeds navigation pointer discovery | Commit `6f9dcc7`; `cmd /c scripts\riftreader-workflow-status.cmd --compact-json` includes `navigationPointerDiscovery` with promoted coordinate, candidate facing target, candidate turn rate, coordinate-delta evidence, freshness, next action, and safety flags. |
| Exact target no-input coordinate readback refreshed | `scripts\captures\static-owner-coordinate-chain-readback-20260531-151942-201598\summary.json`: PID `25668`, HWND `0x320CB0`, owner `0x1B53D7806A0`, coordinate readback fresh. |
| Exact target no-input nav-state readback refreshed | `scripts\captures\static-owner-nav-state-20260531-151943-009442\summary.json`: yaw `22.940854°`, pitch `-4.941195°`, turn rate `1.171186`, no input/movement/debugger/provider writes. |
| Dashboard regenerated | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` generated `2026-05-31T15:19:44Z`; status `passed`, freshness `stale` only because tracked `currentTruth` is older than the local readbacks. |
| Validation ledger recorded reacquisition timing | `.riftreader-local\validation-runs\20260531-151941-457745\summary.md`: coordinate readback `0.777s`, nav readback `0.779s`, dashboard regen `0.773s`, overall passed. |

Current safe next action: keep using the dashboard/status packet for resume context. Do **not** promote facing/turn-rate chains or rewrite current truth unless a deliberate proof/truth-refresh gate is opened.

## Current-truth refresh dry-run plan — 2026-05-31 15:38 UTC

| Check | Evidence |
|---|---|
| Dry-run planner added | `scripts\riftreader-current-truth-refresh-plan.cmd --json --write` calls Python helper `tools\riftreader_workflow\current_truth_refresh_plan.py`. |
| Compact workflow status now embeds the plan | Commit `059832a`; `cmd /c scripts\riftreader-workflow-status.cmd --compact-json` includes `currentTruthRefreshPlan` with status, update count, proposed artifacts, safety flags, and the explicit apply gate. |
| Ignored proposal generated | `.riftreader-local\current-truth-refresh-plan\latest\summary.json`, `proposed-current-truth.json`, and `proposed-current-truth.diff`. |
| Planner result | Status `passed`, `updateCount=9`; it proposes refreshing static-chain readback timestamps/coordinate fields only and keeps API-now/proof/promotion boundaries explicit. |
| Safety boundary | `trackedTruthWritten=false`, `movementSent=false`, `inputSent=false`, `targetMemoryBytesRead=false`, `proofPromotion=false`, `facingPromotion=false`, `gitMutation=false`. |
| Notable warning | Current tracked truth already contains historical `staticOwnerFacing` promotion metadata while the latest dashboard keeps facing as candidate-only context; the plan does not change that field. |
| Validation ledger | `.riftreader-local\validation-runs\20260531-153915-784379\summary.md` and `.riftreader-local\validation-runs\20260531-153917-915814\summary.md` passed. |

Current safe next action: review the ignored proposal artifacts. Applying any
tracked `docs\recovery\current-truth.json` update remains a separate explicit
truth-refresh gate; the dry-run plan is not proof promotion.

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
