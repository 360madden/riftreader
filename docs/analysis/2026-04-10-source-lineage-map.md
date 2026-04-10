# Source Lineage Map (2026-04-10)

## Scope

This is an additive lineage map for the current discovery chain. It is meant to reduce rediscovery and make delegation safer.

Primary inputs reviewed:

- `scripts/captures/player-owner-components.json`
- `scripts/captures/player-selector-owner-trace.json`
- `scripts/captures/player-source-accessor-family.json`
- `scripts/captures/player-owner-graph.json`
- `scripts/captures/player-state-projector-trace.json`
- `scripts/captures/player-stat-hub-graph.json`
- `scripts/export-discovery-watchset.ps1`
- `docs/offline-session-workflow.md`

## Current practical object-family map

```text
selector / source-chain evidence
        ↓
owner-selected source component
        ↓
owner object
        ↓
owner container / component slots
        ↓
owner state record
        ↓
optional owner-state wrappers / projector slots
        ↓
optional ranked shared hubs / identity-bearing siblings
```

## Current addresses by artifact family

### Fresh owner-components lineage

From `player-owner-components.json`:

- owner address: `0x1AEBC2B4C10`
- owner container: `0x1AEF09444B0`
- selected source: `0x1AEF0941250`
- owner state record: `0x1AEBC2B4CD8`

From `player-selector-owner-trace.json`:

- owner object address: `0x1AEBC2B4C10`
- owner container address: `0x1AEF09444B0`
- selected source: `0x1AEF0941250`

This is the current preferred lineage.

### Older accessor / hub / projector lineage

From `player-source-accessor-family.json`:

- source object address: `0x1AEBA302B40`

From `player-owner-graph.json`:

- owner address: `0x1AED5A67610`
- selected source address: `0x1AEBA302B40`
- container address: `0x1AEE411B280`

From `player-state-projector-trace.json`:

- owner address: `0x1AED5A67610`
- state record: `0x1AED5A676D8`

From `player-stat-hub-graph.json`:

- owner address: `0x1AED5A67610`
- state record: `0x1AED5A676D8`
- selected source: `0x1AEBA302B40`

This second lineage is still useful, but it is stale relative to the current owner-components selection.

## Confidence split

### High confidence

- owner-components selected source
- selector owner trace
- owner address
- owner container
- current selected source object

These agree cleanly in the newest source-side captures.

### Medium confidence

- current owner state record in the owner-components family
- projector slot neighborhoods as secondary evidence
- owner-state wrappers

Useful, but they are not the current best orientation anchor.

### Lower confidence / optional stale-run evidence

- source accessor family
- owner graph
- projector family
- ranked shared hubs

These still look useful for stat-side work and lineage history, but they do not currently align with the freshest selected-source family.

## Why this matters

The repo's current watchset logic already prefers the owner-components lineage when artifacts disagree. That is the right bias for now.

Operationally:

- **orientation work** should stay anchored on the fresh selected-source family
- **state / hub work** can still mine the older owner/projector/hub family, but should be marked stale unless refreshed

## Immediate implication

Do not merge the two lineages mentally.

Right now there are effectively two families in play:

1. the **fresh selected-source transform family**
2. the **older owner/projector/hub family**

That split should stay explicit in future notes, prompts, and delegation packets.
