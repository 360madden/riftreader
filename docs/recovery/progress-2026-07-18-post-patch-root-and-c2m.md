# Progress notes — post-patch root reseed + C2M (2026-07-18)

**Status:** durable session milestone. Live authority is always
[`current-truth.md`](current-truth.md) / [`current-truth.json`](current-truth.json).

**Branch commits (pushed to `origin/main`):**

| Commit | Summary |
|---|---|
| `be233c8` | Promote static root `0x32E07C0` (restart, three-pose, truth, W2S) |
| `b88e38c` | C2M runner: W2S/center aim + static-chain pose multi-WP |
| `3b9b0e7` | C2M destination discovery helpers + pre-update root signature |

**Related:**

| Doc | Role |
|---|---|
| [`current-truth.md`](current-truth.md) | Live operator truth pointer |
| [`c2m-truth-bind-and-static-chain-restart-survival.md`](c2m-truth-bind-and-static-chain-restart-survival.md) | **C2M ↔ truth + restart survival (library entry)** |
| [`post-patch-static-root-candidate-2026-07-18.md`](post-patch-static-root-candidate-2026-07-18.md) | Discovery narrative (promoted) |
| [`../workflows/optimized-post-update-recovery-workflow.md`](../workflows/optimized-post-update-recovery-workflow.md) | Next-patch playbook |
| [`../workflows/automated-travel-memory-data-catalog.md`](../workflows/automated-travel-memory-data-catalog.md) | Travel field inventory |
| [`c2m-destination-discovery-status-2026-07-18.md`](c2m-destination-discovery-status-2026-07-18.md) | Engine dest scan (still open) |

---

## 1. Problem we solved

After the 2026-07-14-class client binary change:

| Old root | Status |
|---|---|
| `0x32EBC80` | Dead / wrong epoch |
| `0x32EBDC0` | Null owner pointer on live process |

Navigation and W2S were blocked: no restart-stable owner, no trustworthy camera
child, no promoted static XYZ.

---

## 2. What is promoted now

### Coordinate chain

```text
[rift_x64+0x32E07C0] → owner (heap, session-local)
  +0x320 / +0x324 / +0x328  → player X / Y / Z (float)
  +0x300                    → cumulative rotation counter (not direct heading)
  +0x304                    → scalar matching heading value this session
  +0x330                    → camera-state child pointer
```

### Camera child (under `owner+0x330`)

| Offset | Field |
|---|---|
| `+0x08 / +0x0C / +0x10` | Camera position |
| `+0x14 / +0x18 / +0x1C` | Look-at / player-on-camera |
| `+0x38` | FOV degrees (75 observed) |
| `+0x3C` | Near plane |
| `+0x158` | Heading radians (revalidated) |

**W2S forward:** `normalize(lookAt − camPos)` from `+0x14` relative to cam pos.  
**Do not** use the unit triple at camera `+0x2C` as look direction on this patch
(unit length but not usable forward).

### Superseded

Do **not** use `0x32EBC80` or `0x32EBDC0` for live work on this binary.

---

## 3. Gates passed (evidence)

| Gate | Result | Artifact / note |
|---|---|---|
| API-now family seed | 32 XYZ hits vs RRAPICOORD | `scripts/captures/family-scan-currentpid-26916-20260718-164435-926620/` |
| Module `.data` root reseed | Found `0x32E07C0` + classic `+0x320` | `scripts/captures/owner-root-reseed-currentpid-26916-20260718-165500/` |
| Same-pose API vs chain | Δ ≈ 0.003–0.004 | chain readbacks |
| **Restart survival** | PID `26916` → `21436`; owner heap changed; RVA held | `scripts/captures/owner-root-restart-survival-currentpid-21436-20260718-170030/` |
| **Three-pose + API** | W then S; A→B ≈ 4.87 m, B→C ≈ 2.35 m; all poses API match | `scripts/captures/static-root-three-pose-21436-20260718-170754/` |
| **Center SendInput LMB** | Planar Δ ≈ **2.14 m**; no resize; focus OK | `scripts/captures/sendinput-lmb-test-20260718-170938/` |
| W2S/S2W round-trip | look-at/body planar error **0.0 m** | `scripts/world-to-screen.py --round-trip` |
| Multi-WP C2M | 2 relative legs arrived (`0,5` then `3,0`) | `scripts/captures/c2m-run-to-goal-20260718-171601/` |
| `current-truth` apply | JSON + MD updated; historical backup written | `docs/recovery/historical/current-truth-before-0x32E07C0-promote-20260718-171122.json` |

Helper for three-pose proof (reusable):

```text
python scripts\static_root_three_pose_proof.py --movement-approved --json
```

---

## 4. Operator decisions locked this session

| Topic | Decision | Why |
|---|---|---|
| Click aim | **True client center** for safety proofs; C2M may use **W2S** but **never** ~0.82 Y toolbar band | Lower-third hit action bar after camera angle change |
| NPC under crosshair | Operator clears center; do not treat NPC select as C2M proof | Center is crosshair/units, not pure ground |
| Mouse backend | **SendInput** absolute mouse after foreground focus | PostMessage mouse does not drive RIFT C2M reliably |
| Focus | Activate only; **`SW_RESTORE` only if iconic** | Restore un-maximizes / changes client size |
| Multi-click focus | C2M/route clicks use **`--no-refocus`** | Default SendInput returned focus to previous app every click → flicker |
| Static vs heap | Promote **RVA + offsets only**; reacquire owner each session | Heap owner changes every restart |
| Engine C2M destination | **Not required** for travel MVP | In-game C2M + click + pose arrival is enough |
| Facing probe scripts | Most already tracked historical; **do not** commit leftover scratch without cleanup | Hardcoded dead roots/PIDs |
| CE / x64dbg | Not used in this promotion path | Root found via API match + module pointer scan |

---

## 5. Tools (durable entry points)

| Need | Command |
|---|---|
| Instant pose + heading | `python scripts\static_owner_pose_now.py --json` |
| Truth-bound chain readback | `python scripts\static_owner_coordinate_chain_readback.py --use-current-truth --samples 2 --json` |
| W2S / S2W / round-trip | `python scripts\world-to-screen.py --pid <pid> --round-trip --json` |
| Three-pose proof | `python scripts\static_root_three_pose_proof.py --movement-approved --json` |
| Center LMB proof | `python scripts\test_sendinput_lmb.py --json` |
| Multi-WP C2M (relative) | `python scripts\c2m_run_to_goal.py --execute --stimulus-approved --aim-mode w2s --pose-source static-chain --waypoint-offsets "0,5;3,0" --arrival-radius 2.5 --json` |
| Single offset C2M | `python scripts\c2m_run_to_goal.py --execute --stimulus-approved --aim-mode w2s --pose-source static-chain --offset-z 8 --json` |

**Aim modes (`c2m_run_to_goal`):**

| Mode | Behavior |
|---|---|
| `w2s` | Project world goal via camera; clamp to safe client band |
| `center` | Client-center Y; modest lateral bias only |
| `heuristic` | Mid-client Y only (never toolbar ~0.82) |

**Pose sources:** `static-chain` (preferred/fast), `rrapicoord`, `auto`.

---

## 6. C2M / travel status

| Capability | Status |
|---|---|
| Static XYZ + camera + FOV | ✅ promoted |
| Heading `[[owner+0x330]+0x158]` | ✅ readable (candidate-quality for turns; usable for steering math) |
| W2S / ground-plane S2W | ✅ usable |
| SendInput center LMB moves character | ✅ proven |
| Multi-waypoint relative C2M | ✅ live arrived (2 legs) |
| Absolute route JSON library | ❌ not built yet |
| Stuck re-aim / dwell arrival | ❌ not built yet |
| Engine C2M dest float | ❌ not found / not required |
| Full actor/stat graph | ❌ not promoted |

Engine destination discovery notes (player ±40 volume, no fixed dest float):
[`c2m-destination-discovery-status-2026-07-18.md`](c2m-destination-discovery-status-2026-07-18.md).

---

## 7. How the root was found (short recipe)

No CE, no x64dbg for this reseed:

1. Bind exact PID/HWND.  
2. Fresh RRAPICOORD API-now.  
3. Family scan → API-matching XYZ heap hits.  
4. Scan `rift_x64` module data for QWORD heap pointers.  
5. For each pointer, test classic `+0x320` (and nearby) vs API.  
6. Hit: **`0x32E07C0` → owner → +0x320** matches; **`+0x330` camera child** live.  
7. Restart: new PID, new owner heap, same RVA.  
8. Three-pose W/S + API-now each pose.  
9. Promote into `current-truth` only after gates + explicit approval.

For the **next** client update, prefer:
[`../workflows/optimized-post-update-recovery-workflow.md`](../workflows/optimized-post-update-recovery-workflow.md).

---

## 8. Recommended next

| # | Action | Status |
|---|---|---|
| 1 | Stuck / re-aim loop in C2M | **Done** — flip + center + W2S refresh on no-progress streak |
| 2 | Arrival dwell | **Done** — `--dwell-ms` (default 600) |
| 3 | Absolute / relative waypoint JSON | **Done** — `scripts/routes/` + `--waypoints-json` |
| 4 | Truth fail-closed bind on C2M | **Done** — `--use-current-truth` default on |
| 5 | Heading-aware pre-step | Still open |
| 6 | Operator smoke runbook polish | Partial (`scripts/routes/README.md`) |

### Route + reliability usage

```powershell
python scripts\c2m_run_to_goal.py --execute --stimulus-approved `
  --use-current-truth --aim-mode w2s --pose-source static-chain `
  --waypoints-json scripts\routes\smoke-rel-L.json --json
```

After restart: refresh `current-truth` target bind (or recovery-only `--allow-target-drift`).

**Do not** next: re-seed root, CE attach, mass-commit facing scratch probes.

---

## 9. Facing probe scripts policy

| Set | Policy |
|---|---|
| `scripts/facing_target_*.py` | Keep — formal gate/promotion helpers |
| Most `scripts/facing-*.py` already on `main` | Historical discovery archive |
| Untracked leftovers (`facing-calibrate.py`, `facing-scan-movement.py`) | **Do not commit** without cleanup (hardcoded dead root/PID) |
| Day-to-day heading | `static_owner_pose_now.py` / `world-to-screen.py` |

---

## 10. Safety checklist for future agents

- Exact PID/HWND/process-start/module base before input.  
- No `SW_RESTORE` unless window iconic.  
- No toolbar/lower-edge aim; prefer center or clamped W2S.  
- No CE/x64dbg without explicit re-approval.  
- No truth/promotion without explicit approval.  
- Heap owner is never static; only RVA + offsets.  
- SavedVariables / `ReaderBridgeExport.lua` is **not** live pose truth.

---

*Written 2026-07-18 for durable handoff after post-patch root promotion and multi-WP C2M proof.*
