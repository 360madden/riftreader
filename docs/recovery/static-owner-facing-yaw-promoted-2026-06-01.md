# Static Owner Facing/Yaw Promotion — 2026-06-01

# **✅ PROMOTED**

- Generated UTC: `2026-06-01T17:07:09.168647+00:00`
- Chain: `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314`
- Latest yaw: `80.82343415281247`
- Facing target address: `0x1E16E8709AC`
- Owner address: `0x1E16E8706A0`

## Promotion boundary

- Promotes: static owner facing/yaw source at `owner+0x30C/+0x310/+0x314`.
- Does not promote: turn-rate `owner+0x304`, support fields `owner+0x300`/`owner+0x408`, full actor/stat chain, proof anchor, or autonomous turn control.

## Gates

| Gate | Value |
|---|---|
| Review passed | `True` |
| Fresh pre-promotion readback | `True` |
| API-now vs chain-now | `True` |
| Three-pose displacement | `True` |
| Restart/relog survived | `True` |
| Static evidence passed | `True` |

## Evidence

- Readiness review: `C:\RIFT MODDING\RiftReader\scripts\captures\facing-target-promotion-readiness-review-20260601-165301-889669\summary.json`
- Dashboard: `C:\RIFT MODDING\RiftReader\.riftreader-local\navigation-pointer-discovery\latest\summary.json`
- Nav state: `scripts\captures\static-owner-nav-state-20260601-164856-705835\summary.json`
- API reference: `scripts\captures\rift-api-reference-currentpid-41808-20260601-164918.json`
