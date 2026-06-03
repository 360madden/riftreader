# Current RIFT live truth — POST-UPDATE RECOVERY IN PROGRESS

Updated UTC: `2026-06-02T20:06:19Z`

# **⚠️ BLOCKER**

The 2026-06-02 RIFT update (`STABLE-1-1152-a-1256395`) invalidated the
previous promoted current resolver for the active post-update target. For PID
`77152` / HWND `0x17A0DB2`, `[rift_x64+0x32EBC80]` is readable but its qword is
currently `0x0`.

Do **not** use the 2026-06-01 promoted resolver below as current navigation
truth for this post-update epoch.

PID/HWND identity is a targeting preflight only; it is not freshness proof.
Do not present any latest recorded coordinate snapshot as current-now unless a
fresh same-target API-now vs memory-now comparison exists for that exact epoch.

Candidate-only recovery evidence now exists:

| Purpose | Candidate / status | Evidence |
|---|---|---|
| Position candidate | `[[rift_x64+0x32DD7E8]+0x80]+0x28/+0x2C/+0x30` matched current reference with max abs delta `0.004628906250218279`; 5/5 no-input polling samples matched with stationary drift `0.0`. | `C:\RIFT MODDING\RiftReader\scripts\captures\postupdate-global-container-coordinate-readback-20260602-200619-457973\summary.json` |
| Orientation/static-layout anchor | `[rift_x64+0x335F508]` points at an orientation/matrix-like object, **not** world position. | `C:\RIFT MODDING\RiftReader\scripts\captures\postupdate-static-access-chain-20260602-195804-076419\summary.json` |

Latest recorded coordinate snapshot: candidate readback
`7256.38916015625, 821.4478149414062, 2990.00537109375` at
`2026-06-02T20:06:19.917073+00:00`; do not present this value as current-now.

This is **not** a promotion. No movement/displacement proof, restart/relog
survival, ProofOnly, current-truth apply, actor-chain promotion, or navigation
control has been performed. Historical promoted truth remains archived below for
audit only until new proof gates pass.

---

# Historical RIFT live truth — static coordinate + facing/yaw resolvers PROMOTED

Updated UTC: `2026-06-01T17:34:24Z`

# **✅ RESULT**

The current RIFT target after manual restart is PID `12664` / HWND `0x205146C`, process start `2026-06-01T17:19:45.159353Z`, module base `0x7FF6EE5D0000`.

Both promoted static owner resolvers are current for this target epoch:

| Purpose | Chain / formula | Current evidence |
|---|---|---|
| Player coordinates | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260601-172308-351318\summary.json` |
| Facing target / yaw | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260601-172308-370480\summary.json` |
| Yaw formula | `atan2(facingZ - playerZ, facingX - playerX)` | Current yaw `41.29403500816383°` |

This is a precise promotion boundary. It promotes player coordinates and static owner facing/yaw readback only. It does **not** promote a full actor/stat chain, route-control automation, turn-rate/support fields, proof anchors, or any absolute heap address. Reacquire the owner from `rift_x64+0x32EBC80` each target epoch.

## Current post-restart target — 2026-06-01 17:34 UTC

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `12664` |
| HWND | `0x205146C` |
| Process start UTC | `2026-06-01T17:19:45.159353Z` |
| Module base | `0x7FF6EE5D0000` |
| Static root | `rift_x64+0x32EBC80` = `0x7FF6F18BBC80` |
| Owner in current readback | `0x1E067A80010` |
| Coordinate address in current readback | `0x1E067A80330` (`owner+0x320`) |
| Facing target address in current readback | `0x1E067A8031C` (`owner+0x30C`) |
| Latest coordinate snapshot | `7251.95751953125, 821.4475708007812, 2988.9814453125` at `2026-06-01T17:23:08.352942+00:00` |
| Latest current yaw / pitch | yaw `41.29403500816383°`; pitch `-3.5293889576850765°` at `2026-06-01T17:23:08.371806+00:00` |
| RRAPICOORD API coordinate | `7251.96, 821.45, 2988.98` at `2026-06-01T17:22:58.151422Z` |
| API-vs-chain agreement | Max abs delta `0.00248046875003638` <= tolerance `0.25` |
| Static readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260601-172308-351318\summary.json` |
| Nav/facing readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260601-172308-370480\summary.json` |
| API-now validation | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-12664-20260601-172204.json` |
| Facing/yaw restart survival | `C:\RIFT MODDING\RiftReader\scripts\captures\facing-target-restart-survival-packet-20260601-172408-160107\summary.json` |
| Facing/yaw promotion artifact | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-facing-yaw-promoted-2026-06-01.json` |
| Strong restart-survival doc | `C:\RIFT MODDING\RiftReader\docs\recovery\static-owner-facing-yaw-restart-survival-2026-06-01.md` |

## Current PID 12664 restart-survival propagation — 2026-06-01 17:34 UTC

The user manually restarted RIFT. The process epoch changed from PID `41808` / HWND `0x2B0A26` / process start `2026-06-01T01:50:50.903773Z` to PID `12664` / HWND `0x205146C` / process start `2026-06-01T17:19:45.159353Z`.

| Check | Result |
|---|---|
| Static root reacquired | Passed; module base stayed `0x7FF6EE5D0000`, root resolved to `0x7FF6F18BBC80`. |
| Owner address changed | Passed; old owner `0x1E16E8706A0`, new owner `0x1E067A80010`. This proves no heap address was treated as static. |
| Coordinate offsets stable | Passed; position still at `owner+0x320/+0x324/+0x328`. |
| Facing offsets stable | Passed; facing target still at `owner+0x30C/+0x310/+0x314`. |
| API-now validation | Passed; max abs chain/API delta `0.00248046875003638` <= `0.25`. |
| Current-truth propagation | Passed; `.riftreader-local\current-truth-refresh-apply\latest\summary.json` wrote tracked truth with `promotionPerformed=false` and `facingPromotion=false`. |
| Safety | No live input/movement, no debugger/CE, no target memory writes, no provider writes, no new proof/facing/actor promotion. |

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




## Current PID 41808 no-input static/API-now refresh — 2026-06-01 04:56 UTC

This refresh updated tracked truth from exact-target no-input static-chain/nav-state readbacks plus a same-target RRAPICOORD API-now capture. It did **not** send movement/input, attach Cheat Engine/x64dbg, write provider repos, promote proof, promote actor chains, or promote facing/turn-rate chains.

| Check | Evidence |
|---|---|
| Static coordinate readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260601-045507-534569\summary.json` — coordinate `7259.416503906250, 821.424316406250, 2993.230712890625` at `2026-06-01T04:55:07.535451+00:00`. |
| Nav-state readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260601-045519-286724\summary.json` — candidate yaw `75.177112842°`; facing remains candidate-only. |
| RRAPICOORD API-now | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-41808-20260601-045534.json` — coordinate `7259.419922, 821.419983, 2993.229980` at `2026-06-01T04:55:56.620509Z`. |
| Chain/API agreement | Max abs delta `0.004333406` <= tolerance `0.25`. |
| Dashboard / apply source | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` generated `2026-06-01T04:56:07Z` and `.riftreader-local\current-truth-refresh-plan\latest\summary.json` generated `2026-06-01T04:56:16Z`; no proof/facing/actor promotion was performed. |
| Boundary | Readback and API memory scan only; no live input/movement/debugger/provider writes. |

## Approved bounded route-loop and API refresh — 2026-05-31 16:37 UTC

This slice used the user's explicit approval for live turn/movement gates and repo publish workflow. It executed one exact-target, one-destination route-loop smoke run, then refreshed no-input static readback, nav-state readback, and RRAPICOORD API-now evidence. It did **not** attach Cheat Engine/x64dbg, write provider repos, promote proof, promote actor chains, or promote facing/turn-rate chains.

| Check | Evidence |
|---|---|
| Route loop | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-continuous-route-20260531-163708-174984\summary.json` — destination `7267.194, 3005.045` (`approved-3m-ahead-smoke`), initial distance `2.999636m`, progress `2.642985m`, arrived in `1` iteration / `1` forward step. |
| Route controls | `--turn-approved --movement-approved --allow-candidate-turn-control`, backend `mouse-look`; no turn was needed (`turnsExecuted=0`), movement/input were sent by the forward step. |
| Frame-change visual check | Baseline `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-123659-264.png`; changed frame `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-123721-931.png`; final capture `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260531-123728-957.png`. |
| Static readback after route | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260531-163749-157934\summary.json` — coordinate `7267.523437500000, 821.699401855469, 3005.181640625000` at `2026-05-31T16:37:49.159175+00:00`. |
| Nav-state after route | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260531-163749-964534\summary.json` — yaw `22.962550464°`, pitch `-7.446817291°`, turn-rate `1.1711857318878174`. |
| RRAPICOORD API-now after route | `C:\RIFT MODDING\RiftReader\scripts\captures\rift-api-reference-currentpid-25668-20260531-163751.json` — coordinate `7267.5200, 821.7000, 3005.1799` at `2026-05-31T16:37:59.8565695Z`. |
| Chain/API agreement | Chain-minus-API deltas: X `0.003437500`, Y `-0.000598145`, Z `0.001740625`; max abs `0.003437500` <= tolerance `0.25`. |
| Safety | Route sent approved movement/input only; no reloadui, screenshot key, Cheat Engine, x64dbg attach, provider writes, target memory writes, proof promotion, actor-chain promotion, or facing promotion. |

## Current PID 25668 no-input static readback refresh — 2026-05-31 16:06 UTC

This refresh updated tracked truth from exact-target no-input static-chain/nav-state readbacks only. It did **not** send movement/input, refresh RRAPICOORD API-now, promote facing/turn-rate, or promote actor/stat proof.

| Check | Evidence |
|---|---|
| Static coordinate readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260531-160614-677227\summary.json` — coordinate `7264.431640625, 821.697204590, 3003.875732422` at `2026-05-31T16:06:14.677913+00:00`. |
| Nav-state readback | `C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-nav-state-20260531-160615-484864\summary.json` — yaw `22.940853610°`, turn-rate sample `1.171185732`; turn control remains separately gated by live-route approvals. |
| Dashboard / apply source | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` generated `2026-05-31T16:06:16Z`; `.riftreader-local\current-truth-refresh-plan\latest\summary.json` applied at `2026-05-31T16:08:47Z` with `updateCount=13`. |
| Boundary | API-now evidence remains the 2026-05-31 bounded family snapshot ending `2026-05-31T14:22:57Z`; this refresh is not proof promotion. |

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

These samples validate the promoted resolver historically. They must not be presented as current live PID API-now proof. Movement displacement agreed between the API surface and chain readback:

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

Continue from this promoted coordinate resolver with exact-target/freshness preflights. Current PID `41808` static readback refreshed at `2026-06-01T04:19:15.250942+00:00` and RRAPICOORD API-now matched at `2026-06-01T04:20:16.895781Z` with max abs delta `0.004316406`; before presenting coordinates as API-confirmed truth in a later session, refresh API-now vs memory-now evidence again. Keep actor/stat field discovery separate from this coordinate promotion.
