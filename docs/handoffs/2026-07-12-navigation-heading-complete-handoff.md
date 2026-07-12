# 2026-07-12 — Navigation & heading complete handoff

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` up to date with `origin/main` at `2ec2208` |
| Worktree | Dirty: `scripts/resolve-player-coords.py` modified; untracked `.local/`, `artifacts/screenshots/`, `facing-calibrate.py`, `facing-scan-movement.py` |
| RIFT PID | Not tracked in this session — no live RIFT target |

## Milestones achieved

| # | Milestone | Status |
|---|---|---|
| 1 | **Heading discovered** — `[[[0x32EBDC0]+0x330]+0x158]` = single float in radians, 0° offset from camera direction | **PROMOTED** |
| 2 | **Turn calibration** — 172°/s for both left and right (C# SendInput hold) | **PROMOTED** |
| 3 | **nav6** — aim-then-walk navigation using heading (3-7 steps, 2-3 units/step) | **PASSED** |
| 4 | **nav7** — multi-waypoint router chaining nav6 (3/3 waypoints) | **PASSED** |
| 5 | **nav8** — full nav system: A* pathfinding, obstacle detection (4 recovery strategies), zone detection, targeting | **PASSED** |
| 6 | **FreshState** — validates pointer chain before every read, detects stale reads, waits for movement to complete | **PASSED** |
| 7 | **Facing restart survival** — ASLR base change handled by module enumeration, pointer chain intact, turn calibration 172°/s still accurate | **PASSED** |
| 8 | **Navmesh overlay** — tkinter overlay with Record/Stop/Navigate buttons, scroll zoom, right-click drag pan, left-click waypoints | **PASSED** |

## Key files

| Path | Purpose |
|---|---|
| `scripts/nav6.py` | Aim-then-walk navigation using heading |
| `scripts/nav7.py` | Multi-waypoint router chaining nav6 |
| `scripts/nav8.py` | Full nav: A* pathfinding, obstacle detection, zone detection, targeting |
| `scripts/navmesh-overlay.py` | Tkinter overlay with Record/Stop/Navigate buttons |
| `scripts/record-navmesh.py` | Record positions while human walks |
| `scripts/read-player-facing.py` | Player facing reader using heading at +0x158 |
| `scripts/resolve-player-coords.py` | Production coord resolver (modified: added camera child offset constants) |
| `tools/RiftReader.SendInput/` | C# SendInput for reliable key delivery |
| `artifacts/memory-dumps/2026-07-12/` | 2GB memory dump + manifest |

## How to resume

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
python scripts/nav8.py
python scripts/navmesh-overlay.py
python scripts/read-player-facing.py
python scripts/resolve-player-coords.py
```

## Validation already run

- nav6: 3-7 steps, 2-3 units/step — passed
- nav7: 3/3 waypoints — passed
- nav8: A* pathfinding, obstacle detection, zone detection, targeting — passed
- Facing restart survival: ASLR base change handled, pointer chain intact, turn calibration 172°/s still accurate — passed
- Turn calibration: 172°/s for both left and right — confirmed

## Not validated

- No live RIFT target in this session — all nav tests were from prior sessions
- No navmesh expansion beyond existing 90 nodes
- No swimming/falling detection
- No movement state flags
