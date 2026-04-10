# Watchset Coverage Audit for Orientation Work (2026-04-10)

## Scope

This is an additive audit of the current session-watchset coverage for actor-orientation work.

Primary inputs reviewed:

- `scripts/export-discovery-watchset.ps1`
- `docs/offline-session-workflow.md`
- `reader/RiftReader.Reader/Program.cs`
- current capture files under `scripts/captures/`

## Current judgment

For actor-orientation work, the watchset is already **good enough for targeted evidence capture** around the selected source family.

It is **not yet a strong offline replay/analysis workflow** because timing, markers, and post-processing are still thin.

## Regions already covered well

The watchset currently captures these selected-source regions:

- `selected-source-object` — 384 bytes
- `selected-source-coord48` — 12 bytes
- `selected-source-basis60` — 36 bytes
- `selected-source-coord88` — 12 bytes
- `selected-source-basis94` — 36 bytes

That already preserves:

- both duplicated coord triplets
- both duplicated basis blocks
- the broader selected-source neighborhood

This is the core of current actor-orientation work.

## Nearby family context already covered

The watchset also captures:

- owner object
- owner container slots
- owner state record
- selected-source slot in the owner container
- optional owner-state wrappers
- optional projector slot neighborhoods
- optional ranked shared hubs
- optional hub field neighborhoods
- optional bootstrap cache window

That is enough family context for source-side orientation work and some secondary state-side comparisons.

## What is weak

### 1. Default session cadence is coarse

The owned session flow currently defaults to sparse timeline sampling. That is acceptable for broad state changes, but weak for fine turn dynamics.

### 2. Marker richness is minimal

Current session markers are limited to:

- session start
- label
- session end

That is not enough for reliable offline interpretation of turn intent.

### 3. No offline analyzer exists yet

The session package stores evidence, but the repo does not yet have a dedicated offline orientation-session analyzer that turns recorded samples into a structured turn report.

## Orientation-specific gaps

These are the main remaining coverage gaps for orientation work:

- semantic breakout of each basis row/column as first-class watchset entries
- richer turn/move stimulus markers
- a lightweight analyzer over saved orientation sessions
- higher-cadence burst sampling mode for tight turn windows

## Current recommendation

Do **not** broaden the watchset aggressively yet.

The current selected-source coverage is already the right first layer. The bigger gain now is to improve **interpretation**, not raw breadth.

Best next additive improvements:

1. preserve the current selected-source focus
2. add better marker vocabulary
3. add an offline basis/session analyzer
4. only widen source-adjacent neighborhoods if current edge-case tests fail
