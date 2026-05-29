# Current RIFT live truth — static player-coordinate resolver PROMOTED

Updated UTC: `2026-05-27T22:50:24Z`

# **✅ RESULT**

The static chain below is now **promoted** as the current static **player-coordinate resolver**:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

This is a precise promotion. It proves and promotes current player **coordinates** only. It does **not** promote a full actor/stat chain, a heap address, or the stale PID `12148` proof pointer.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `34176` |
| HWND | `0x3D1544` |
| Process start UTC | `2026-05-27T18:06:53.0701460Z` |
| Module base | `0x7FF77AF40000` |
| Static root | `rift_x64+0x32EBC80` = `0x7FF77E22BC80` |
| Owner in validated epoch | `0x278C3830010` |
| Coordinate address in validated epoch | `0x278C3830330` |
| Latest static-chain coordinate | `7260.723144531, 821.425231934, 2995.659667969` |
| Latest RRAPICOORD API coordinate | `7260.720000000, 821.430000000, 2995.660000000` |
| Latest API timestamp | `2026-05-27T22:14:02.0252303Z` |
| Promotion report | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promoted-2026-05-27.md` |

## Promotion gate summary

| Gate | Result | Evidence |
|---|---|---|
| Explicit operator approval | **Passed** | User approval in current session: `approval is given, document strongly` |
| Reboot/relogin survival | **Passed** | `docs/recovery/static-owner-coordinate-chain-survived-reboot-2026-05-27.md` |
| RRAPICOORD live source restored | **Passed** | `C:\RIFT MODDING\RiftReader\scripts\captures\rrapicoord-addon-settings-repair-20260527-220840-742763\summary.json` |
| `/reloadui` from actionbar slot 11 (`-`) | **Sent after approval** | Exact PID/HWND game-window action, frame changed |
| API-now vs static-chain-now baseline | **Passed** | Max delta `0.001933594` |
| API-now vs static-chain-now after forward movement | **Passed** | Max delta `0.001955469` |
| API-now vs static-chain-now after reverse movement | **Passed** | Max delta `0.004768066` |
| Overall max API/chain delta | **Passed** | `0.004768066` <= tolerance `0.25` |
| Cheat Engine / x64dbg | **Not used** | No CE, no x64dbg attach, no breakpoints/watchpoints |
| Target memory writes | **None** | Memory reads only |

## Live validation samples

| Sample | Movement state | RRAPICOORD API-now | Static chain-now | Max abs delta |
|---|---|---:|---:|---:|
| `baseline-after-reloadui` | `none-after-reloadui` | `7259.980000000, 821.430000000, 2990.990000000` | `7259.981933594, 821.429870605, 2990.988525391` | `0.001933594` |
| `after-forward-w-1200ms` | `w:1200ms` | `7261.149900000, 821.450000000, 2998.369900000` | `7261.151855469, 821.450012207, 2998.371582031` | `0.001955469` |
| `after-reverse-s-900ms` | `s:900ms then delayed api retry` | `7260.720000000, 821.430000000, 2995.660000000` | `7260.723144531, 821.425231934, 2995.659667969` | `0.004768066` |

Movement displacement agreed between the API surface and chain readback:

| Segment | API planar X/Z delta | Static-chain planar X/Z delta |
|---|---:|---:|
| `baseline-after-reloadui` -> `after-forward-w-1200ms` | `7.472053936` | `7.475175085` |
| `after-forward-w-1200ms` -> `after-reverse-s-900ms` | `2.743787896` | `2.745591184` |

## Promotion boundary

| Item | Current status | Rule |
|---|---|---|
| `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` | **PROMOTED** | Primary static player-coordinate resolver. |
| `rift_x64+0x32EBC80` | **PROMOTED ROOT RVA** | Read this from the current module base each session. |
| `0x278C3830010` | **Not static** | Current epoch owner only; reacquire from root RVA. |
| `owner+0x320/+0x324/+0x328` | **Promoted coordinate fields** | Current coordinate triplet. |
| PID `12148` proof pointer `0x23863A26E50` | **Historical/stale** | Superseded; do not use as current movement/API proof. |
| Full actor/stat chain | **Not promoted** | Needs separate discovery/proof. |
| Secondary `[[rift_x64+0x32FFB68]+0]+0x40` chain | **Not promoted** | Failed post-reboot/current readback priority. |

## Status-helper state

| Helper | Current behavior |
|---|---|
| `tools\riftreader_workflow\decision_packet.py` | Static-resolver aware; `staticChainStatus.promotionAllowed=true` opens the promoted resolver path. |
| `scripts\coordinate_recovery_status.py` | Can prefer current-truth target when the static resolver is promoted. |
| `docs\recovery\current-proof-anchor-readback.json` | Demoted to historical/stale for PID `12148`; kept for audit and reacquisition hints only. |

## Safety ledger

| Boundary | Status |
|---|---|
| Movement/input during final validation | Approved and sent: `w:1200ms`, `s:900ms` |
| `/reloadui` | Approved and sent via actionbar slot `11` / key `-` |
| Cheat Engine | Not used |
| x64dbg attach | Not used |
| DebugActiveProcessStop | Not called |
| Provider repo writes | None |
| Target memory writes | None |
| Proof-anchor promotion | Not done |
| Full actor/stat-chain promotion | Not done |
| Static coordinate resolver promotion | **Done** |

## Required operating rule

Use the promoted resolver as the current coordinate source, but keep live workflows fail-closed.
See **[Coordinate Recovery & Reacquisition Workflow](coordinate-recovery-workflow.md)** for the full tiered guide.

1. Verify exact PID/HWND/process-start/module-base.
2. Resolve owner from `moduleBase + 0x32EBC80`.
3. Read `owner+0x320/+0x324/+0x328`.
4. Before movement/route loops, perform a fresh same-target chain readback and reject implausible/stale values.
5. Revalidate against RRAPICOORD/API-now or another live reference after patch/module drift.

## Canonical artifacts

| Artifact | Path |
|---|---|
| Promotion report | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promoted-2026-05-27.md` |
| Promotion JSON | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promoted-2026-05-27.json` |
| Live displacement validation | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-chain-live-displacement-validation-20260527-221626\summary.md` |
| Live displacement validation JSON | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-chain-live-displacement-validation-20260527-221626\summary.json` |
| Baseline API reference | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-220935.json` |
| Baseline chain readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-221002-258295\summary.json` |
| Forward API reference | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-221111.json` |
| Forward chain readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-221136-189619\summary.json` |
| Reverse API reference | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-34176-20260527-221337.json` |
| Reverse chain readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-221323-713371\summary.json` |

## Next recommended action

Continue from this promoted coordinate resolver into the next lane: wire/readback consumers against `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`, keep exact-target/freshness preflights, and pursue separate actor/stat field discovery without conflating it with this coordinate promotion.
