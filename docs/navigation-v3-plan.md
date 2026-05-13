# Navigation v3 plan

As of **April 23, 2026**, v3 work should promote navigation from a proven
single-segment reader path into a route-aware, still fail-closed movement
system. The current implementation now includes the first v3 slices:
read-only route-chain planning, a unit-tested route execution core, an
explicit active-input route CLI gate, and opt-in per-segment auto-turn.

## May 13, 2026 focus pivot

RiftReader's active product focus is **RIFT MMO navigation**. Static pointer
chain recovery, coordinate-family discovery, x64dbg, Cheat Engine, and
RiftScan coordination are supporting recovery lanes only when navigation is
blocked by stale or missing coordinate/facing truth.

Do **not** expand this repo into a general-purpose reverse-engineering product
as the next milestone. Build navigation capability first, and keep low-level
memory work narrowly scoped to the proof gates needed for safe navigation.

| Priority | Navigation-first meaning |
|---:|---|
| 1 | Keep visual gate, exact PID/HWND target selection, and current proof-anchor validation as the first live-input gates. |
| 2 | Resume from the newest navigation handoff/current-truth before any movement or auto-turn work. |
| 3 | Treat coordinate-family/static-chain work as dependency recovery, not as the repo's main deliverable. |
| 4 | Prefer no-turn observed-forward route proofs before turn/auto-facing experiments. |
| 5 | Promote actor-facing/turn backends only after current-PID evidence passes the documented proof gates. |

Offline navigation resume status can be generated without live input:

```powershell
python .\scripts\navigation_resume_status.py --write-summary --json
```

This helper reports the latest visual gate, `ProofOnly`, navigation run,
target-control status, turn-backend evidence, and navigation handoff. It is an
offline status report only; it does not prove currentness or grant movement
permission.

## V3 goals

| Priority | Goal | Promotion condition |
|---:|---|---|
| 1 | Route-chain planning | Ordered start / via / destination waypoints produce validated segment metadata before any live movement input |
| 2 | Route-chain execution | Each segment can run with strict coord-trace truth, optional auto-turn, and per-segment stop reasons |
| 3 | Terrain / obstacle policy | Stalls, moving-away, and blocked travel are classified without unsafe recovery loops |
| 4 | Repeatable live proofs | Aligned and deliberately misaligned route proofs can be repeated from the proof suite |
| 5 | Operator UX | Scripts/docs make active-input risk, foreground requirements, and current route state explicit |

## Implemented v3 slice: route-chain planning

Use the read-only route planner to validate a future multi-waypoint route
without sending movement input:

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --process-name rift_x64 `
  --plan-navigation-route `
  --start-waypoint smoke_start `
  --via-waypoint optional_midpoint `
  --destination-waypoint smoke_destination `
  --navigation-waypoint-file C:\RIFT MODDING\RiftReader\scripts\navigation\smoke-test-waypoints.json `
  --json
```

Current behavior:

| Behavior | Status |
|---|---|
| Builds ordered route IDs from `--start-waypoint`, repeated `--via-waypoint`, and `--destination-waypoint` | Done |
| Emits per-segment planar distance, height delta, bearing, arrival radius, and pace | Done |
| Fails closed for repeated/zero-distance route segments | Done |
| Fails closed for explicit cross-zone segments when both waypoint zones are known and different | Done |
| Sends movement input | Not in this slice |
| Performs obstacle recovery | Not in this slice |

## Implemented v3 slice: route execution core

The route execution core is now exposed through an explicit active-input CLI
gate. This is still a v3-prep path: per-segment auto-turn and live two-segment
proof-suite promotion remains pending.

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- `
  --process-name rift_x64 `
  --navigate-waypoint-route `
  --start-waypoint smoke_start `
  --via-waypoint optional_midpoint `
  --destination-waypoint smoke_destination `
  --navigation-waypoint-file C:\RIFT MODDING\RiftReader\scripts\navigation\smoke-test-waypoints.json `
  --auto-turn-before-move `
  --json
```

Current behavior:

| Behavior | Status |
|---|---|
| Builds a route plan before any segment execution | Done |
| Refuses to read coordinates or send input when the route plan is invalid | Done |
| Runs planned segments sequentially through the existing single-segment navigator | Done |
| Preserves per-segment `NavigationRunResult` payloads in a route-level result | Done |
| Stops the route on the first failed segment and reports its segment index | Done |
| Uses the prior waypoint arrival radius as the next segment start tolerance floor | Done |
| Provides route-level text output for aggregate and per-segment results | Done |
| CLI active multi-segment movement command | Done behind explicit `--navigate-waypoint-route` |
| Per-segment auto-turn before every segment | Done behind opt-in `--auto-turn-before-move` |
| Proof-suite route-plan segment assertions | Done for read-only smoke route planning |
| Live two-segment proof-suite route | Pending |

## Next execution slices

| # | Slice | Work |
|---:|---|---|
| 1 | Live route proof | Add a two-segment smoke route proof after single-segment active proofs stay green |
| 2 | Active route assertions | Assert route-run segment and turn status in the proof suite once active route proof is enabled |
| 3 | Terrain classification | Split `no-progress` into blocked/stalled/telemetry categories using existing event evidence |
| 4 | Operator guardrails | Keep active route docs/scripts explicit about foreground, terrain, and proof-anchor requirements |
| 5 | Route tuning | Decide whether route mode needs per-segment pace/timeout overrides beyond waypoint config |
