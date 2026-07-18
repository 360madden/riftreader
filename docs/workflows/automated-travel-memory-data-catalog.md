# Automated travel memory data catalog

**Purpose:** Durable inventory of every memory field, derived value, window metric,
and consumer contract needed for automated travel — coordinates, facing/yaw/pitch,
camera/FOV, world-to-screen / click-to-move, navmesh tooling, and Godot (or other)
overlay markers/waypoints.

**When to use:** Building or recovering navigation, navmesh recording, overlay
apps, click-to-move, or any consumer that needs a full pose + projection bundle.

**Authority order (when sources disagree):**

1. Live code behavior in `scripts/` and `reader/`
2. `docs/recovery/current-truth.md` (current epoch status)
3. This catalog
4. `docs/workflows/owner-layout-reference.md`
5. Dated handoffs under `docs/handoffs/` and `docs/handoff-*.md`

**Status (as of 2026-07-18 evening):**

| Layer | Status |
|---|---|
| **Current promoted root** | **`0x32E07C0`** — restart-survivable on this binary; see `current-truth.md` |
| **C2M ↔ truth** | **Yes** — `c2m_run_to_goal` defaults to `--use-current-truth` (fail closed) |
| Pre-patch July layout (`0x32EBDC0`) | **Historical** — null on this binary; do not use |
| May–June formal root (`0x32EBC80`) | **Historical** — dead on this binary |
| Live automated travel (MVP) | **Unblocked** for static pose + in-game C2M multi-WP (SendInput + W2S) |
| Milestone notes | `docs/recovery/progress-2026-07-18-post-patch-root-and-c2m.md` |
| **C2M / restart contract (library)** | `docs/recovery/c2m-truth-bind-and-static-chain-restart-survival.md` |

Still re-bind PID/HWND/process-start every session (truth target rebind). Root RVA
survives restart; heap owner does not. Re-validate P0 fields after patches.

---

## 1. What automated travel needs (capability map)

| Capability | Minimum data | Nice-to-have |
|---|---|---|
| Stay on a path / aim-then-walk | Player `X/Y/Z` + heading (yaw) + turn calibration | Speed, movement-complete detect |
| Multi-waypoint route | Pose + waypoint list + arrival radius | A* navmesh graph |
| Navmesh record / paint | Player `X/Z` (and `Y`) at sample rate + zone id | Obstacles, water flags |
| Overlay markers on map | Player pose + waypoints + scale/pan transform | Zone bounds, path polyline |
| World overlay / Godot 3D markers | Player pose + camera + FOV + clip + HWND client size | View matrix, aspect, DPI |
| Click-to-move / click ground | World→screen projection + HWND + client rect | Cursor depth, click backend proof |
| Obstacle recovery | Pose history + heading | Terrain/prop stuck flags (not NPCs) |
| Freshness / fail-closed | PID, HWND, process start, module base, timestamps | API-now coordinate cross-check |

**Navigation collision policy (locked):** pathing / navmesh **do not** treat
**friendly, neutral, or hostile NPCs** as collision or blocked cells. Avoid rocks,
trees, geometry, and unwalkable terrain only. Unit lists may still be used later
for combat or target selection — **not** for walkability.

---

## 2. Classification legend

| Class | Meaning | Consumer rule |
|---|---|---|
| **P0-required** | Must resolve every session for automated travel | Fail closed if missing/null/stale |
| **P1-control** | Required for aim-then-walk / turn planning | Prefer direct heading; fallback only if documented |
| **P2-projection** | Required for W2S, click-to-move, 3D overlay | Fail closed for those features only |
| **P3-support** | Diagnostics / heuristics | Never sole route-control authority |
| **Historical** | Pre-update or alternate chain | Revalidate before use |
| **Gap** | Needed conceptually; not durable/proven | Do not invent; discover under gates |

Promotion classes (orthogonal to priority):

| Promotion | Meaning |
|---|---|
| **Promoted (epoch)** | Passed formal gates for a named binary epoch |
| **Practically validated** | Drove live nav tests; formal promotion packet incomplete |
| **Candidate** | Evidence only |
| **Blocked (current)** | Not usable on the installed post-patch binary |

---

## 3. Target identity bundle (always first)

Exact-target binding is not optional. Every pose sample must carry this bundle.

| Field | Source | Type | Class | Notes |
|---|---|---|---|---|
| `processName` | Process enumeration | string | P0 | Usually `rift_x64` |
| `processId` | Process enumeration | u32 | P0 | Fail on drift |
| `targetWindowHandle` | Window enum / title `RIFT` | HWND hex | P0 | Exact HWND for input backends |
| `processStartUtc` | Process creation time | ISO-8601 | P0 | Restart epoch guard |
| `moduleBase` | Module snapshot (`rift_x64.exe`) | u64 | P0 | ASLR base for all RVAs |
| `moduleFileName` | Module path | path | P1 | Binary identity |
| `exeSha256` / size | File hash of installed exe | string / int | P1 | Detect patches (see current-truth) |
| `recordedAtUtc` | Wall clock sample time | ISO-8601 | P0 | Freshness |

**Fail-closed rules:**

- Any mismatch of PID / HWND / process-start vs the bound target → stop.
- Module base must be re-read after restart; never hardcode absolute owner addresses.
- Coordinate claims require **API-now vs memory-now** within tolerance when claiming “current.”

Helpers:

| Helper | Role |
|---|---|
| `scripts/static_owner_coordinate_chain_readback.py` | Promoted static readback path (when root valid) |
| `scripts/resolve-player-coords.py` | July chain resolver + camera child constants |
| `scripts/riftreader-decision-packet.cmd` | Blockers + safe next action |
| `scripts/riftreader-navigation-consumer-state.cmd` | Read-only consumer pose contract |

---

## 4. Coordinate owner object (player pose root)

### 4.1 Static root (resolver entry)

Two RVAs appear in repo history. They are **epoch-specific**, not interchangeable
without re-proof.

| Epoch / label | Root expression | Owner offsets | Status |
|---|---|---|---|
| May–June 2026 formal promotion | `[rift_x64+0x32EBC80]` | `+0x320/+0x324/+0x328` coords; `+0x30C/+0x310/+0x314` facing target | Promoted for that epoch; **stale after later binary drift** |
| July 2026 nav session | `[rift_x64+0x32EBDC0]` | Same owner layout family + camera child `+0x330` | Practically validated for nav6–nav8; **null root post-2026-07-14 patch** |
| **Current promoted (2026-07-18)** | **`[rift_x64+0x32E07C0]`** | `+0x320/+0x324/+0x328` coords; `+0x330` camera; heading `[[cam]+0x158]` | **Live promoted + restart-survivable** (RVA); C2M uses via `current-truth` — see `docs/recovery/c2m-truth-bind-and-static-chain-restart-survival.md` |

```text
# Conceptual chain (when root non-null)
moduleBase = base of rift_x64.exe
owner      = read_ptr(moduleBase + ROOT_RVA)   # fail if 0 / non-heap
x,y,z      = read_f32(owner + 0x320/0x324/0x328)
```

### 4.2 Owner-relative fields (pose + support)

Offsets are relative to the **owner / coord object** pointer.

| Offset | Type | Field | Class | Promotion notes | Consumer use |
|---|---|---|---|---|---|
| `+0x320` | f32 | Player **X** | P0-required | Promoted (epoch); revalidate post-patch | Position, distance, navmesh |
| `+0x324` | f32 | Player **Y** (elevation) | P0-required | Promoted (epoch) | 3D distance, vertical gates |
| `+0x328` | f32 | Player **Z** | P0-required | Promoted (epoch) | Planar nav (`X/Z`) |
| `+0x30C` | f32 | Facing-target **X** | P1-control | Promoted (epoch) as look-at point | Yaw via atan2 vs player pos |
| `+0x310` | f32 | Facing-target **Y** | P1-control | Promoted (epoch) | Pitch-ish elevation of look-at |
| `+0x314` | f32 | Facing-target **Z** | P1-control | Promoted (epoch) | Yaw via atan2 |
| `+0x300` | f32 | Cumulative rotation counter | P3-support | Not direct heading | “Did we turn?” diagnostic |
| `+0x304` | f32 | Yaw-adjacent scalar / historical “turn rate” | P3-support | Candidate only; **not** proven active turn rate | Diagnostic; do not control turns from this alone |
| `+0x308` | f32 | Adjacent support | P3-support | Unproven | Research only |
| `+0x318` | ptr/gap | Often zero / dormant | P3 | — | Ignore for travel |
| `+0x330` | ptr | **Camera-state child** | P1 / P2 | July practical validation | Heading, FOV, W2S |
| `+0x90` | ptr | Look-ahead target child | P3 / alt facing | Candidate | Alternate yaw: atan2(target−player) |
| `+0x180` | ptr | Entity-like child | Gap / research | Candidate | Nearby entity experiments |

#### Derived yaw from facing target (May–June path)

```text
yaw_rad = atan2( (owner+0x314) - (owner+0x328),
                 (owner+0x30C) - (owner+0x320) )
yaw_deg = degrees(yaw_rad)
```

- Facing target is a **look-at point ~10 m ahead**, not an NPC.
- Guard zero vector `(0,0,0)` on zone-in — treat as blocked, not heading 0°.

#### Direct heading (July path — preferred for aim-then-walk when available)

```text
camera = read_ptr(owner + 0x330)
heading_rad = read_f32(camera + 0x158)
heading_deg = degrees(heading_rad)
```

- Calibrated **0.0° offset** vs camera direction vector.
- Round-trip turn residual ~0.15° in discovery notes.
- Used by `nav6` / `nav7` / `nav8` / `FreshState` in July work.
- Formal gate-by-gate promotion packet is incomplete; classify as
  **practically validated**, not immortal current truth.

---

## 5. Camera-state child (`owner+0x330`)

Required for FOV, world-to-screen, click-to-move, and Godot 3D overlays.

| Offset (in child) | Type | Field | Class | Typical / notes |
|---|---|---|---|---|
| `+0x08` | f32 | Camera position **X** | P2-projection | Orbit camera world X |
| `+0x0C` | f32 | Camera position **Y** | P2-projection | |
| `+0x10` | f32 | Camera position **Z** | P2-projection | |
| `+0x14` | f32 | Player position **X** (camera copy) | P3-support | Cross-check vs owner `+0x320` |
| `+0x18` | f32 | Player position **Y** | P3-support | |
| `+0x1C` | f32 | Player position **Z** | P3-support | |
| `+0x2C` | f32 | Direction **X** (normalized) | P1 / P2 | Heading cross-check `atan2(dx,dz)` |
| `+0x30` | f32 | Direction **Y** | P2 / pitch | Vertical component of view |
| `+0x34` | f32 | Direction **Z** (normalized) | P1 / P2 | |
| `+0x38` | f32 | **FOV** (degrees) | P2-projection | Observed **75°** |
| `+0x3C` | f32 | Near clip | P2-projection | Observed **0.1** |
| `+0x40` | f32 | Far clip | P2-projection | Observed **2400** |
| `+0x158` | f32 | **Heading (radians)** | P1-control | Preferred July nav heading |

### Derived camera quantities

| Derived | Formula | Use |
|---|---|---|
| Camera yaw (deg) | `degrees(atan2(dir_x, dir_z))` | Cross-check heading |
| Camera pitch (deg) | `degrees(atan2(dir_y, hypot(dir_x, dir_z)))` | Vertical look estimate |
| Camera distance | distance(cam_pos, player_pos) | Orbit radius; overlay scale sanity |
| Aspect ratio | `clientWidth / clientHeight` | From HWND, not memory |
| Focal length | `1 / tan(radians(fov)/2)` | W2S |

### World-to-screen (click-to-move / markers)

Implemented in `scripts/world-to-screen.py` (July; mark as **not fully proof-gated**):

1. Read camera position, direction, FOV from child.
2. Build camera basis: forward = dir; right = normalize(forward × world_up); up = right × forward.
3. Transform world point into camera space `(cx, cy, cz)`.
4. Reject if `cz < near` (behind / too close).
5. Project with FOV + aspect into NDC, then client pixels.
6. Click backends: exact-HWND `PostMessage` client coords, or screen `SetCursorPos` (legacy).

**Required extra window fields for W2S / click:**

| Field | Source | Class |
|---|---|---|
| Client width / height | `GetClientRect(hwnd)` | P2 |
| Client origin on screen | `ClientToScreen` | P2 |
| DPI / scale | Win32 DPI APIs | P2 if multi-monitor / scaled |
| Click backend | C# SendInput / WindowMessage | Gated live input |

---

## 6. Pitch and full orientation

| Source | Status | Notes |
|---|---|---|
| Camera `dir_y` + planar length | **Best practical pitch estimate** | From camera child direction |
| Facing-target elevation `owner+0x310` vs player Y | Partial | Look-at elevation, not pure pitch |
| Historical actor basis matrix `+0x60/+0x6C/+0x78` | Historical | Pre-update; revalidate before use |
| Direct pitch scalar in owner | **Gap** | Camera branch notes: direct pitch unresolved historically |
| RIFT Lua API heading/pitch | **Not exposed** | API gives coords only |

Automated travel **does not require pitch** for ground aim-then-walk. Pitch is
required for 3D reticle overlays, camera-relative flight, and some click-on-entity
cases.

---

## 7. Movement control data (not pure memory, but required)

Automated travel needs calibrated **input** metadata alongside memory pose.

| Item | Proven value / source | Class | Notes |
|---|---|---|---|
| Turn rate | **~172°/s** left/right (July, C# SendInput hold) | P1-control | Recalibrate after input backend or patch change |
| Prefer backend | `tools/RiftReader.SendInput` via `scripts/send-rift-key-csharp.ps1` `--input-mode ScanCode` | P1 | Policy: C# scancode first |
| Fallback backend | `post-rift-key.ps1` WindowMessage exact HWND | P1 | Proven leaf |
| Keys | W forward, A/D turn, optional S | P1 | Chat/text mode is operator-managed |
| Step length heuristic | 2–3 units / pulse (nav6 notes) | P3 | Environment-dependent |
| Arrival radius | Waypoint field (default consumer-normalized) | P0 for multi-WP | Schema: `arrivalRadius` |
| Movement-complete wait | FreshState / settle readback | P1 | Avoid reading mid-slide as arrived |
| Stuck / no-progress | Distance not improving over N samples | P1 | Fail closed |

**Hard policy:** live movement, displacement stimulus, ProofOnly, and promotion
remain **approval-gated**. Cataloging a field does not authorize sending input.

---

## 8. API / runtime truth surfaces (validation, not memory)

Use these to prove memory is current — never as sole mid-run movement truth unless
the surface is explicitly live.

| Surface | Live? | Fields useful for travel | Rule |
|---|---|---|---|
| ChromaLink `/api/v1/riftreader/world-state` | Yes (when bridge up) | coords, zone, etc. | Preferred API-now when available |
| RiftReaderApiProbe / RRAPICOORD | Live overlay string | Player coords | API-now cross-check |
| ReaderBridge in-game runtime | Live in client | coords | Live surface OK |
| `ReaderBridgeExport.lua` SavedVariables | **Post-save only** | coords snapshot | **Never** live truth during movement |
| Inspect.Unit.Detail coords | Addon API | `coordX/Y/Z` | Ground truth for validation |

Every freshness result should record: API coord + time, memory coord + address/chain,
PID/HWND/process-start, per-axis deltas, tolerance, verdict.

---

## 9. Window + overlay geometry (map overlay and Godot)

### 9.1 Map-style navmesh overlay (2D top-down)

Used by `scripts/navmesh-overlay.py` (tkinter). Needs:

| Data | Source |
|---|---|
| Player `X/Z` (optionally `Y`) | Owner coords |
| Navmesh nodes / edges | Recorded JSON graph |
| Waypoints | Clicked or file-backed list |
| View scale / pan | Overlay UI state |
| Sample interval while recording | e.g. 500 ms |

No FOV required for pure top-down map. Optional heading arrow uses heading/yaw.

### 9.2 Godot (or any 3D) game overlay

Minimum bundle per frame / tick for markers that track world space:

```json
{
  "schemaVersion": 1,
  "kind": "riftreader-travel-pose-frame",
  "recordedAtUtc": "ISO-8601",
  "target": {
    "processId": 0,
    "targetWindowHandle": "0x0",
    "processStartUtc": "ISO-8601",
    "moduleBase": "0x0"
  },
  "resolver": {
    "rootRva": "0x32EBDC0",
    "owner": "0x0",
    "camera": "0x0",
    "epochStatus": "blocked|candidate|validated"
  },
  "player": {
    "x": 0.0, "y": 0.0, "z": 0.0,
    "headingRadians": 0.0,
    "headingDegrees": 0.0,
    "yawSource": "camera+0x158|facing-target-atan2|unknown"
  },
  "camera": {
    "x": 0.0, "y": 0.0, "z": 0.0,
    "dirX": 0.0, "dirY": 0.0, "dirZ": 0.0,
    "fovDegrees": 75.0,
    "nearClip": 0.1,
    "farClip": 2400.0
  },
  "window": {
    "clientWidth": 0,
    "clientHeight": 0,
    "clientLeftScreen": 0,
    "clientTopScreen": 0
  },
  "waypoints": [],
  "markers": [],
  "safety": {
    "movementSent": false,
    "inputSent": false,
    "routeControlAuthorized": false
  }
}
```

Godot side uses:

| Godot need | Catalog field |
|---|---|
| Player gizmo | `player.x/y/z` + heading |
| World markers | `markers[]` / `waypoints[]` world coords |
| Camera match (optional) | `camera.*` + FOV + aspect from window |
| Screen-space labels | W2S using camera + window |
| Click ground | W2S inverse or cast from click → world (future) |

**Coordinate convention note:** RIFT travel planning commonly treats **planar**
motion as `X/Z` with `Y` elevation. Confirm handedness when importing into Godot
(remap axes explicitly; do not assume Unity-style).

### 9.3 Waypoint file contract (repo schema)

Canonical schema: `docs/schemas/navigation/normalized-waypoints.schema.json`.

| Field | Type | Required |
|---|---|---|
| `id` | string | yes |
| `label` | string | yes |
| `x`, `y`, `z` | number | yes |
| `arrivalRadius` | number ≥ 0 | yes |

Provenance should prefer `forward-key-movement-bearing` for route metadata when
present (see `docs/navigation-waypoint-v1.md`).

Consumer pose contract: `docs/schemas/navigation/navigation-consumer-state.schema.json`
and `docs/workflows/navigation-consumer-contract.md`.

---

## 10. Navmesh application data

| Asset | Contents | Produced by | Travel role |
|---|---|---|---|
| Navmesh node graph | Sampled walkable `X/Z` (+ optional `Y`), connectivity, `grid_size` | `scripts/record-navmesh.py`, overlay Record | A* pathfinding (`nav8`) |
| Zone label | Zone / location string | API / addon | Segment routes by zone |
| Obstacle samples | Failed move cells / blocked edges | Recovery strategies in nav8 | Avoid loops |
| Recorded trail | Timestamped pose series | Overlay recording | Rebuild mesh |
| Path polyline | Ordered nodes for active route | A* | Overlay draw + execution |

**Minimum node fields:**

| Field | Type | Notes |
|---|---|---|
| `x`, `z` | float | Planar position |
| `y` | float optional | Elevation for slopes |
| `id` / grid key | string/int | Stable identity |
| `neighbors` | id[] | Graph edges |
| `flags` | bitset optional | water / steep / blocked — mostly **Gap** |

---

## 11. Recommended pose poll set (one read cycle)

When the static root is valid, a single automated-travel sample should read:

| # | Read | Bytes | Why |
|---|---|---|---|
| 1 | `moduleBase + ROOT_RVA` → owner | 8 | Root |
| 2 | owner `+0x320`..`+0x328` | 12 | Position |
| 3 | owner `+0x330` → camera | 8 | Child |
| 4 | camera `+0x158` | 4 | Heading |
| 5 | camera `+0x08`..`+0x40` | ~0x3C | Cam pos, player copy, dir, FOV, clip |
| 6 | owner `+0x30C`..`+0x314` | 12 | Facing-target backup yaw |
| 7 | HWND client rect | OS | Overlay / W2S |

Optional / diagnostic: `+0x300`, `+0x304`, look-ahead `+0x90` child.

Emit one JSON frame matching §9.2 for Godot / overlay / nav controller.

---

## 12. Feature → field dependency matrix

| Feature | Must have | Should have | Optional |
|---|---|---|---|
| Live map dot | PID + `X/Z` | Heading | Zone |
| Record navmesh | PID + `X/Z` + sample clock | `Y`, zone | Speed |
| Aim-then-walk to waypoint | `X/Y/Z` + heading + turn rate + input backend | Movement settle | Speed `0x304` |
| Multi-waypoint | Above + waypoint file | A* mesh | Obstacles |
| Top-down overlay markers | Pose + waypoints + pan/zoom | Heading arrow | Path |
| Godot 3D markers | Pose + camera + FOV + client size | Pitch from dir | Full view matrix |
| Click-to-move | Camera + FOV + client size + click backend | Depth/reject behind cam | Cursor feedback |
| API freshness gate | Memory pose + live API coords | ChromaLink freshness | — |
| Restart survival | Module base rediscovery + same ROOT_RVA | Owner signature | AOB |

---

## 13. Known gaps (do not invent)

| Gap | Why it matters | Suggested discovery path |
|---|---|---|
| Post-patch static root | **Resolved 2026-07-18** as `0x32E07C0` | Keep for next patch: API match → module ptr scan / Ghidra |
| Direct pitch scalar | Camera look / flight | Camera child neighborhood + look stimulus |
| True view/projection matrix | Higher-quality W2S | Scan near FOV/clip; compare to constructed basis |
| Movement state flags (walk/run/swim/fall/mount) | Mode-aware control | Displacement + ability/API correlation |
| Collision / stuck native flag | Better recovery than distance heuristic | — |
| Combat effect on `0x30C` facing target | Yaw stability in combat | Approved discovery session |
| Entity list for dynamic obstacles | Avoid NPCs | Entity child `+0x180` research |
| Zone bounds for mesh clip | Multi-zone routes | API zone + recorded edges |
| Inverse screen→world for click ground | True click-to-move | Ray from camera through click NDC |

---

## 14. Safety and promotion gates (travel consumers)

Before any consumer claims “can auto-travel”:

| Gate | Requirement |
|---|---|
| Exact target | PID/HWND/process-start match |
| Root non-null | Owner pointer valid heap |
| Coord API-now | Memory vs live API within tolerance |
| Heading consistent | `+0x158` vs camera dir (or facing-target) within bound |
| Restart survival | Chain survives relog/restart on **current** binary |
| No SavedVariables-as-live | Declared truth surface is live |
| Input approval | Separate explicit approval for movement / click |
| No CE/x64dbg unless approved | Default no-attach |
| Route control flag | Consumers keep `routeControlAuthorized=false` until gates pass |

Formal promotion artifacts live under `docs/recovery/static-owner-*-promoted-*.md`
and capture summaries under `scripts/captures/`. Handoff prose alone is not promotion.

---

## 15. Primary code and doc references

| Path | Role |
|---|---|
| `docs/recovery/current-truth.md` | Current epoch blocker / target |
| `docs/workflows/owner-layout-reference.md` | Owner field map (May–June promotion epoch) |
| `docs/handoff-2026-07-12-facing.md` | July camera/heading/FOV structure |
| `docs/handoffs/2026-07-12-navigation-heading-complete-handoff.md` | nav6–nav8 + overlay milestone |
| `docs/navigation-waypoint-v1.md` | Reader waypoint navigation v1 |
| `docs/workflows/navigation-consumer-contract.md` | External consumer pose rules |
| `docs/schemas/navigation/` | JSON schemas for waypoints / consumer / live-run |
| `docs/workflows/navigation-route.md` | Route execution workflow |
| `scripts/resolve-player-coords.py` | Coord chain + camera offsets |
| `scripts/read-player-facing.py` | Facing from camera dir |
| `scripts/world-to-screen.py` | FOV projection + click helper |
| `scripts/nav6.py` / `nav7.py` / `nav8.py` | Aim-then-walk → multi-WP → A* |
| `scripts/navmesh-overlay.py` | Map overlay + record/navigate UI |
| `scripts/record-navmesh.py` | Mesh recording |
| `tools/RiftReader.SendInput` | Preferred input backend |

---

## 16. Post-patch recovery note (2026-07-18)

**Resolved for this binary:** root **`0x32E07C0`** promoted after restart survival,
three-pose displacement, and API-now match. Details:
`docs/recovery/progress-2026-07-18-post-patch-root-and-c2m.md`.

| Do not use | Why |
|---|---|
| `0x32EBC80` | Pre-May/June epoch; dead on this exe |
| `0x32EBDC0` | July interim; **null** on current process |

After the **next** patch: follow
`optimized-post-update-recovery-workflow.md` (session seed → static promote).
Offline Ghidra remains useful if module scan fails:

```powershell
.\scripts\riftreader-ghidra-static-evidence.cmd --run --binary-path 'C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe' --json
```

---

## 17. Maintenance

When a field is re-proven or a patch lands:

1. Update **§4–§5** offsets and promotion class.
2. Point **§3** / epoch table at new `current-truth.md` facts.
3. Bump any machine consumer schema if JSON shape changes.
4. Keep this file as the **catalog**; keep dated proof in `docs/recovery/` and
   `scripts/captures/`.

**Last updated:** 2026-07-18  
**Document kind:** durable catalog (not a live truth pointer)
