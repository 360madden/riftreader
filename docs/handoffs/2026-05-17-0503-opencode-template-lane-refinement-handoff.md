# Compact handoff — OpenCode template lane refinement

Generated UTC: `2026-05-17T09:03:18Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

The tracked OpenCode config template now describes the new compact lanes more
explicitly: read-only SITREP prefers compact status, validator treats exit `2`
from status helpers as a safe blocker, package/applier defaults to compact
dry-run before any approved apply, and live observer runs no-input triage/status
while preserving stale proof as historical.

## Implemented files

| Path | Purpose |
|---|---|
| `.opencode/opencode.example.jsonc` | Refines agent prompts around compact SITREP, package dry-run, validation blockers, and no-input live observation. |
| `docs/workflow/opencode-non-codex-bridge.md` | Adds a concise table of template agents and their default lanes. |

## Safety

No permissions were relaxed for Git mutation, live input, movement, CE/x64dbg,
provider writes, or secret handling. Package intake remains ask-gated in the
template; `--apply` remains explicit-approval only.

## Resume point

Next safe OpenCode slice: create a final compact milestone handoff/index of the
OpenCode bridge commands added in this pass, then stop if no further safe
OpenCode/non-Codex integration gap remains.
