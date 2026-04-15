# Dashboard Branch Handoff — `codex/dashboard-hud`

Date: 2026-04-15

## Current state

- the dashboard remains **display-only** and compiles a static snapshot into
  `tools/dashboard/dashboard-data.js`
- the active branch now needs its own rich summary rather than placeholder-only
  metadata
- actor recovery and camera discovery should remain wired to their real docs and
  capture artifacts
- the dashboard should be easy to regenerate and open without remembering manual
  file paths

## What changed recently

- added richer branch-local coverage beyond `codex/actor-yaw-pitch`
- surfaced source-file freshness in the UI
- kept the dashboard as a static browser app rather than adding a backend

## Recommended first action in the next conversation

1. Keep the current branch summary, launcher flow, and source-file coverage aligned with the actual dashboard files before widening the schema again.
2. Add a lightweight smoke check once the data shape stops moving.
3. Only then consider moving branch-specific config into a small data file.
