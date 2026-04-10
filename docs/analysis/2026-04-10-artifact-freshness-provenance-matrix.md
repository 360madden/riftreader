# Artifact Freshness and Provenance Matrix (2026-04-10)

## Scope

This is an additive freshness/provenance summary for the current capture set. The goal is to make stale lineage splits obvious before any new discovery work is assigned.

Primary inputs reviewed from `scripts/captures/`:

- `player-owner-components.json`
- `player-selector-owner-trace.json`
- `player-source-accessor-family.json`
- `player-source-chain.json`
- `player-owner-graph.json`
- `player-state-projector-trace.json`
- `player-stat-hub-graph.json`
- `player-current-anchor.json`
- `player-actor-orientation.json`
- `actor-orientation-key-profile.json`

## Summary judgment

The capture set currently contains **two different lineages**:

1. a **fresh selected-source lineage** centered on `0x1AEF0941250`
2. an **older owner/projector/hub lineage** centered on `0x1AEBA302B40` and owner `0x1AED5A67610`

That split is the most important provenance fact in the current repo snapshot.

## Matrix

| Artifact | Generated (UTC) | Primary lineage | Freshness | Notes |
|---|---:|---|---|---|
| `player-selector-owner-trace.json` | 2026-04-09 06:19:37 | selected source `0x1AEF0941250`, owner `0x1AEBC2B4C10` | Fresh | Aligns with owner-components lineage |
| `player-owner-components.json` | 2026-04-09 06:20:31 | selected source `0x1AEF0941250`, owner `0x1AEBC2B4C10`, container `0x1AEF09444B0`, state `0x1AEBC2B4CD8` | Fresh | Best current source-side anchor |
| `player-actor-orientation.json` | 2026-04-09 06:26:35 | selected source `0x1AEF0941250` | Fresh | Built from current owner-components artifact |
| `actor-orientation-key-profile.json` | 2026-04-09 06:26:22 | selected source family behavior | Fresh | Confirms left/right turn behavior |
| `player-source-chain.json` | 2026-04-09 02:22:40 | older source chain | Older | Still useful for discovery history |
| `player-source-accessor-family.json` | 2026-04-09 02:36:05 | source `0x1AEBA302B40` | Stale vs fresh source | Does not match current owner-components selected source |
| `player-owner-graph.json` | 2026-04-09 03:12:31 | owner `0x1AED5A67610`, source `0x1AEBA302B40` | Stale vs fresh source | Still useful for state/projector side |
| `player-state-projector-trace.json` | 2026-04-09 03:43:21 | owner `0x1AED5A67610`, state `0x1AED5A676D8` | Stale vs fresh owner | Secondary evidence only until refreshed |
| `player-stat-hub-graph.json` | 2026-04-09 04:36:09 | owner `0x1AED5A67610`, source `0x1AEBA302B40` | Stale vs fresh source | Good candidate pool, but not current transform family |
| `player-current-anchor.json` | 2026-04-09 01:37:17 | cache/blob family | Legacy bootstrap | Useful for bootstrap only, not current source truth |

## Current preferred lineage

Current preferred lineage should be:

- selected source: `0x1AEF0941250`
- owner: `0x1AEBC2B4C10`
- container: `0x1AEF09444B0`
- state record: `0x1AEBC2B4CD8`

Reason:

- it is the newest consistent source-side chain
- selector trace agrees with it
- current live orientation capture agrees with it
- current key-profile evidence agrees with it

## Current stale lineage

The following should be treated as stale-run lineage until refreshed:

- source `0x1AEBA302B40`
- owner `0x1AED5A67610`
- state record `0x1AED5A676D8`

This lineage is still valuable for state-side exploration, hub mining, and history, but it should not be confused with the freshest selected-source transform family.

## Operational guidance

### Safe default
When source families disagree, prefer the newest owner-components lineage for orientation work.

### Safe caveat
Do not discard the older projector/hub lineage. Mark it stale and use it deliberately for secondary work.

### Immediate implication
Future reports, prompts, and delegation packets should explicitly state which lineage they are using.
