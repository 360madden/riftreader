# Project Overview

## Project Shape

RiftReader is a hybrid project with two planned components:

- a **Lua addon** for in-game validation and comparison
- a **.NET 10 memory reader** for external data collection

## Current Implementation Scope

Only the **memory reader** is in scope right now.

The current prototype should stay focused on:

- PTS-only process targeting
- safe read-only process attachment
- raw memory reads for investigation
- logging and output that can later be validated from the addon side

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
