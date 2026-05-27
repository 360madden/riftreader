# Static Owner Chain API-Now Validation Handoff

Generated UTC: `2026-05-27T18:50:27Z`

## TL;DR

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` is now the strongest current player-coordinate chain candidate:

- survived reboot/relogin into PID `34176` / HWND `0x3D1544`;
- responded to approved bounded `W`/`S` displacement;
- matched fresh RRAPICOORD API-now with max absolute axis delta `0.004167578`.

It is **not promoted**. Do not silently update proof/static resolver state.

## Evidence

| Evidence | Artifact |
|---|---|
| API-now validation report | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-api-now-validation-2026-05-27.md` |
| API-now validation JSON | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-api-now-validation-2026-05-27.json` |
| Fresh RRAPICOORD reference | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-184750.json` |
| Immediate static chain readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-184809-256384\summary.json` |
| Dynamic displacement report | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-displacement-validation-2026-05-27.md` |
| Reboot survival report | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-survived-reboot-2026-05-27.md` |

## Current chain

| Field | Value |
|---|---|
| Expression | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Root address | `0x7FF77E22BC80` |
| Owner | `0x278C3830010` |
| Coordinate | `7259.949707031, 821.437561035, 2990.375732422` |

## Blockers remaining

- `proof-promotion-not-approved`
- `actor-chain-promotion-not-approved`
- `no-static-resolver-promoted`
- old PID `12148` proof pointer remains stale and must not be reused as current truth

## Safety ledger

- No CE.
- No x64dbg attach for this validation.
- No DebugActiveProcessStop.
- No provider writes.
- No proof promotion.
- No actor/static-chain promotion.
- No git mutation.

## Next single best action

Prepare an explicit promotion review packet for `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`, including exactly which consumer surfaces would change and how to roll back.
