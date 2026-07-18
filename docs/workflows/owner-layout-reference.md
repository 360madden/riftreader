# Owner Layout Reference

**What this covers:** The canonical memory layout of the player owner object
dereferenced from the **promoted static root**.

**Live root (2026-07-18+):** `[rift_x64+0x32E07C0]`  
**Historical (pre-patch):** `[rift_x64+0x32EBC80]` / July interim `0x32EBDC0` — **do not use** on current binary.

**When to use:** Understanding what fields are available, discovering new fields,
or validating after a game update.

**Related:** For the full automated-travel inventory (coords, heading, camera/FOV,
world-to-screen, navmesh, Godot overlay pose frames, and post-patch status), see
[automated-travel-memory-data-catalog.md](automated-travel-memory-data-catalog.md).
Always check `docs/recovery/current-truth.md` before treating offsets as live.
Milestone notes: `docs/recovery/progress-2026-07-18-post-patch-root-and-c2m.md`.  
C2M / restart contract: `docs/recovery/c2m-truth-bind-and-static-chain-restart-survival.md`.

**Status:** Coordinates at `owner+0x320/+0x324/+0x328` are **promoted** via root
`0x32E07C0` (restart-survivable RVA; three-pose + API-now; multi-restart C2M proof,
2026-07-18). Camera child at `owner+0x330`; heading at `[[owner+0x330]+0x158]`.
Heap owner is session-local. `owner+0x304` remains a yaw-adjacent scalar candidate,
not a formal turn-rate resolver. C2M consumes this chain through `current-truth`.

---

## Owner object at a glance

```
Owner object: [[rift_x64+0x32E07C0]]   // promoted 2026-07-18
Size: at least 0x380+ bytes (observed window 0x2C0-0x35F)
Classification: Player position/rotation controller object
Camera child: [owner+0x330]
```

## Known field layout

| Offset | Size | Type | Field | Status | Notes |
|---|---|---|---|---|---|
| `+0x000` | 8 | ptr | vtable[0] | Candidate | Module-relative function table |
| `+0x008` | 8 | ptr | vtable[1] | Candidate | Second vtable entry |
| `+0x010` | 8 | ptr | self-pointer | Candidate | Points to owner itself |
| `+0x060` | 12 | vec3 | Actor basis forward row | Historical | Different object (actor, not owner). Revalidate after updates. |
| `+0x094` | 12 | vec3 | Actor basis duplicate | Historical | Duplicate basis at different object |
| `+0x2F8` | 1 | byte | Flag byte | Candidate | Set to 0x1 in some states |
| `+0x300` | 4 | float | Accumulated heading / heading support | Candidate/support | Monotonic counter-like value; not promoted for control |
| `+0x304` | 4 | float | Yaw-adjacent scalar candidate | Candidate/support | Latest review: deltas oppose atan2 yaw deltas in radians; active turn-rate delta proof is blocked; do not use as promoted turn rate |
| `+0x308` | 4 | float | Rotation support | Candidate/support | Adjacent to turn rate; semantics unproven |
| `+0x30C` | 4 | float | **Facing target X** | **Promoted** | World-space look-at point |
| `+0x310` | 4 | float | **Facing target Y** | **Promoted** | Elevation of look-at point |
| `+0x314` | 4 | float | **Facing target Z** | **Promoted** | World-space look-at point |
| `+0x318` | 8 | — | Padding/gap | — | 8 bytes between facing target and coordinates |
| `+0x320` | 4 | float | **Player coordinate X** | **Promoted** | East-west position |
| `+0x324` | 4 | float | **Player coordinate Y** | **Promoted** | Elevation |
| `+0x328` | 4 | float | **Player coordinate Z** | **Promoted** | North-south position |
| `+0x400` | 8 | ptr | Source cache pointer | Historical | Points to source+0x48 coordinate cache |
| `+0x408` | 4 | float | Rotation animation timer | Candidate | Binary drop on any turn |

## Key relationships

```
owner+0x320 → player X    ┐
owner+0x324 → player Y    │  Same object, 12-byte contiguous vec3
owner+0x328 → player Z    ┘

owner+0x30C → facing X    ┐
owner+0x310 → facing Y    │  Same object, 20 bytes (0x14) before coordinates
owner+0x314 → facing Z    ┘

Yaw = atan2(facingZ - playerZ, facingX - playerX)
owner+0x304 = yaw-adjacent scalar candidate. In the latest left/right
camera-yaw review, Δ0x304 ≈ -radians(ΔpromotedYaw). Do not interpret its sign
as active turning without a separate successful turn-rate proof.
```

## Behavioral notes

### 0x30C — Facing target

- **NOT a target NPC position.** Tab-selecting a nearby NPC does NOT change this value.
- It's a **camera look-at point** — a point ~10 units ahead of the player in their facing direction.
- Can be (0,0,0) on fresh zone-in — guarded by zero-vector check (#2 gate).
- Validated through 4-pose yaw triangulation (baseline, turn-right, turn-left, symmetric-left).

### 0x304 — Yaw-adjacent scalar candidate

- Historical captures showed positive values during left turns and negative
  values during right turns.
- Current-PID validation on 2026-06-01 found the value can persist non-zero
  while stationary and can show `turnRateDelta=0.0` during a live turn
  stimulus; therefore it is **not proven as an instantaneous turn rate**.
- A paired 2026-06-01 camera-yaw review observed:
  - right mouse-look: promoted yaw `+25.413°`, `Δ0x304=-0.43499`
  - left mouse-look: promoted yaw `-25.413°`, `Δ0x304=+0.43999`
  - max error versus `-radians(ΔpromotedYaw)` was `0.00856`, so current
    evidence favors **yaw-adjacent scalar** semantics.
- Cross-checked against atan2-derived turn direction in the route planner only
  as candidate/support evidence unless the turn-rate promotion artifact exists
- Must remain candidate-only until left/right sign proof, non-zero live delta,
  settle-to-baseline behavior, no-drift proof, restart survival, and fresh
  current-PID readback gates pass

### 0x300 — Accumulated heading

- Monotonic counter, not a normalized angle
- Increases with every turn regardless of direction
- Useful as a "did we turn at all?" diagnostic, not for yaw calculation

## Neighborhood scan results

Last `pointer_owner_neighborhood_inspector.py` scan (2026-05-27, ±64KB around root):

| Finding | Count |
|---|---|
| Region matches | 380 |
| Module pointers (rift_x64.exe) | 379 |
| Owner-window module pointers | 4 |
| Exact owner pointer | **1** — `0x32EBC80` |
| Coordinate field pointers | 0 |

**Interpretation:** Only ONE module-RVA pointer reaches the owner object in the
scanned region. There is no backup chain in the immediate neighborhood.

## Pointer family scan results

Last `pointer_family_scan.py` (2026-05-27):

| Finding | Count |
|---|---|
| Scanned targets | 20 |
| Owner hits | 20 |
| Module hits | 1 |
| rift_x64.exe hits | 1 |
| Module hit address | `0x7FF77E22BC80` (=`rift_x64+0x32EBC80`) |

**Interpretation:** The owner is reachable from 20 different heap pointers, but
only ONE of those is a module-RVA pointer. All other paths are heap-to-heap
and won't survive a process restart.

## Behavior during combat (UNKNOWN)

The behavior of 0x30C during combat is **not yet characterized**:

- It might continue tracking camera facing (current assumption)
- It might snap to the selected enemy (would break yaw calculation)
- It might be the same as out-of-combat behavior

This needs a live discovery session with `rift-discovery` during combat.

## After a game update — what to re-validate

| Priority | Check | How |
|---|---|---|
| P0 | Root RVA still valid | AOB signature scan or `--scan-module-pattern` |
| P0 | Owner layout unchanged | Read owner+0x300 through +0x340, verify floats are plausible |
| P1 | 0x30C is still 0x14 before 0x320 | Neighborhood inspector scan for vec3 pairs 20 bytes apart |
| P2 | 0x304 yaw-adjacent scalar still tracks yaw | Run paired left/right camera-yaw classification and `riftreader-owner-0x304-semantics-review.cmd --json`; do not mark as turn-rate without a separate non-zero live delta proof |
| P3 | Full layout scan | Pointer owner neighborhood inspector, full window dump |
