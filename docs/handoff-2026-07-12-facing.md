# Handoff: 2026-07-12 — Facing Discovery Session

## Status: ✅ MILESTONE — Heading angle found

## Goal
Resolve player facing/heading from RIFT's dynamic memory for navmesh navigation.

## Key Finding
**Heading angle is a single float at `[[[0x32EBDC0]+0x330]+0x158]` in radians.** No atan2 needed.

```
heading_rad = read_float(pid, coord_obj_ptr + 0x330_child + 0x158)
heading_deg = degrees(heading_rad)
```

**Calibration:** 0.0° offset from camera direction vector. Round-trip test: 0.15° delta.

## All Facing Sources (ranked by simplicity)

| # | Source | Chain | Offset | Method |
|---|--------|-------|--------|--------|
| 1 | Heading float | `[[[0x32EBDC0]+0x330]+0x158]` | 0.0° | Direct read |
| 2 | Camera direction | `[[0x32EBDC0]+0x330]+0x2c/+0x34]` | 0.0° | atan2(dx,dz) |
| 3 | Look-ahead target | `[[0x32EBDC0]+0x90]+0x14/+0x28]` | 0.7° | atan2(tx-px, tz-pz) |

## Object Structure (confirmed)

```
Coord Object (+0x320/+0x324/+0x328 = X/Y/Z)
├── +0x300: cumulative rotation counter (NOT heading)
├── +0x304: turn rate (unstable)
├── +0x318: all zeros (dead)
├── +0x330: Camera state object
│   ├── +0x08/+0x0c/+0x10: camera position
│   ├── +0x14/+0x18/+0x1c: player position
│   ├── +0x2c/+0x30/+0x34: direction vector (normalized)
│   ├── +0x38: FOV (75°)
│   ├── +0x3c: near clip (0.1)
│   ├── +0x40: far clip (2400)
│   └── +0x158: **HEADING IN RADIANS**
├── +0x90: Look-ahead target
│   ├── +0x14/+0x18/+0x1c: target position
│   └── +0x28/+0x2c/+0x30: current position
├── +0x180: Entity-like object
│   ├── +0x19c/+0x1a0/+0x1a4: coord set 1
│   ├── +0x1b0/+0x1b4/+0x1b8: coord set 2 (matches player)
│   ├── +0x190: movement counter
│   ├── +0x1c0: shared camera state pointer
│   └── +0x1f0: player ID
```

## Files Created This Session

| File | Purpose |
|------|---------|
| `scripts/read-player-facing.py` | Dynamic base discovery + heading read |
| `scripts/facing-calibrate.py` | Camera direction calibration (0° offset) |
| `scripts/facing-verify-target.py` | Look-ahead target turn test |
| `scripts/facing-test-158.py` | +0x158 as heading angle test |
| `scripts/facing-calibrate-158.py` | +0x158 vs camera direction (exact match) |
| `scripts/facing-investigate-obj.py` | Object structure analysis |
| `scripts/facing-investigate-180.py` | +0x180 entity structure |
| `scripts/facing-scan-heap-nearby.py` | Heap scan for other entities |
| `scripts/dump-process-memory.py` | 2GB memory dump (6.3s) |
| `scripts/world-to-screen.py` | Screen projection (not tested) |

## Git Commits

```
8dbdf6f  facing discovery: look-ahead target position at +0x90
eaec74f  facing: +0x330 child +0x158 IS heading in radians — 0° offset
a0d8ef7  facing discovery: +0x158 heading, +0x180 structure, entity scan
```

## Next Steps

1. **Wire +0x158 heading into nav5.py** — replace displacement-based facing
2. **Validate heading across RIFT restarts** — is the +0x158 offset constant?
3. **Implement aim-then-walk navigation** — turn to face waypoint, walk forward
4. **Use Ghidra on 2GB dump** — trace what writes to +0x158
5. **Investigate +0x180 as NPC structure** — the 10-unit offset might be entity range
