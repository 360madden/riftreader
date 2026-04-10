# Orientation Evidence Report (2026-04-10)

## Scope

This report is additive only. It summarizes the current actor-orientation evidence already present in the repo and capture set without changing any existing tool or workflow.

Primary inputs reviewed:

- `README.md`
- `reader/RiftReader.Reader/Models/PlayerOrientationReader.cs`
- `reader/RiftReader.Reader/Models/PlayerOwnerComponentRanker.cs`
- `scripts/captures/player-owner-components.json`
- `scripts/captures/player-actor-orientation.json`
- `scripts/captures/actor-orientation-key-profile.json`

## Current conclusion

The strongest current reading is:

- the **owner-selected source component** is the transform/orientation-bearing object
- the **owner/state/hub side** is more likely the stat-bearing family
- actor yaw/pitch are currently being derived from the **forward row** of the selected source basis matrix

This is not just commentary. It is consistent across the README, the typed reader path, the owner-component ranker, and the current live capture files.

## Evidence

### 1. Reader design is actor-oriented, not camera-oriented

The current reader path for `--read-player-orientation` reuses the owner-selected source component and derives yaw/pitch from the live source basis matrix.

The current selected source also exposes duplicated 3x3 basis blocks:

- `+0x60 / +0x6C / +0x78`
- `+0x94 / +0xA0 / +0xAC`

The helper treats these as primary and duplicate basis blocks.

### 2. The live capture points to a single selected source object

Current capture set:

- selected source address: `0x1AEF0941250`
- selected entry address: `0x1AEF0941250`
- selected entry index: `6`

The selected entry role hints currently include:

- `selected-source`
- `coord48-match`
- `coord88-match`
- `orientation60-match`
- `orientation94-match`

That is unusually strong agreement for the current transform candidate.

### 3. Live coord agreement is strong

The live source object exposes duplicated coordinate triplets at:

- `+0x48`
- `+0x88`

Current capture says both source coord snapshots match the ReaderBridge player coordinates.

### 4. Basis quality is strong

From `player-actor-orientation.json`:

- preferred basis: `Basis60`
- determinant: `0.999999906152682`
- orthonormal: `true`
- forward/up/right dot products: near zero
- duplicate-basis max row delta: `0.0`

That is the strongest current sign that this is not random float noise. It behaves like a valid local basis.

### 5. Key-stimulus profiling supports actor-turn interpretation

From `actor-orientation-key-profile.json`:

- `Left` -> classified `actor-turn`
- `Right` -> classified `actor-turn`
- `Q`, `E`, `Up`, `Space` -> classified `no-turn`

Current results also show:

- large yaw change for left/right
- zero pitch change
- zero coord drift
- determinant staying near `1.0`
- duplicate-basis disagreement remaining extremely small

That is the expected shape for clean actor-facing changes.

## What is currently strongest

### Proven by current evidence

- the selected source family is the current best actor-orientation candidate
- the forward row in the selected source basis can be turned into stable yaw
- the duplicate basis block is currently in full agreement with the primary block
- left/right stimuli produce yaw change without coord drift in the current environment

### Supported but not fully proven yet

- the selected source basis is the final authoritative actor-facing truth in all movement states
- no better nearby orientation field exists in the same family
- the same behavior will remain stable across mounts, swimming, vertical movement, knockback, and scripted motion

## Immediate implications

This repo should continue to treat the selected source basis as the primary actor-orientation anchor until contrary evidence appears.

That does **not** justify broad refactors. It justifies:

- more additive evidence gathering around the same source family
- better capture labeling
- better basis integrity reporting
- better provenance tracking for stale lineage splits

## Next narrow step

Use the current orientation path as the baseline truth candidate and evaluate it under controlled edge cases rather than broadening the search prematurely.
