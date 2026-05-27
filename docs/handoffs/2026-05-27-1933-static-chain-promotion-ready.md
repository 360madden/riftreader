# Static Chain Promotion-Ready Handoff

Generated UTC: `2026-05-27T19:35:09Z`

## TL;DR

The static player-coordinate chain is ready for explicit promotion review:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

Final fresh API-now vs chain-now sample passed with max axis delta `0.004167578` within tolerance `0.25`.

Promotion was **not** applied.

## Promotion review packet

- Markdown: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promotion-review-2026-05-27.md`
- JSON: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promotion-review-2026-05-27.json`

## Current blocker

The only practical blocker is approval and resolver wiring:

- `explicit-promotion-approval-not-given`
- `no-static-resolver-promoted`
- stale PID `12148` proof pointer still blocks current decision/status helpers

## Next command if promotion is approved

Do not run blindly; first patch the decision/status helpers to recognize a promoted static resolver, then update current-truth to promoted status and validate with fresh chain readback.
