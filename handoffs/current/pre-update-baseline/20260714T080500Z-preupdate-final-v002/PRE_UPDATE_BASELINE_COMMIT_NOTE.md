# Pre-Update Baseline Commit Note — 2026-07-14

## Intent

Preserve read-only pre-patch recovery evidence before the RIFT server shutdown / Glyph client update.

## Staged paths (explicit allowlist)

- `handoffs/current/PRE_UPDATE_SERVER_SHUTDOWN_HANDOFF_2026-07-14.md`
- `handoffs/current/pre-update-baseline/20260714T075857Z-preupdate-capture-v001/`
- `handoffs/current/pre-update-baseline/20260714T080500Z-preupdate-final-v002/`
- `signatures/rift_x64/root_coord-root-32ebdc0.json`
- `signatures/rift_x64/root_preupdate-final-coord-root.json`
- `scripts/resolve-player-coords.py` (add `0x7FF63CA90000` known module base)

## Not staged

- `scripts/captures/*` runtime capture dirs (repo-local evidence; referenced by handoff paths)
- `docs/recovery/current-truth.md` (separate dirty slice)
- Untracked helper drafts (`scripts/facing-*.py`, `mcps/`, `.local/`)

## Resume

```
PRE_UPDATE_SERVER_SHUTDOWN_HANDOFF_2026-07-14.md
```

Generated UTC: 2026-07-14T08:10:00Z