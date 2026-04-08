# Project Overview

## Project Shape

RiftReader is a hybrid project with two planned components:

- a **Lua addon** for in-game validation and comparison
- a **.NET 10 memory reader** for external data collection

## Current Implementation Scope

The **memory reader** remains the primary implementation target right now.

The current prototype should stay focused on:

- PTS-only process targeting
- safe read-only process attachment
- raw memory reads for investigation
- logging and output that can later be validated from the addon side
- a minimal in-game addon that acts as a validation harness, not the primary data source

## Environment Constraint

All active development and testing should assume the **Rift PTS test server**.

That means:

- no live-server assumptions
- no live-only data offsets or workflows
- no claims of compatibility beyond PTS until explicitly verified

## Immediate Milestones

1. confirm reliable PTS process targeting
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

- attach to the PTS process
- locate and read memory structures
- decode typed values that are not practical to derive from addon-visible state
- remain the authoritative implementation target for external data collection
