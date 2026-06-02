# RiftReader Handoff — Target-current resolver repair — 2026-06-02 04:39 UTC

## Summary

The Phase 1 C# `--read-target-current` blocker is repaired for the current
selected-target packet. The previous blocker was
`target-current-family-resolution-failed:fam-CEC3708F`.

| Evidence | Result |
|---|---|
| Root cause 1 | Target acceptance required name and distance matches even though target-family samples normally do not read those optional fields; `Distance` was always `null`. |
| Root cause 2 | Target-family ranking favored high-volume coord-only families, allowing `fam-CEC3708F` to outrank the lower-count full object family with level/health. |
| Code repair | `TargetCurrentReader` now treats name/distance as optional readback fields and `TargetSignatureProbeCaptureBuilder` ranks full coord+level+health matches before coord-only hit count. |
| Live readback | `dotnet run --project .\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-target-current --json` passed. |
| Phase 1 helper | `scripts\riftreader-phase1-target-entity-snapshot.cmd --json` passed. |
| New Phase 1 artifact | `scripts\captures\phase1-target-entity-snapshot-20260602-043904-933361\summary.json`; verdict `phase1-target-current-reader-passed`. |
| Resolved family | Reader now resolves `fam-6F81F26E` from the target-current path. |
| Memory address | `0x1E036430920`; level `45`; health `18208`; coords `(7251.04, 821.44, 2987.8699)`. |

## Safety notes

- This repair used read-only process memory access only.
- No live input, movement, `/reloadui`, screenshot key, Cheat Engine, x64dbg,
  provider writes, target memory writes, proof promotion, actor-chain promotion,
  branch rewrite, or remote mutation was performed by the repair validation.
- `ReaderBridgeExport.lua` remains a post-flush SavedVariables snapshot, not
  live IPC truth.
- The selected target in this packet is still self-target `Atank`; repeat Phase
  1 with a non-self selected target once target selection is reliable.

## Current next action

Repeat Phase 1 with a non-self selected target, then use the passing target
reader output as the seed for selected-target memory/entity discovery.
