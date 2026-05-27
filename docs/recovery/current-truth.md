# Current RIFT live truth — static owner chain promotion-review ready, not promoted

Updated UTC: `2026-05-27T20:04:30Z`

## Verdict

The best current player-coordinate static-chain candidate is:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

It is **promotion-review ready** but **not promoted**.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `34176` |
| HWND | `0x3D1544` |
| Process start UTC | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` |
| Static root | `rift_x64+0x32EBC80` = `0x7FF77E22BC80` |
| Owner | `0x278C3830010` |
| Latest chain coordinate | `7259.949707031, 821.437561035, 2990.375732422` |

## Final fresh API-now vs chain-now sample

| Source | Coordinate | Artifact |
|---|---|---|
| RRAPICOORD API-now | `7259.949700000, 821.440000000, 2990.379900000` | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-193250.json` |
| Static chain-now | `7259.949707031, 821.437561035, 2990.375732422` | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-193319-122219\summary.json` |

Max absolute axis delta: `0.004167578` within tolerance `0.25`.

## Promotion review packet

- `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promotion-review-2026-05-27.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promotion-review-2026-05-27.json`

## Evidence already captured

- Reboot/relogin survival: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-survived-reboot-2026-05-27.md`
- Dynamic displacement validation: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-displacement-validation-2026-05-27.md`
- API-now validation: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-api-now-validation-2026-05-27.md`
- No-debug static-owner discovery extension: `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-27-2004-no-debug-static-owner-chain-discovery.md`

## Latest no-debug static-owner discovery

| Check | Result |
|---|---|
| Static owner-chain readback | `passed`; root `rift_x64+0x32EBC80` still resolves owner `0x278C3830010` and coordinate field `0x278C3830330` |
| Owner neighborhood inspection | `passed`; `255` interesting matches, `177` module pointers, `12` owner-window module pointers, `7` exact owner self refs |
| Owner pointer-family scan | `passed`; `26` hits to owner and `1` `rift_x64.exe` module hit at `0x7FF77E22BC80` |
| Coordinate-field pointer scan | `passed`; `0` direct pointer hits to `0x278C3830330`, consistent with embedded owner `+0x320` field |
| Owner-layout comparison packet | `blocked` only on promotion/proof gates; now recognizes the current static owner resolver instead of routing solely through stale PID `12148` proof-family artifacts |
| RiftScan milestone review | `blocked`; confirms stale PID `12148` proof pointer / no current selected RiftScan candidate for PID `34176` |
| Fresh API source refresh attempt | `blocked`; RRAPICOORD scan had no usable marker and ChromaLink world-state was not healthy/fresh enough for player position |

Artifacts:

- `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-200107-566800\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\pointer-owner-neighborhood-inspector-20260527-200201-853835\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\pointer-family-scan-20260527-200236-877935\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\pointer-family-scan-20260527-200328-634938\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\owner-layout-comparison-packet-20260527-200911-671622\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260527-200952.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\rrapicoord-scan-diagnostics-20260527-201612-575793\summary.json`
- `C:\RIFT MODDING\RiftReader\scripts\captures\chromalink-world-state-reference-20260527-201624-468822\summary.json`

This extension is candidate evidence only and does **not** promote the chain.

## Status-helper readiness

Decision/status helpers are now **static-resolver aware**, but the activation
gate is still closed because the chain has **not** been promoted.

| Helper | Prepared behavior | Activation gate |
|---|---|---|
| `tools\riftreader_workflow\decision_packet.py` | Can treat a promoted static resolver as the current target epoch instead of the stale PID `12148` proof pointer | `staticChainStatus.promotionAllowed=true` after explicit promotion approval |
| `scripts\coordinate_recovery_status.py` | Can use the current-truth target for live PID checks when a complete static resolver is promoted | `staticChainStatus.promotionAllowed=true` after explicit promotion approval |

Validation added:

- `python -m unittest scripts.test_decision_packet`
- `python -m unittest scripts.test_coordinate_recovery_status`

This helper wiring **does not promote** the chain.

## Remaining blockers

| Blocker | Meaning |
|---|---|
| `explicit-promotion-approval-not-given` | Do not silently promote resolver/proof state |
| `no-static-resolver-promoted` | No approved static resolver has been marked promoted |
| `decision-status-helpers-static-resolver-aware-but-unpromoted-chain-still-blocks` | Existing gates still correctly block until explicit promotion flips the resolver gate |

## Safety ledger

| Boundary | Status |
|---|---|
| Movement/input in latest sample | None |
| Cheat Engine | Not used |
| x64dbg attach | Not used |
| DebugActiveProcessStop | Not called |
| Provider writes | None |
| Proof promotion | Not done |
| Actor/static-chain promotion | Not done |
| Git mutation | Not done |

## Next recommended action

If continuing no-debug discovery, restore a fresh live API/reference source first: the latest RRAPICOORD scan found no usable marker, and the ChromaLink world-state reference was blocked as not healthy/fresh enough for player position. After the API source is healthy, rerun API-now vs static-chain-now immediately before any promotion review and keep stale PID `12148` proof-family evidence separate from the current static resolver.

If explicitly approved, promote `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` as the static player-coordinate resolver. Decision/status helpers are now prepared to stop treating stale PID `12148` proof as the active target **only after** `staticChainStatus.promotionAllowed=true` is set by that approved promotion.
