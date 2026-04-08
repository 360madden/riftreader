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
- a minimal in-game addon that acts as a validation harness, not the primary data source
- a reader CLI that can grow into robust switches, clear help, and colorized/highlighted menus

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
3. define the first useful data snapshot shape
4. prepare comparison points for future addon validation

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

## CLI UX Requirement

The reader CLI should be treated as a first-class tool, not a throwaway launcher.

Desired traits:

- extensive and robust switches as needed
- intuitive help text with examples
- colorized menus and warnings where the terminal supports them
- syntax-highlighted or otherwise visually distinct examples for easy copy/paste
- graceful fallback to plain text when color support is unavailable

See `C:\RIFT MODDING\RiftReader\docs\reader-cli-ux.md` for the full UX note.
