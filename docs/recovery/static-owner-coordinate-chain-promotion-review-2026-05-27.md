# Static Owner Coordinate Chain Promotion Review Packet

Generated UTC: `2026-05-27T19:35:09Z`

## Verdict

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` is **ready for explicit promotion approval**, but promotion was **not applied**.

This packet is the review gate before changing canonical resolver/proof behavior.

## Candidate

| Field | Value |
|---|---|
| Resolver expression | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Static root RVA | `0x32EBC80` |
| Static root address in current epoch | `0x7FF77E22BC80` |
| Current module base | `0x7FF77AF40000` |
| Current owner heap address | `0x278C3830010` |
| Owner vtable | `0x7FF77D58CEB8` / RVA `0x264CEB8` |
| Target | PID `34176`, HWND `0x3D1544` |

Promote the **module RVA + offsets**, not the current heap owner address.

## Final fresh API-now vs chain-now sample

| Source | Coordinate | Artifact |
|---|---|---|
| RRAPICOORD API-now | `7259.949700000, 821.440000000, 2990.379900000` | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-193250.json` |
| Static chain-now | `7259.949707031, 821.437561035, 2990.375732422` | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-193319-122219\summary.json` |

| Axis | Chain - API | Absolute delta |
|---|---:|---:|
| X | `0.000007031` | `0.000007031` |
| Y | `-0.002438965` | `0.002438965` |
| Z | `-0.004167578` | `0.004167578` |
| Max |  | `0.004167578` |

Tolerance: `0.25`. Verdict: `passed`.

## Evidence stack

| Gate | Status | Artifact |
|---|---|---|
| Reboot/relogin survival | Passed | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-survived-reboot-2026-05-27.md` |
| Dynamic displacement | Passed | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-displacement-validation-2026-05-27.md` |
| API-now validation | Passed | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-api-now-validation-2026-05-27.md` |
| Final fresh sample | Passed | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-193250.json` + `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-193319-122219\summary.json` |

## Promotion plan if approved later

1. Mark `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` as the promoted static player-coordinate resolver.
2. Keep old PID `12148` proof anchor as historical/stale only.
3. Update decision/workflow gates to prefer the promoted static resolver for current target readiness instead of blocking on stale `current-proof-anchor-readback.json`.
4. Keep movement/navigation blocked until resolver readback passes in current PID/HWND immediately before use.
5. Record rollback instructions and keep all evidence reports.

## Do not promote

- Current owner heap address `0x278C3830010` as a static pointer.
- Old PID `12148` absolute proof anchor `0x23863A26E50`.
- Secondary `[[rift_x64+0x32FFB68]+0]+0x40` playerPosition chain.

## Remaining blockers

- `explicit-promotion-approval-not-given`
- `no-static-resolver-promoted`
- `decision-status-helpers-still-block-on-stale-proof-pointer-until-wired`

## Safety ledger

| Boundary | Status |
|---|---|
| Movement/input in this step | None |
| Cheat Engine | Not used |
| x64dbg attach | Not used |
| DebugActiveProcessStop | Not called |
| Provider writes | None |
| Proof promotion | Not done |
| Actor/static-chain promotion | Not done |
| Git mutation | Not done |
