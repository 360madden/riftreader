# Branch Workboard — `codex/dashboard-hud`

Updated: 2026-04-15

## Purpose

This board tracks the display-only, branch-aware dashboard work on
`codex/dashboard-hud`.

The dashboard is intentionally static: it compiles git state, docs, and capture
artifacts into a browser-readable snapshot without introducing a backend.

## Critical-path rule

Keep these decisions local:

1. what data the dashboard is allowed to present as current truth,
2. which branches get rich branch-local coverage,
3. when a UI affordance is ready enough to expose as part of the default flow,
4. when a branch should remain generic instead of gaining hard-coded richness.

Everything else should stay narrow, reviewable, and easy to regenerate from the
repo.

## Now

| Item | Lane | Why now |
|---|---|---|
| Keep the current branch dashboard summary tied to real source files and git state | Integrator | The active branch should not regress to placeholder-only status. |
| Keep actor and camera branches aligned with the docs and artifacts that feed their rich views | Data | Dashboard trust depends on upstream branch truth staying coherent. |
| Keep source-file freshness visible in the UI | UX | Makes stale snapshot risk obvious during handoff and review. |

## Parallel now

| Item | Lane | Output required |
|---|---|---|
| Keep the rebuild-and-open launcher working as dashboard files move | Tooling | launcher stays current + no broken entrypoint |
| Keep dashboard usage docs aligned with the real workflow | Docs | README reflects regenerate/open steps |
| Keep generic branches readable even when they only have fallback metadata | UX | no confusing empty states or bogus rich-data claims |

## Next

| Item | Lane | Trigger |
|---|---|---|
| Add a lightweight dashboard generator smoke check | Tooling | after the current data shape settles |
| Move branch-specific config out of hard-coded switches | Architecture | after rich branch coverage stops moving around |
| Run a browser visual pass on narrower widths | UX | after the current dashboard cards and labels stabilize |

## Parked

| Item | Reason parked |
|---|---|
| Live auto-refresh | static snapshots are the intended v1 model |
| Inline editing/actions from the dashboard | out of scope for the display-only branch |
| Adding a backend or service layer | unnecessary for the current repo workflow |

## Definition of ready for handoff

The branch is ready to hand off when:

1. the active branch view is rich and no longer placeholder-only,
2. the rich non-current branches still compile from real docs/artifacts,
3. the launcher and README match the current regenerate/open flow,
4. the next improvement step is captured in the handoff doc.
