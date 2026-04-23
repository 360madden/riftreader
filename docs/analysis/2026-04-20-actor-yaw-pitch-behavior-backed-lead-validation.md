# 2026-04-20 actor-yaw / pitch behavior-backed lead validation

> **Historical / superseded note:** this April 20 validation is preserved for
> evidence only. For the living actor-facing truth and recovery workflow, see
> `docs/recovery/current-truth.md` and `docs/recovery/rebuild-runbook.md`.

## Scope

This note records the fresh no-CE live validation that re-established actor yaw
and pitch truth for the current `rift_x64` session on `main`.

## Fresh live truth

- source address: `0x1B115201EB0`
- truth-bearing forward row:
  - `+0xD4`
  - `+0xD8`
  - `+0xDC`
- up row:
  - `+0xE0`
  - `+0xE4`
  - `+0xE8`
- right row:
  - `+0xEC`
  - `+0xF0`
  - `+0xF4`

The current live basis at those offsets is orthonormal and meaningful:

- forward = `(-0.0574871, 0.0, -0.9983460)`
- up = `(0.0, 0.9999999, 0.0)`
- right = `(0.9983461, 0.0, -0.0574871)`

Derived truth:

- yaw = `atan2(forwardZ, forwardX)`
- pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

## Fresh live key proof

Fresh live validation on **April 20, 2026** used foreground `PostMessage`
stimulus only.

### `A` proof

- before yaw/pitch: `-93.2956 / 0.0000`
- after yaw/pitch: `63.0244 / 0.0000`
- yaw delta: `+156.3200`
- pitch delta: `0.0000`

### `D` proof

- before yaw/pitch: `63.0244 / 0.0000`
- after yaw/pitch: `-92.4286 / 0.0000`
- yaw delta: `-155.4530`
- pitch delta: `0.0000`

## Important correction

The historical `+0x60/+0x94` basis windows on this source are not current truth
on the updated client.

On the same live source:

- `+0x60/+0x6C/+0x78` reads garbage-sized floats
- `+0x94/+0xA0/+0xAC` is not the current actor-facing truth basis

So the repo must not keep preferring the historical `Orientation60` /
`Orientation94` path when the behavior-backed lead is available and still
validates live.

## Operational consequence

`C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1` now
needs to:

1. prefer the behavior-backed lead file when present
2. read the live source directly
3. validate the lead basis live
4. derive yaw / pitch from the validated `+0xD4` forward row
5. fail closed if that lead stops validating instead of silently falling back to
   stale owner-component recovery
