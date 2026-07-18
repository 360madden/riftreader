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
| `relative` | `dx`, `dz` (optional `dy`) | Offset from **route start pose** (first sample) |
| `absolute` | `x`, `y?`, `z` | World coordinates (session/zone specific) |

Optional per-waypoint `arrivalRadius` overrides `defaultArrivalRadius` / CLI `--arrival-radius`.

## Run

```powershell
python scripts\c2m_run_to_goal.py --execute --stimulus-approved `
  --use-current-truth `
  --aim-mode w2s --pose-source static-chain `
  --waypoints-json scripts\routes\smoke-rel-L.json `
  --json
```

Truth bind is **on by default** (`--use-current-truth`). After a RIFT restart,
update `docs/recovery/current-truth.json` (or pass `--allow-target-drift` only for recovery).

## Samples

| File | Mode | Purpose |
|---|---|---|
| `smoke-rel-L.json` | relative | Portable L-shape smoke (5m +Z, then 3m +X) |
| `absolute-template.json` | absolute | Template — fill x/y/z from `static_owner_pose_now.py` |
