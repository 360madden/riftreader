# RiftReader Validation Addon Spec

## Purpose

`RiftReaderValidator` is a helper addon for the hybrid RiftReader project.

It exists to support the external memory reader by supplying:

- API-visible player state snapshots
- low-noise transition markers
- a rolling saved-variable history for side-by-side comparison

It is **not** intended to replace the reader or become the main data source.

## Scope

### In scope

- manual snapshot capture from the in-game API
- saved-variable persistence of recent validation samples
- a small slash-command surface for testing
- automatic capture on a few meaningful state changes
- a compact status GUI with indicator lights for manual validation work

### Out of scope

- full UI overlays
- heavy event spam logging
- arbitrary automation
- hard environment-specific compatibility guarantees without verification
- any dependency from the reader on the addon for core functionality

## Data Contract v1

### RiftReaderValidator Snapshot Schema

Each snapshot captures the following **player-visible** state:

| Field | Type | Source |
|-------|------|--------|
| `sequence` | number | Incrementing counter |
| `reason` | string | Capture trigger (manual, event, auto) |
| `capturedAt` | number | `Inspect.Time.Real()` timestamp |
| `playerUnit` | string | Unit ID from `Inspect.Unit.Lookup("player")` |
| `name` | string | `Inspect.Unit.Detail().name` |
| `level` | number | `Inspect.Unit.Detail().level` |
| `health` | number | `Inspect.Unit.Detail().health` |
| `healthMax` | number | `Inspect.Unit.Detail().healthMax` |
| `mana` | number | `Inspect.Unit.Detail().mana` |
| `manaMax` | number | `Inspect.Unit.Detail().manaMax` |
| `energy` | number | `Inspect.Unit.Detail().energy` |
| `energyMax` | number | `Inspect.Unit.Detail().energyMax` |
| `power` | number | `Inspect.Unit.Detail().power` |
| `charge` | number | `Inspect.Unit.Detail().charge` |
| `chargeMax` | number | `Inspect.Unit.Detail().chargeMax` |
| `combo` | number | `Inspect.Unit.Detail().combo` |
| `role` | string | `Inspect.Unit.Detail().role` |
| `combat` | boolean | `Inspect.Unit.Detail().combat` |
| `zone` | string | `Inspect.Unit.Detail().zone` |
| `locationName` | string | `Inspect.Unit.Detail().locationName` |
| `coord` | table | `{x, y, z}` from `coordX/Y/Z` fields |

### ReaderBridgeExport Snapshot Schema

Extended schema with additional telemetry:

| Field | Type | Source |
|-------|------|--------|
| `schemaVersion` | number | Export format version |
| `status` | string | `"ready"` or `"waiting-for-player"` |
| `exportReason` | string | Trigger reason |
| `generatedAtRealtime` | number | `Inspect.Time.Real()` timestamp |
| `sourceMode` | string | `"ReaderBridge"` or `"DirectAPI"` |
| `sourceAddon` | string | Source addon name |
| `exportAddon` | string | `"ReaderBridgeExport"` |
| `exportVersion` | string | Addon version |
| `hud` | table | HUD state (visible, locked, showBuffPanel) |
| `player` | table | Player unit snapshot (see below) |
| `target` | table | Target unit snapshot (see below) |
| `playerId` | string | Player unit ID |
| `targetId` | string | Target unit ID |
| `playerBuffLines` | array | Top 5 buff descriptions |
| `playerDebuffLines` | array | Top 5 debuff descriptions |
| `targetBuffLines` | array | Target's top 5 buffs |
| `targetDebuffLines` | array | Target's top 5 debuffs |
| `playerStats` | table | Raw `Inspect.Stat()` snapshot |
| `playerCoordDelta` | table | Movement delta since last update |
| `nearbyUnits` | array | Up to 10 units from `Inspect.Unit.List()` |
| `partyUnits` | array | Up to 5 party members |

#### Player/Target Unit Fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Unit ID |
| `name` | string | Display name |
| `level` | number | Unit level |
| `calling` | string | Class archetype |
| `guild` | string | Guild name |
| `relation` | string | Relation to player |
| `role` | string | Combat role |
| `player` | boolean | Is player character |
| `combat` | boolean | In combat flag |
| `pvp` | boolean | In PvP flag |
| `hp` / `hpMax` / `hpPct` | number | Health values |
| `absorb` | number | Absorb shield |
| `vitality` | number | Vitality stat |
| `resourceKind` | string | Primary resource type (Mana/Energy/Power/Charge) |
| `resource` / `resourceMax` / `resourcePct` | number | Primary resource values |
| `mana` / `manaMax` | number | Mana fields |
| `energy` / `energyMax` | number | Energy fields |
| `power` | number | Power field |
| `charge` / `chargeMax` / `chargePct` | number | Charge fields |
| `planar` / `planarMax` / `planarPct` | number | Planar attunement |
| `combo` | number | Combo points |
| `zone` | string | Zone name |
| `locationName` | string | Sub-zone name |
| `coord` | table | `{x, y, z}` coordinates |
| `cast` | table | Castbar state (active, abilityName, duration, remaining, etc.) |
| `distance` | number | 3D distance to player (target only) |
| `ttd` / `ttdText` | number/string | Time-to-death estimate (target only) |

This is intentionally narrow. The reader should later grow its own typed models and only use addon data as a comparison surface.

## Capture Rules

### Manual capture

Primary path for early reverse-engineering work.

Commands:

- `/rrv snapshot`
- `/rrv status`
- `/rrv clear`
- `/rrv ui`
- `/rrv help`

### Automatic capture

The addon should auto-capture only on a few low-frequency markers:

- startup
- player zone changes
- player role changes
- player level changes
- secure enter / leave events as a combat-adjacent marker

Health, mana, power, and similar rapidly changing values should be captured manually at first to avoid noisy sample history.

## Persistence Model

Snapshots are stored in one character-scoped saved variable table:

- `RiftReaderValidator_State`

The table should keep:

- session metadata
- settings
- latest snapshot
- a rolling sample buffer
- the next sequence number

Recommended default rolling history:

- `64` samples

## Basic GUI

The addon should expose a lightweight in-game status window for manual testing.

The first GUI pass should include:

- visible indicator lights for:
  - addon loaded
  - player unit available
  - last snapshot freshness
  - secure/combat-adjacent mode
- a compact current snapshot summary
- a small recent-activity list
- buttons for snapshot, refresh, clear, and hide

This GUI is a testing aid only. It should remain lightweight and should not evolve into a large gameplay UI.

## Reader Correlation Workflow

1. Position the player in a known state.
2. Trigger `/rrv snapshot`.
3. Immediately run the C# reader against the intended Rift process.
4. Compare:
   - timestamp window
   - sequence number
   - known API-visible fields
5. Promote confirmed matches into typed reader models.

## Folder Layout

```text
addon/
└── RiftReaderValidator/
    ├── README.md
    ├── RiftAddon.toc
    └── main.lua
```

## Known Limits

- The addon only sees what the Rift addon API exposes.
- It cannot validate structures that are fully hidden from the API.
- The exact `Environment` value in `RiftAddon.toc` may need to be updated if the current client expects a newer addon API environment.

## Next Implementation Targets

1. add a typed export format shared with the reader docs
2. add a small comparison checklist for the first memory target
3. extend snapshots only after the first reader-to-addon field match is confirmed
