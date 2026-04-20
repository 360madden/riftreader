---
state: current
as_of: 2026-04-20
---

# Actor-Facing Solved State — 2026-04-20

## Verdict

Actor-facing is now **solved** for the canonical live source:

- source object: `0x1B115201EB0`
- basis forward offset: `0xD4`

The prior incumbent:

- `0x1B1230D39E0 + 0x144`

is **rejected** and must not be trusted or silently re-promoted.

## Canonical solved source

| Field | Value |
|---|---|
| Source object | `0x1B115201EB0` |
| Basis forward offset | `0xD4` |
| Forward block start | `0x1B115201F84` |
| Sibling component | `0x1B115201F8C` |
| Actor yaw formula | `atan2(forwardZ, forwardX)` |
| Hot traced sibling offset | `0xDC` |
| Dominant live access anchor | `rift_x64.exe+0x5CDC93 : movss xmm3,[rcx+8]` |
| Repo status | `preferred-solved-lead` |
| Operational status | `behavior-backed-lead` |

## Exact evidence that solved actor-facing

| Evidence type | Result |
|---|---|
| Idle validation | pass |
| Turn-left validation | pass |
| Turn-right validation | pass |
| Integrity gates | pass |
| Preferred lead capture path | active by default |

### Turn-left pass

| Field | Value |
|---|---|
| Source | `0x1B115201EB0 + 0xD4` |
| Before yaw | `-123.92663226194297°` |
| After yaw | `110.82872614126791°` |
| Yaw delta | `-125.24464159678915°` |
| Planar coord delta | `0.0` |
| Verdict | pass |

### Turn-right pass

| Field | Value |
|---|---|
| Source | `0x1B115201EB0 + 0xD4` |
| Before yaw | `110.82872614126791°` |
| After yaw | `-121.41233296150064°` |
| Yaw delta | `+127.7589408972315°` |
| Planar coord delta | `0.0` |
| Verdict | pass |

## Rejected incumbent

| Field | Value |
|---|---|
| Source | `0x1B1230D39E0 + 0x144` |
| Failure mode | visible left turn changed the scene, but captured yaw stayed unchanged |
| Before/after yaw | `26.7241523772533° -> 26.7241523772533°` |
| Delta yaw | `0.0°` |
| Disposition | rejected |

## Repo policy from this point forward

| Policy | Meaning |
|---|---|
| Canonical source | `0x1B115201EB0 + 0xD4` is the default actor-facing source |
| Canonical actor yaw | derived from the canonical forward basis row, not a separately promoted standalone float |
| Standalone yaw-float search | do not reopen unless fresh live evidence contradicts the canonical basis-derived yaw source |
| Reopen rule | Do not reopen actor-facing discovery unless fresh live evidence contradicts the canonical source |
| Forward validation | Treat forward movement / navigation proof as a separate downstream track |
| Promotion rule | Do not promote any conflicting source without fresh proof that beats the canonical solved lead |

## Remaining open work

| Area | Status |
|---|---|
| Actor-facing | solved |
| Forward movement validation | pending |
| Navigation-grade contract | pending repeated forward proof |
