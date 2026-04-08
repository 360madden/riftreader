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

## Data Contract v0

Each snapshot should capture a compact subset of **player-visible** state:

- sequence number
- capture reason
- capture timestamp
- player unit id
- name
- level
- health / healthMax
- mana / manaMax
- energy / energyMax
- power
- charge / chargeMax
- combo
- role
- combat state
- zone
- location name
- raw coord payload if available from the API

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
