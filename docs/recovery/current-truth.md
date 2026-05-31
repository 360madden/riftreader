# Current RIFT live truth — static player-coordinate resolver PROMOTED

Updated UTC: `2026-05-31T14:23:13Z`

# **✅ RESULT**

The static chain below remains **promoted** as the current static **player-coordinate resolver**:

`[rift_x64+0x32EBC80]+0x320/+0x324/+0x328`

This is a precise promotion. It proves and promotes current player **coordinates** only. It does **not** promote a full actor/stat chain, a heap address, or the stale PID `12148` proof pointer. Current target metadata is PID `25668` / HWND `0x320CB0`; current PID `25668` now has fresh RRAPICOORD API-now vs static-chain validation from the 2026-05-31 bounded family snapshot. PID `34176` appears below only as historical promotion-validation evidence.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `25668` |
| HWND | `0x320CB0` |
| Process start UTC | `2026-05-30T02:46:41.581536+00:00` |
| Module base | `0x7FF6EE5D0000` |
| Static root | `rift_x64+0x32EBC80` = `0x7FF6F18BBC80` |
| Owner in current readback | `0x1B53D7806A0` |
| Coordinate address in current readback | `0x1B53D7809C0` (owner+0x320) |
| Latest recorded coordinate snapshot | `7264.431640625, 821.697204590, 3003.875732422` at `2026-05-31T14:23:12.926638+00:00` — current exact-target static-chain readback after bounded displacement. |
| Latest current nav yaw | `22.940853610°` at `2026-05-31T14:23:12.943809+00:00` |
| Latest RRAPICOORD API coordinate for PID 25668 | `7264.4297, 821.7000, 3003.8799` |
| Latest API timestamp for PID 25668 | `2026-05-31T14:22:56.4433446Z` |
| Current static readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260531-142312-924000\summary.json` |
| Current nav-state readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260531-142312-943158\summary.json` |
| Current PID API-now vs chain-now validation | `C:\RIFT MODDING\RiftReader\scripts\captures\family-snapshot-sequence-currentpid-25668-20260531-142159-332736\delta-analysis\delta-summary.json` |
| Promotion report | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-coordinate-chain-promoted-2026-05-27.md` |

PID/HWND identity is a targeting preflight only. The current PID `25668` API-now validation below passed at `2026-05-31T14:22:57Z`; refresh it before later live movement or proof promotion because coordinates and target epochs drift over time.

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


## Current PID 25668 API-now validation — 2026-05-31

This is a **fresh current-target validation**, not a new proof promotion. It used exact PID/HWND targeting, RRAPICOORD memory-scan references, and a bounded `W` 350ms displacement through the C# ScanCode backend.

| Pose | RRAPICOORD API | Static owner memory | Max abs delta / tracking |
|---|---:|---:|---:|
| Baseline | `7262.3398, 821.6900, 3003.0000` | `7262.338378906, 821.693603516, 3002.999023438` | baseline max abs `0.003603516` |
| Forward 350ms displaced | `7264.4297, 821.7000, 3003.8799` | `7264.431640625, 821.697204590, 3003.875732422` | displaced max abs `0.004167578` |
| Displacement delta | planar API `2.267577125` | planar memory `2.269441179` | tracking max abs `0.006398926` |

Artifacts:

- Sequence summary: `C:\RIFT MODDING\RiftReader\scripts\captures\family-snapshot-sequence-currentpid-25668-20260531-142159-332736\summary.json`
- Delta summary: `C:\RIFT MODDING\RiftReader\scripts\captures\family-snapshot-sequence-currentpid-25668-20260531-142159-332736\delta-analysis\delta-summary.json`
- Candidate vec3: `C:\RIFT MODDING\RiftReader\scripts\captures\family-snapshot-sequence-currentpid-25668-20260531-142159-332736\delta-analysis\candidate-vec3.json`

Safety: no Cheat Engine, no x64dbg attach, no target memory writes, no provider writes, and no proof/actor-chain promotion.


## Historical promotion validation samples (PID 34176)

| Sample | Movement state | RRAPICOORD API-now | Static chain-now | Max abs delta |
|---|---|---:|---:|---:|
| `baseline-after-reloadui` | `none-after-reloadui` | `7259.980000000, 821.430000000, 2990.990000000` | `7259.981933594, 821.429870605, 2990.988525391` | `0.001933594` |
| `after-forward-w-1200ms` | `w:1200ms` | `7261.149900000, 821.450000000, 2998.369900000` | `7261.151855469, 821.450012207, 2998.371582031` | `0.001955469` |
| `after-reverse-s-900ms` | `s:900ms then delayed api retry` | `7260.720000000, 821.430000000, 2995.660000000` | `7260.723144531, 821.425231934, 2995.659667969` | `0.004768066` |

These samples validate the promoted resolver historically. They must not be presented as current PID `25668` API-now proof. Movement displacement agreed between the API surface and chain readback:

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
| Movement/input during historical promotion validation | Approved and sent in PID `34176` epoch: `w:1200ms`, `s:900ms` |
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

Continue from this promoted coordinate resolver with exact-target/freshness preflights. Before presenting current coordinates as API-confirmed truth, capture PID `25668` API-now vs chain-now evidence. Keep actor/stat field discovery separate from this coordinate promotion.
