# Static Owner Coordinate Chain — Fresh API-Now Validation

Generated UTC: `2026-05-27T18:50:27Z`

## Verdict

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` **matched fresh RRAPICOORD API-now within tolerance** on PID `34176` / HWND `0x3D1544`.

Status: **passed, not promoted**.

## Comparison

| Source | Coordinate | Artifact |
|---|---|---|
| API-now / RRAPICOORD | `7259.949700000, 821.440000000, 2990.379900000` | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-184750.json` |
| Chain-now | `7259.949707031, 821.437561035, 2990.375732422` | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-184809-256384\summary.json` |

| Axis | Chain - API | Absolute delta |
|---|---:|---:|
| X | `0.000007031` | `0.000007031` |
| Y | `-0.002438965` | `0.002438965` |
| Z | `-0.004167578` | `0.004167578` |
| Max |  | `0.004167578` |

Tolerance: `0.25`.

## Chain

| Field | Value |
|---|---|
| Expression | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Static root | `0x7FF77E22BC80` |
| Owner | `0x278C3830010` |
| Owner vtable | `0x7FF77D58CEB8` / RVA `0x264CEB8` |
| Target | PID `34176`, HWND `0x3D1544` |

## Supporting evidence

- Survived reboot/relogin report: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-survived-reboot-2026-05-27.md`
- Dynamic displacement report: `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-displacement-validation-2026-05-27.md`
- API scan file: `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-scan-currentpid-34176-20260527-184750.json`

## Safety / promotion ledger

| Gate | Status |
|---|---|
| API-now capture | Read-only RRAPICOORD memory scan, no input |
| Chain-now readback | Read-only process memory read |
| Cheat Engine | Not used |
| x64dbg attach | Not used |
| DebugActiveProcessStop | Not called |
| Provider writes | None |
| Proof promotion | Not done |
| Actor/static-chain promotion | Not done |
| Git mutation | Not done |

## Promotion status

This is now promotion-grade evidence, but promotion was **not** performed. The next step is an explicit promotion review/approval packet, not silent mutation of proof/static resolver truth.
