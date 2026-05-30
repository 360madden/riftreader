# Combat Bot Roadmap

**What this covers:** Full phased plan for building an automated combat bot.

**Status:** Phase 0 in progress (50% complete). Phases 1–6 are planned.

---

## Phase 0: Foundation — Navigation Correctness ✅🔄

**Goal:** Prove the navigation pipeline works end-to-end with turn verification.

| # | Task | Status |
|---|---|---|
| 0a | Player position resolver | ✅ Promoted |
| 0b | Player facing / yaw resolver | ✅ Promoted |
| 0c | Turn rate discriminator (0x304) | ✅ Promoted |
| 0d | SendInput (ScanCode) for movement keys | ✅ Proven |
| 0e | Navigation route planner (turn-aware) | ✅ Built |
| 0f | Module base freshness gate | ✅ Shipped (#1) |
| 0g | Facing target zero-vector guard | ✅ Shipped (#2) |
| **0h** | **Turn completion detection** | **❌ NEXT** |
| **0i** | **Live E2E smoke test** | **After 0h** |

---

## Phase 1: Target Entity Memory Discovery 🔴

**Goal:** Find the pointer chain for the selected target entity.

**Hardest single phase.** Without this, you can't read target health, verify
selection, or compute bearing-to-target.

**What to discover:**

| Field | Priority | Why |
|---|---|---|
| Target base address | P0 | Root of the target object |
| Target health (current/max) | P0 | Kill priority, execute range |
| Target level | P0 | Pull safety |
| Target position (x/y/z) | P0 | Distance calculation |
| Target dead/alive flag | P1 | Stop attacking corpses |
| Target faction/hostility | P1 | Don't attack friendlies |
| Target name/ID | P2 | Identity verification |
| Target casting flag | P2 | Interrupt detection |

**Method:** Tab-to-select → memory snapshots with target vs. without target →
`rift-discovery` agent for chain tracing.

**Estimated work:** 2–4 discovery sessions + promotion gates.

---

## Phase 2: Player Combat State Discovery 🟡

**Goal:** Read player combat state from the owner object.

**Likely location:** Owner object between `+0x000` and `+0x300`.

**What to discover:**

| Field | Priority | Why |
|---|---|---|
| Player health (current/max) | P0 | Death prevention |
| Player mana/energy/power | P0 | Ability gating |
| In-combat flag | P0 | Don't rest while fighting |
| Casting/channeling flag | P1 | Don't interrupt own casts |
| GCD state | P1 | Ability queue timing |
| Buff slots (count/IDs) | P2 | Food buff, mount, stealth detection |

**Method:** Neighborhood scan of owner object. Compare while taking damage,
casting, entering/leaving combat.

**Estimated work:** 1–2 discovery sessions.

---

## Phase 3: Target Selection & Engagement 🟢

**Goal:** Build the target acquisition and engagement pipeline.

**Components:**

1. `target_selection.py` — Tab to nearest target, verify in memory
2. `target_prioritization.py` — Rank by distance, health, threat
3. `engagement_preflight.py` — Range check, facing check, LOS
4. `engagement_executor.py` — Move into range, face target, attack

**Depends on:** Phase 1 (target chain) + Phase 0h (turn completion).

**Estimated work:** 1–2 sessions.

---

## Phase 4: Rotation Engine 🟢

**Goal:** Build a configurable ability rotation system.

**Components:**

1. `ability_catalog.py` — Ability definitions (key, cooldown, range, resource cost)
2. `rotation_engine.py` — Priority queue, GCD tracking, resource management
3. `castbar_detector.py` — Detect when a cast completes (memory flag)
4. `interrupt_handler.py` — Detect enemy casts, interrupt if configured

**Depends on:** Phase 2 (player combat state) + Phase 1 (target casting flag).

**Estimated work:** 1–2 sessions.

---

## Phase 5: Combat Loop Integration 🟢

**Goal:** Wire everything together into a continuous combat loop.

```
while combat_active:
    1. Read player state (health, mana, GCD)
    2. Read target state (health, dead?, casting?)
    3. If no target or target dead → target_selection.py
    4. If out of range → move into range (turn + forward)
    5. If not facing target → turn to face
    6. Execute next ability from rotation
    7. Health check → potion/defensive if low
    8. Loop
```

**Estimated work:** 1 session.

---

## Phase 6: Resilience & Anti-Detection 🟡

**Goal:** Make the bot robust against edge cases and harder to detect.

| Feature | Priority |
|---|---|
| Stuck detection (no progress timeout) | P1 |
| Combat log verification (did damage land?) | P1 |
| Pull radius safety (don't aggro extra mobs) | P1 |
| Out-of-combat recovery (rest, rebuff) | P2 |
| Zone/instance detection | P2 |
| Randomized action timing | P2 |
| Death recovery (corpse run) | P3 |
| Pathfinding around obstacles | P3 |

**Estimated work:** 1–2 sessions.

---

## Total estimate

| Phase | Sessions | Dependency |
|---|---|---|
| 0 (finish #3–#4) | 1 | None |
| 1 (target discovery) | 2–4 | Phase 0 |
| 2 (player combat state) | 1–2 | Phase 0 |
| 3 (target selection) | 1–2 | Phase 1 |
| 4 (rotation engine) | 1–2 | Phase 2 |
| 5 (combat loop) | 1 | Phases 3+4 |
| 6 (resilience) | 1–2 | Phase 5 |
| **Total** | **8–14** | |

---

## Next action

**Continue Phase 0h: Turn completion detection.**
This is the last correctness blocker before live navigation can work reliably.
Without it, every turn is a coin flip.
