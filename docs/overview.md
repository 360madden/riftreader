# Project Overview

## Project Shape

RiftReader is a hybrid project with two planned components:

- a **Lua addon** for in-game validation and comparison
- a **.NET 10 memory reader** for external data collection

## Current Implementation Scope

The **memory reader** remains the primary implementation target right now.

The current prototype should stay focused on:

- explicit process targeting
- safe read-only process attachment
- raw memory reads for investigation
- logging and output that can later be validated from the addon side
- using Cheat Engine as the interactive discovery workbench when manual structure narrowing is faster than pure CLI scans
- a minimal in-game addon that acts as a validation harness, not the primary data source
- a reader CLI that can grow into robust switches, clear help, and colorized/highlighted menus

The implementation bias should now be:

- ship one narrow working reader path first
- use the addon export plus Cheat Engine only to support that path
- refine structure quality, anchors, and coverage after the first typed read is already useful

## Environment Constraint

Active development and testing should always identify the exact Rift client
environment being targeted.

That means:

- no environment assumptions without verification
- no offset or workflow claims that silently generalize across installs
- no compatibility claims beyond the environment actually tested

## Immediate Milestones

1. confirm reliable process targeting
2. establish a reusable memory read layer
3. use ReaderBridge exports plus grouped player-signature scans to narrow a first trustworthy candidate family
4. materialize that family in Cheat Engine for interactive validation
5. turn the winning layout back into a typed reader path
6. ship a first `--read-player-current` mode that reads level / health / coords and compares them against the latest ReaderBridge export
7. turn the first verified coord-triplet code access into a reader-usable anchor report via `--read-player-coord-anchor`
   - and compare that trace-derived sample back against current ReaderBridge ground truth
8. reuse that trace-derived object anchor as a fast path for `--read-player-current` when it belongs to the current process and still matches current exported player state

Current discovery refinement:

- prefer directional CE next-scans after movement (`increased` / `decreased` / `changed`) over relying only on a second exact-value float scan
- reject debugger trace hits unless the traced instruction can be verified against the watched coord triplet (`x/y/z`)
- prefer tracing CE-confirmed moved-axis candidate addresses when available instead of assuming the default current-player sample is the best access target
- inspect a small disassembly cluster around any verified coord trace before promoting it, so nearby instructions using the same base register can be compared quickly

## Addon Boundary

The helper addon exists to reduce blind memory hunting, not replace the reader.

Addon responsibilities:

- surface API-visible values that already exist in the client UI API
- mark important transitions such as zone, role, and combat-state changes
- keep lightweight history for manual comparison against memory reads

Reader responsibilities:

- attach to the intended Rift process
- locate and read memory structures
- decode typed values that are not practical to derive from addon-visible state
- remain the authoritative implementation target for external data collection

## Cheat Engine Boundary

Cheat Engine is now part of the workflow, but in a narrow role:

- **Cheat Engine**
  - interactive discovery
  - changed/unchanged narrowing
  - write/access tracing
  - quick structure inspection
- **RiftReader**
  - repeatable automation
  - grouped scan logic
  - exported helper generation
  - typed model implementation

See `C:\RIFT MODDING\RiftReader\docs\cheat-engine-workflow.md` for the current bridge between the two.

## First Working Product

The first working product does not need the full object model.

It only needs to:

- pick the current best player-family sample
- read a few trusted fields from that sample
- report whether they match the addon-exported ground truth
- reuse a validated cached sample address when it still matches current exported state so repeated reads stay fast
- expose the first verified code-path-backed coord anchor so later AOB/pointer work can build on something narrower than raw family rescans
- opportunistically reuse the trace-derived object base for repeated player reads before falling back to grouped family reacquisition
- allow that trace-derived object anchor to be refreshed on demand when the saved trace clearly belongs to an older Rift process, while keeping the default player-read path biased toward speed

That keeps the project moving toward a usable reader instead of spending too
long perfecting discovery infrastructure first.

## CLI UX Requirement

The reader CLI should be treated as a first-class tool, not a throwaway launcher.

Desired traits:

- extensive and robust switches as needed
- intuitive help text with examples
- colorized menus and warnings where the terminal supports them
- syntax-highlighted or otherwise visually distinct examples for easy copy/paste
- graceful fallback to plain text when color support is unavailable

See `C:\RIFT MODDING\RiftReader\docs\reader-cli-ux.md` for the full UX note.
