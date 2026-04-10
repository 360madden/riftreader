# Basis Integrity and Invariant Report (2026-04-10)

## Scope

This report evaluates whether the current selected-source basis behaves like a real actor-facing frame rather than random float noise.

Primary inputs reviewed:

- `scripts/captures/player-actor-orientation.json`
- `scripts/captures/player-actor-orientation.previous.json`
- `scripts/captures/actor-orientation-key-profile.json`
- `scripts/captures/player-owner-components.json`

## Current judgment

The current selected-source basis is **structurally strong**.

It behaves like a clean, nearly orthonormal actor-facing frame with duplicated agreement between the primary and duplicate basis blocks.

## Current selected source

- selected source address: `0x1AEF0941250`
- selected entry index: `6`

The current live capture resolves both the selected source address and the selected entry to the same object.

## Basis quality from current live capture

From `player-actor-orientation.json`:

### Basis60
- determinant: `0.999999906152682`
- orthonormal: `true`
- forward dot up: `0.0`
- up dot right: `0.0`
- forward dot right: `1.3556533229319712e-08`

### Basis94
- determinant: `0.999999906152682`
- orthonormal: `true`
- forward dot up: `0.0`
- up dot right: `0.0`
- forward dot right: `1.3556533229319712e-08`

### Duplicate-basis agreement
- forward delta magnitude: `0.0`
- up delta magnitude: `0.0`
- right delta magnitude: `0.0`
- max row delta magnitude: `0.0`

## Interpretation

These are exactly the invariants expected from a stable local basis:

- determinant very close to `1`
- row vectors nearly unit length
- cross-axis dot products near `0`
- full agreement between the duplicated basis blocks

That is much stronger evidence than simply finding one plausible forward vector.

## Forward-row behavior

Current preferred forward row:

- `X = -0.10310710966587067`
- `Y = 0.0`
- `Z = 0.9946702122688293`

Derived from the current capture:

- yaw degrees: `95.9181202534254`
- pitch degrees: `0.0`
- magnitude: `0.9999999536192828`

This is consistent with a flat-ground actor-facing vector.

## Right and up rows

Current right row:

- `X = -0.9946702718734741`
- `Y = 0.0`
- `Z = -0.10310710221529007`
- magnitude: `1.0000000121380426`

Current up row:

- `X = 0.0`
- `Y = 0.9999999403953552`
- `Z = 0.0`
- magnitude: `0.9999999403953552`

This is the expected shape for an upright actor on level ground:

- up is effectively world-up
- forward lies in the horizontal plane
- right is a horizontal perpendicular

## Key-profile evidence

From `actor-orientation-key-profile.json`:

### Keys classified as actor-turn
- `Left`
- `Right`

### Keys classified as no-turn
- `Q`
- `E`
- `Up`
- `Space`

### Turn signatures
- `Left` yaw delta: `+120.4866185134546`
- `Right` yaw delta: `-120.43703166779102`
- pitch delta remained `0.0`
- coord delta magnitude remained `0.0`

Basis quality stayed strong after those turn stimuli:

- determinant remained near `1`
- duplicate-basis disagreement stayed tiny or zero
- forward `Y` stayed `0`

## Risk assessment

### Low-risk conclusions
- the selected-source basis is not random noise
- the basis is currently internally self-consistent
- left/right turn stimuli move yaw without introducing coord drift
- the duplicated basis block is a strong built-in integrity check

### Remaining edge cases
Still not proven from this capture set alone:

- vertical look / pitch states
- non-flat terrain
- airborne states
- mounts
- knockback / scripted forced movement
- any state where world-up and actor-up diverge

## Current recommendation

Treat the selected-source duplicated basis as the current best actor-orientation anchor.

Use duplicate-basis agreement and determinant stability as the first integrity gates for all future orientation captures.
