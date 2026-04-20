---
state: superseded-by-solved-state
as_of: 2026-04-19
---

# AHK-Backed Actor-Facing Lead (2026-04-19)

> **Superseded on April 20, 2026**
>
> This note captured the first behavior-backed lead.
>
> The canonical solved-state handoff is now:
>
> - `C:\RIFT MODDING\RiftReader_facing\docs\handoffs\2026-04-20-actor-facing-solved-state.md`

## Scope

This note freezes the first behavior-backed actor-facing lead that survived:

- trusted automated turn stimulus,
- opposite-direction retained state change,
- and repeated live access to the same source block.

## Lead summary

| Field | Value |
|---|---|
| Source object | `0x1B115201EB0` |
| Forward block start | `0x1B115201F84` (`+0xD4`) |
| Sibling component | `0x1B115201F8C` (`+0xDC`) |
| Dominant live access | `rift_x64.exe+0x5CDC93 : movss xmm3,[rcx+8]` |
| Base register | `RCX = 0x1B115201F84` |
| Effective address | `0x1B115201F8C` |
| Operational status | **behavior-backed lead** |

## Why this replaced the old incumbent

| Old incumbent | New lead |
|---|---|
| `0x1B1230D39E0 + 0x144` | `0x1B115201EB0 + 0xD4` |
| Structurally plausible but frozen through visible turn | Structurally plausible and changed under trusted AHK-backed A/D turn stimulus |
| Rejected | Current best live source |

## Strongest runs

| Run | Watch | Key | Derived yaw delta | Dominant RIP |
|---|---|---|---:|---|
| AHK access | `0x1B115201F84` | `D` | about `-92.766°` | `rift_x64.exe+0x5CDC93` |
| AHK access | `0x1B115201F84` | `A` | about `+113.788°` | `rift_x64.exe+0x5CDC93` |

## Repo impact

`C:\RIFT MODDING\RiftReader_facing\scripts\capture-actor-orientation.ps1` now prefers the tracked behavior-backed lead file:

- `C:\RIFT MODDING\RiftReader_facing\scripts\actor-facing-behavior-backed-lead.json`

`C:\RIFT MODDING\RiftReader_facing\scripts\actor-facing-common.ps1` now treats captures resolved through `ResolutionMode = behavior-backed-lead` as the repo's canonical preferred lead via `OperationalStatus = behavior-backed-lead` and `PreferredLead = true`.

The old artifact-selected source path remains fallback-only and should only be re-enabled deliberately.
