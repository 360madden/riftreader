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

## Recovery / Rebuild

If artifacts or notes are corrupted, start here:

- C:\RIFT MODDING\RiftReader\docs\recovery\README.md

## Post-Update Status (April 14, 2026)

The April 14, 2026 Rift update left the reader baseline partially intact but
drifted the owner/source discovery chain.

Current short version:

- `player-current` still works
- the coord-anchor module pattern still works
- source-chain refresh is broken
- selector-owner trace is broken
- actor-orientation and camera claims below are historical until rebuilt
- camera live workflow currently lives on
  `feature/camera-orientation-discovery`, not the `main` worktree

Use these first:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`

## Immediate Milestones

1. confirm reliable process targeting
2. establish a reusable memory read layer
3. use ReaderBridge exports plus grouped player-signature scans to narrow a first trustworthy candidate family
4. materialize that family in Cheat Engine for interactive validation
5. turn the winning layout back into a typed reader path
6. ship a first `--read-player-current` mode that reads level / health / coords and compares them against the latest ReaderBridge export
7. turn the first verified coord-triplet code access into a reader-usable anchor report via `--read-player-coord-anchor`
   - and compare that trace-derived sample back against current ReaderBridge ground truth
8. reject the first trace-derived destination object when it does not actually match current player state, then surface the traced upstream source object instead
   - and verify that the source-object coord sample does match current exported player state
9. trace the selector-owner path that chooses the source object and prove the stable owner/container/index -> source mapping
10. walk the stable owner object and classify its linked child wrappers around the selected source
    - source-wrapper
    - owner-backref wrapper
    - owner-state wrapper
11. enumerate the stable owner container itself and separate the live selected-source component from its sibling component records
12. classify the first stat-side graph around that owner/component table by identifying raw-unit-id-bearing identity components and shared level/resource hubs
13. reuse only validated fast paths for `--read-player-current` when they still belong to the current process and still match current exported player state
14. expose an actor-orientation helper via `--read-player-orientation` plus a capture script so live yaw/pitch experiments can compare repeated owner/source orientation samples and the full source basis matrix instead of rescanning blindly

Current discovery refinement:

Post-update note:

- as of April 14, 2026, only the player-current path and coord-anchor module
  pattern are currently revalidated on `main`
- the selected-source / selector-owner / owner-components / actor-orientation
  bullets below are historical until the chain is rebuilt on the updated client

- keep artifact freshness and provenance explicit before promoting a new anchor:
  - `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1`
    catches stale or cross-run capture drift early
  - `C:\RIFT MODDING\RiftReader\scripts\refresh-discovery-chain.ps1`
    refreshes the source-chain → selector-owner → owner-components →
    owner-graph → accessor-family → stat-hub sequence in one pass
- prefer directional CE next-scans after movement (`increased` / `decreased` / `changed`) over relying only on a second exact-value float scan
- reject debugger trace hits unless the traced instruction can be verified against the watched coord triplet (`x/y/z`)
- prefer tracing CE-confirmed moved-axis candidate addresses when available instead of assuming the default current-player sample is the best access target
- prefer actor-orientation work over camera-config work first when the goal is player/world-facing logic:
  - pre-update, the selected source component yielded the strongest actor-orientation vectors
  - pre-update, that selected source also exposed duplicated 3x3 basis blocks at `+0x60/+0x6C/+0x78` and `+0x94/+0xA0/+0xAC`
  - pre-update, `--read-player-orientation` plus `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1` produced repeatable yaw/pitch captures derived from the forward basis row
  - pre-update, `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1` validated actor-turn stimuli directly
  - pre-update, `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1` classified bindings that produced clean actor yaw changes vs no-turn/movement noise
  - current camera live workflow is branch-specific and lives on `feature/camera-orientation-discovery`, not `main`
- treat the owner container as a component table, not just a wrapper list:
  - pre-update, entry `6` behaved like the transform/source component
  - pre-update, indices `9`, `12`, and `13` behaved like identity-bearing siblings because they embedded the raw player unit id
  - pre-update, shared stat hubs clustered around `0x1AEE40A4600`, `0x1AEE411B4B0`, and `0x1AEBBF6E380`
- inspect a small disassembly cluster around any verified coord trace before promoting it, so nearby instructions using the same base register can be compared quickly
- derive a stronger pre-coord source chain from that cluster so we can pivot from the destination coord cache toward the likely source object/owner path
- once the source chain is found, isolate the accessor it calls so we can recognize stable returned field offsets such as the current coord-source `+0x48` path
- use `C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1` before trusting a new artifact chain, and `C:\RIFT MODDING\RiftReader\scripts\refresh-discovery-chain.ps1` when you want to rebuild the current chain in one pass
- keep the selected source / owner graph path as the main discovery path; treat the older cache-blob family as a bootstrap, not the final anchor
- keep CE and other mature reverse-engineering tools as the live acquisition workbench, but freeze each useful run into a repo-owned session package so decoding work can continue offline:
  - `C:\RIFT MODDING\RiftReader\scripts\export-discovery-watchset.ps1`
    derives the current schema-versioned named watchset from owner/source/stat artifacts
  - `C:\RIFT MODDING\RiftReader\scripts\record-discovery-session.ps1`
    packages the current artifacts, consistency report, ReaderBridge snapshot, and sampled watchset bytes into `scripts\sessions\...`, and now records timing drift, capture duration, interruption state, marker summaries, and per-region read summaries
  - `C:\RIFT MODDING\RiftReader\scripts\append-session-marker.ps1`
    appends normalized manual/scripted markers into a watched marker-input file during a live recording window
  - `dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --record-session ...`
    performs the actual one-attach sampling pass and supports burst/high-frequency intervals without changing the package contract
  - `dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --session-summary --session-directory ...`
    inspects a recorded package without attaching to a live process, loading the package manifest, recording manifest, samples, markers, and frozen ReaderBridge truth when available
  - see `C:\RIFT MODDING\RiftReader\docs\offline-session-workflow.md`

## Addon Boundary

The helper addon exists to reduce blind memory hunting, not replace the reader.

### Addon Capabilities

**RiftReaderValidator** (`/rrv` commands):
- Manual snapshot capture via `/rrv snapshot`
- Rolling history (default 64 samples)
- Auto-capture on zone/role/level changes and secure instance transitions
- In-game status window with indicator lights
- Fields captured: name, level, health/mana/energy/power/charge, combo, role, combat, zone, locationName, coords

**ReaderBridgeExport** (`/rbx` commands):
- Automatic export every 0.5 seconds (heartbeat)
- Exports ReaderBridge.State when available, falls back to direct API
- Extended telemetry: buffs/debuffs (top 5 each), castbar state, target distance, TTD estimator
- Party member snapshots (up to 5)
- Nearby unit enumeration (up to 10)
- Coord delta tracking for movement detection
- Raw `Inspect.Stat()` snapshot for class-specific stats

### Addon responsibilities:

- surface API-visible values that already exist in the client UI API
- mark important transitions such as zone, role, and combat-state changes
- keep lightweight history for manual comparison against memory reads
- provide ground-truth validation for memory reader anchors

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
- surface the traced upstream source object when the destination cache object proves to be a bad direct player anchor
- trace the selector-owner path so the source object is no longer just "the thing that had the right coords" but a selected child of a stable owning object/container/index relationship
- classify the owner-linked child wrappers so the graph around the selected source is explicit instead of a pile of ad hoc pointer notes
- opportunistically reuse only validated trace-backed anchors before falling back to grouped family reacquisition
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
