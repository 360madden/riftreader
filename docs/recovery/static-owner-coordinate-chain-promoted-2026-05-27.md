# Static Owner Coordinate Chain Promotion — PROMOTED

Generated UTC: `2026-05-27T22:50:24Z`

# **✅ RESULT**

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` is now **PROMOTED** as the current static **player-coordinate resolver** for the validated RIFT build/epoch.

This is a narrow promotion: it promotes the module-RVA coordinate resolver, **not** a full player actor/stat chain and **not** any heap address.

## Canonical resolver

| Field | Value |
|---|---|
| Promoted expression | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Root module | `rift_x64.exe` |
| Root RVA | `0x32EBC80` |
| Current module base | `0x7FF77AF40000` |
| Root address in validated epoch | `0x7FF77E22BC80` |
| Owner address in validated epoch | `0x278C3830010` |
| Coordinate address in validated epoch | `0x278C3830330` |
| Latest static-chain coordinate | `7260.723144531, 821.425231934, 2995.659667969` |
| Latest API coordinate | `7260.720000000, 821.430000000, 2995.660000000` |
| Latest API timestamp | `2026-05-27T22:14:02.0252303Z` |
| Validation tolerance | `0.25` |
| Max observed API/chain delta | `0.004768066` |

Promote the **module RVA + offsets**. Do **not** promote `0x278C3830010` or any other current heap address as static.

## Promotion evidence

| Sample | Movement state | RRAPICOORD API-now | Static chain-now | Max abs delta | Within tolerance |
|---|---|---:|---:|---:|---|
| `baseline-after-reloadui` | `none-after-reloadui` | `7259.980000000, 821.430000000, 2990.990000000` | `7259.981933594, 821.429870605, 2990.988525391` | `0.001933594` | `True` |
| `after-forward-w-1200ms` | `w:1200ms` | `7261.149900000, 821.450000000, 2998.369900000` | `7261.151855469, 821.450012207, 2998.371582031` | `0.001955469` | `True` |
| `after-reverse-s-900ms` | `s:900ms then delayed api retry` | `7260.720000000, 821.430000000, 2995.660000000` | `7260.723144531, 821.425231934, 2995.659667969` | `0.004768066` | `True` |

Movement displacement also matched between the live API surface and static chain:

| Segment | API planar X/Z delta | Static-chain planar X/Z delta |
|---|---:|---:|
| `baseline-after-reloadui` -> `after-forward-w-1200ms` | `7.472053936` | `7.475175085` |
| `after-forward-w-1200ms` -> `after-reverse-s-900ms` | `2.743787896` | `2.745591184` |

Evidence verdict: `live-api-now-and-static-chain-now-match-through-displacement`. The original run summary was `passed-not-promoted` because promotion had not yet been approved; approval has now been recorded and applied in this document set.

## What was promoted vs not promoted

| Area | Status | Rule |
|---|---|---|
| Static player-coordinate resolver | **PROMOTED** | Use `rift_x64+0x32EBC80` to resolve owner, then read `owner+0x320/+0x324/+0x328`. |
| Full player actor/stat chain | **NOT promoted** | This evidence proves coordinates, not stats/inventory/actor fields. |
| Current owner heap address `0x278C3830010` | **NOT static** | Reacquire it from the module RVA every process/session. |
| Old PID `12148` proof pointer `0x23863A26E50` | **Historical only** | Superseded by the promoted static resolver for PID `34176`. |
| Secondary `[[rift_x64+0x32FFB68]+0]+0x40` lane | **Rejected/currently not primary** | Failed post-reboot readback; keep as historical candidate only. |

## Safety ledger

| Boundary | Status |
|---|---|
| Operator approval | Given in current session: `approval is given, document strongly` |
| AddonSettings repair | Applied to re-enable RRAPICOORD marker: `C:\RIFT MODDING\RiftReader\scripts\captures\rrapicoord-addon-settings-repair-20260527-220840-742763\summary.json` |
| `/reloadui` / actionbar slot `11` (`-`) | Sent after approval to refresh RRAPICOORD runtime state |
| Movement stimulus | Sent after approval: `w:1200ms`, then `s:900ms` |
| Cheat Engine | Not used |
| x64dbg attach/breakpoints/watchpoints | Not used |
| Target memory writes | None |
| Provider repo writes | None |
| Proof-anchor promotion | Not done |
| Full actor/stat-chain promotion | Not done |
| Static coordinate resolver promotion | **Done** |

## Required use policy

1. Resolve from `moduleBase + 0x32EBC80`; never hard-code the epoch owner heap pointer.
2. Verify exact PID/HWND/process-start/module-base before live use.
3. Read `owner+0x320/+0x324/+0x328` as the coordinate triplet.
4. Run a fresh same-target chain readback/freshness sanity before movement, route loops, or long captures.
5. Revalidate after client patch, module layout drift, process anomalies, or implausible coordinate jumps.
6. Roll back `promotionAllowed` to `false` if API-now vs chain-now exceeds tolerance or the root no longer resolves a plausible owner.

## Canonical artifacts

| Artifact | Path |
|---|---|
| Promotion JSON | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promoted-2026-05-27.json` |
| Promotion Markdown | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promoted-2026-05-27.md` |
| Live displacement validation JSON | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-chain-live-displacement-validation-20260527-221626\summary.json` |
| Live displacement validation Markdown | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-chain-live-displacement-validation-20260527-221626\summary.md` |
| Baseline API reference | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-220935.json` |
| Baseline static-chain readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-221002-258295\summary.json` |
| Forward API reference | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-221111.json` |
| Forward static-chain readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-221136-189619\summary.json` |
| Reverse API reference | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-221337.json` |
| Reverse static-chain readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-221323-713371\summary.json` |

## Rollback conditions

Rollback this promotion and mark the resolver blocked if any of these occur:

- `rift_x64+0x32EBC80` no longer resolves to a plausible owner object.
- `owner+0x320/+0x324/+0x328` no longer matches a fresh live API/runtime coordinate within tolerance.
- RIFT client build/module layout changes invalidate the owner layout.
- Exact target identity cannot be proven before a live workflow.
