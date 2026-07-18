# C2M route files

JSON routes for `scripts/c2m_run_to_goal.py --waypoints-json <path>`.

## Schema

```json
{
  "schemaVersion": 1,
  "kind": "riftreader-c2m-route",
  "name": "smoke-rel-L",
  "coordinateMode": "relative",
  "defaultArrivalRadius": 2.5,
  "notes": "optional",
  "zoneHint": "optional operator note",
  "waypoints": [
    { "id": "leg1", "dx": 0.0, "dz": 5.0 },
    { "id": "leg2", "dx": 3.0, "dz": 0.0, "arrivalRadius": 2.0 }
  ]
}
```

| `coordinateMode` | Waypoint fields | Meaning |
|---|---|---|
| `relative` | `dx`, `dz` (optional `dy`) | Offset from **route start pose**. With `relativeFrame: "heading"` (default CLI), **dx=right, dz=forward** along facing — prefer this so you face open ground instead of world-axis into rocks/trees. |
| `relative` | `forward`, `right` | Explicit heading-frame meters (optional) |
| `absolute` | `x`, `y?`, `z` | World coordinates (session/zone specific; can hit props if path is blind) |

**Obstacle note:** C2M has no navmesh. If stuck, the runner aims a **lateral detour** (side of path) then resumes. Still face open ground before absolute/world-axis routes.

**NPC collision:** navigation **ignores** friendly / neutral / hostile NPCs as blockers. Detours and future navmesh are for **terrain/props only**, not unit avoidance.

Optional per-waypoint `arrivalRadius` overrides `defaultArrivalRadius` / CLI `--arrival-radius`.

## Run

```powershell
python scripts\c2m_run_to_goal.py --execute --stimulus-approved `
  --use-current-truth `
  --aim-mode w2s --pose-source static-chain `
  --waypoints-json scripts\routes\smoke-rel-L.json `
  --json
```

Truth bind is **on by default** (`--use-current-truth`). C2M **uses current-truth**
for PID/HWND/process-start/root RVA and fail-closes on mismatch.

After a RIFT restart: **rebind truth target** (not the root RVA on this binary —
root `0x32E07C0` is restart-survivable). See
`docs/recovery/c2m-truth-bind-and-static-chain-restart-survival.md`.

Recovery-only: `--allow-target-drift` (does not update truth).

### Known-good sample

| File | Notes |
|---|---|
| `safe-handpicked-a.json` | Operator-walked absolute path (~56 m) |
| `safe-handpicked-a-reverse.json` | Same path reverse (start at last mark) |

## Samples

| File | Mode | Purpose |
|---|---|---|
| `smoke-rel-L.json` | relative | Portable L-shape smoke (5m +Z, then 3m +X) |
| `absolute-template.json` | absolute | Template — fill x/y/z from `static_owner_pose_now.py` |
