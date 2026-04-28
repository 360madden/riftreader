# RiftReader current truth Cheat Engine table

## Purpose

This snapshot preserves the **currently known truth** that would be painful to
reconstruct from scratch if the live Rift or Cheat Engine session is lost.

Files:

- `C:\RIFT MODDING\RiftReader\artifacts\cheat-engine\tables\2026-04-22-riftreader-current-truth-session.ct`
- `C:\RIFT MODDING\RiftReader\artifacts\cheat-engine\tables\2026-04-22-riftreader-current-truth-session.md`

## Saved on

| Item | Value |
|---|---|
| Date | April 22, 2026 |
| Branch | `navigation` |
| Workspace | `C:\RIFT MODDING\RiftReader` |
| Target process | `rift_x64` |
| Live PID at save time | `34088` |

## What the table preserves

| Area | What is preserved |
|---|---|
| Actor-facing source | Live session-bound source base `0x24F595F8D10` and the validated primary/duplicate basis rows |
| Player-current family | Live session-bound family base `0x24F0500ACA0` with level/health/coord offsets |
| Structural reference | Cheat Engine structures for the current actor-facing source layout, player-current family layout, and coord-trace object layout |

## Current actor-facing truth captured here

| Item | Value |
|---|---|
| Source base | `0x24F595F8D10` |
| Primary forward row | `+0x60 / +0x64 / +0x68` |
| Duplicate forward row | `+0x94 / +0x98 / +0x9C` |
| Primary up row | `+0x6C / +0x70 / +0x74` |
| Primary right row | `+0x78 / +0x7C / +0x80` |
| Duplicate up row | `+0xA0 / +0xA4 / +0xA8` |
| Duplicate right row | `+0xAC / +0xB0 / +0xB4` |
| Yaw formula | `atan2(forwardZ, forwardX)` |
| Pitch formula | `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))` |

## Current player-current family truth captured here

The table anchors the player-current family at the level field so the offsets
stay positive in the CE structure view.

| Item | Value |
|---|---|
| Family id | `fam-6F81F26E` |
| Family base | `0x24F0500ACA0` |
| Level | `+0x00` |
| Health copy 1 | `+0x08` |
| Health copy 2 | `+0x10` |
| Health copy 3 | `+0x18` |
| Coord X | `+0x90` |
| Coord Y | `+0x94` |
| Coord Z | `+0x98` |

## Coord-trace object structure preserved here

This part is structural reference rather than a current-process live base.

| Item | Value |
|---|---|
| Module-local instruction | `rift_x64.exe+0x93560E` |
| Instruction bytes | `F3 0F 10 86 5C 01 00 00` |
| Coord X | `+0x158` |
| Coord Y | `+0x15C` |
| Coord Z | `+0x160` |
| Level | `+0xC8` |
| Health | `+0xD0` |

## Important limits

| Item | Note |
|---|---|
| Actor-facing live addresses | Session-bound; if Rift restarts, these exact addresses may move |
| Player-current live addresses | Session-bound; base is valid for the saved live session only |
| Selector-owner lineage | Still not rebuilt as fresh current-process truth |
| Historical `+0xD4` / `+0x140` actor-facing lanes | Do **not** promote; the April 22, 2026 validation rejected them on the current truth source |

## Source artifacts this table was derived from

| File | Why it matters |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json` | Canonical live actor-facing source base and basis offsets |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-current-anchor.json` | Current player-current family base and signature |
| `C:\RIFT MODDING\RiftReader\scripts\captures\player-coord-write-trace.json` | Coord-trace-backed object layout and module-local instruction |
| `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md` | Repo-level current-truth summary |
| `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-04-22-codex-actor-facing-source-chain-truth.md` | Promoted actor-facing truth handoff |

## Intended use

Use this table to:

- reopen the live session in Cheat Engine without retyping the known-good rows
- keep the validated `+0x60/+0x94` actor-facing basis visible
- preserve the player-current family layout that the reader is currently using
- carry forward structural offsets even if live addresses change after a restart
