# Current RIFT live truth — POST-PATCH STATIC ROOT BLOCKED

Updated UTC: `2026-07-18T05:05:46Z`

## **⚠️ BLOCKER — PRE-PATCH ROOT IS NULL IN THE CURRENT BINARY**

The installed RIFT executable changed after the 2026-07-14 baseline. A fresh
exact-target, no-input readback on 2026-07-18 resolved the current process and
module base successfully, but `rift_x64+0x32EBDC0` contained a null owner
pointer. The July coordinate and heading chain is therefore a **pre-patch
recovery baseline**, not current live navigation truth.

| Current target field | Value |
|---|---|
| PID / HWND | `4256` / `0x1ED0C56` |
| Process start UTC | `2026-07-18T05:00:28.788Z` |
| Module base | `0x7FF78ECD0000` |
| Installed exe SHA256 | `7A3AAE5383E392210B169ACDE0FC00A9EA262A100DED65041E851C26F4884DD7` |
| Installed exe size | `59,969,472` bytes |
| Pre-patch exe SHA256 | `7D2595BE8D9543ACFF7808B12796C967FB690C7825FD7DD6846AC2194E551D40` |
| Pre-patch exe size | `60,024,256` bytes |
| Root readback | `[moduleBase+0x32EBDC0] = 0x0` |
| Verdict | `root-pointer-null` |

Current consequences:

- Do not run navigation from the July static resolver.
- Do not publish `owner+0x320/+0x324/+0x328` or
  `[[owner+0x330]+0x158]` as current post-patch values.
- Do not promote a replacement root from pre-patch artifacts.
- Continue with offline caller/xref analysis before repeating live RVA sweeps.
- Movement, displacement proof, debugger/CE work, and promotion remain
  separately approval-gated.

Safe next action:

```powershell
.\scripts\riftreader-ghidra-static-evidence.cmd --run --binary-path 'C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe' --json
```

## Last validated pre-patch chain (historical recovery baseline)

```text
Static global: rift_x64+0x32EBDC0  (RVA 0x32EBDC0, .data section)
  → Pointer to heap object
    → +0x320: X coordinate (float)
    → +0x324: Y coordinate (float)
    → +0x328: Z coordinate (float)
    → +0x300: Cumulative rotation counter (legacy heading proxy; not direct heading)
    → +0x304: Speed / turn rate (float)
    → +0x330: Camera-state child pointer
        → +0x158: Direct heading (float, radians)
```

## Pre-patch heading-source reconciliation (2026-07-12)

The coordinate owner and coordinate offsets were the promoted position source
for the July 12 pre-patch epoch. Facing discovery superseded the earlier
interpretation of `owner+0x300` as the canonical heading:

| Source | Pre-patch classification | Historical use |
|---|---|---|
| `owner+0x300` | Cumulative rotation counter | Historical/diagnostic turn-change evidence only; do not publish it as direct facing |
| `[[owner+0x330]+0x158]` | Direct heading float in radians | Navigation-facing source used by `nav6`, `nav8`, and `FreshState`; provisional pending formal promotion gates |
| `[[owner+0x330]+0x2c/+0x34]` | Camera direction vector | Independent cross-check via `atan2(dx, dz)` |

The direct `+0x158` value matched the camera direction with a 0° offset, returned
to its baseline after a round-trip turn, drove the recorded `nav6`/`nav7`/`nav8`
tests, and was reported to survive a RIFT restart. The latest handoff labels it
promoted for navigation. That handoff does not link a standalone, gate-by-gate
promotion report, so this document records `+0x158` as **practically validated
but provisionally classified**, not as formally promoted current truth.

Formal promotion still requires a durable timestamped proof artifact with exact
PID/HWND/process-start binding, fresh truth-versus-`+0x158` agreement,
three-pose directional evidence, restart/relog survival, and artifact-freshness
checks. Handoff prose and commit messages do not replace those gates.

## Pre-patch verification across restarts

| Session | PID | Module base | X | Y | Z | `+0x300` support reading | Evidence |
|---|---|---|---|---|---|---|---|
| Session 1 | 20080 | 0x7FF728B80000 | 6964.14 | 841.08 | 3331.19 | — | API match (delta <2) |
| Session 2 | 552 | 0x7FF728B80000 | 6974.50 | 840.31 | 3324.52 | 192.75° | Movement + heading tests |
| Session 3 | 16008 | 0x7FF728B80000 | 6974.50 | 840.31 | 3324.52 | 22.94° | Restart survival confirmed |
| Session 4 | 36332 | 0x7FF728B80000 | 7003.19 | 841.92 | 3302.60 | 100.46° | Displacement validation passed |

**All four sessions used the same pre-patch binary, ASLR base, coordinate root,
and owner layout.**

## Historical movement validation

| Test | Input | Result |
|---|---|---|
| Forward (W key 500ms) | ScanCode via C# SendInput | X delta +10.36 (6964→6974) |
| Left turn (A key 500ms) | ScanCode via C# SendInput | Heading 192.75° → 122.44° |
| Right turn (D key 500ms) | ScanCode via C# SendInput | Heading 122.44° → 143.49° |
| Forward (W key 500ms) | WindowMessage via post-rift-key.ps1 | dist=3.21 units |
| Left turn (A key 500ms) | WindowMessage via post-rift-key.ps1 | Heading delta=22° |

## Historical displacement validation (2026-07-12)

| Test | Before | After | Delta | Status |
|---|---|---|---|---|
| Forward movement | X=7004.06 Y=842.55 Z=3305.62 | X=7003.19 Y=841.92 Z=3302.60 | dist=3.21 | ✅ PASS |
| Left turn | H=78.46° | H=100.46° | delta=22° | ✅ PASS |

**Chain coordinates respond correctly to both movement and turning.**

## Last validated API coverage (RiftReaderApiProbe v0.3.0)

| Global | Fields | Status |
|---|---|---|
| Player | id, name, level, calling, role, guild, coords, hp, mana, power, combat, mounted | ✅ Working |
| Target | 40+ fields (name, level, hp, coords, etc.) | ✅ Working |
| Environment | zone, location, shard, secure | ✅ Working |
| Nearby | up to 20 units with coords, name, level, calling, relation | ✅ Working |
| Abilities | 55 spells with cooldowns, ranges, weapon, channeled, passive | ✅ Working |
| Stats | armor, dexterity, endurance, crit, dodge, hit, resistances | ✅ Working |
| Live | backward-compat RRAPICOORD1 string | ✅ Working |

## Pre-patch field map at player object

| Offset | Type | Meaning | Restart-stable? |
|---|---|---|---|
| +0x300 | float (counter) | Cumulative rotation counter; legacy heading proxy, not direct heading | ✅ |
| +0x304 | float | Speed or turn rate (2.14 → -1.22 during turns) | ✅ |
| +0x308 | float | Unknown (near zero) | — |
| +0x30C | float | Previous X or movement start (zeros after idle) | — |
| +0x310 | float | Previous Y (zeros after idle) | — |
| +0x314 | float | Previous Z (zeros after idle) | — |
| +0x318 | pointer | Dormant object pointer (all-zero content when inactive) | — |
| +0x320 | float | **Current X** | ✅ |
| +0x324 | float | **Current Y** | ✅ |
| +0x328 | float | **Current Z** | ✅ |
| +0x330 | pointer | Camera-state child containing direct heading and direction vector | Reported across restart |

### Camera-state child map (`owner+0x330`)

| Offset | Type | Meaning | Evidence |
|---|---|---|---|
| +0x2C | float | Camera direction X | Matches direct heading via `atan2` |
| +0x34 | float | Camera direction Z | Matches direct heading via `atan2` |
| +0x158 | float | **Direct heading in radians** | 0° camera-direction offset; navigation-tested; restart survival reported |

## Resolver script

These commands remain diagnostic entry points. In the current post-patch epoch,
they must fail closed on the null `0x32EBDC0` root and must not publish stale
coordinates.

```powershell
# One-shot
python scripts\resolve-player-coords.py --pid <pid> --json

# Continuous polling (writes latest.json in rift-bridge format)
python scripts\resolve-player-coords.py --pid <pid> --watch --interval 200 --output .local\state\latest.json

# Registry-based (Assets repo approach - experimental)
python scripts\resolve-player-coords.py --pid <pid> --registry --json
```

Output matches `watch_rift.py` JSON schema: `position.x/y/z`, `navigation.yawDeg`, `navigation.isMoving`, `transport: "memory-chain"`.

## Dead chain (historical)

The previous root `rift_x64+0x32EBC80` was **dead** in the July pre-patch
binary. The old promoted chain `[[0x32EBC80]+0x320]` does not work. Do not use
it.

## Status

- **Current post-patch resolver:** ❌ **BLOCKED** — `rift_x64+0x32EBDC0` is null on exact PID `4256`
- **Current route/navigation authority:** ❌ **NONE** — replacement static root not recovered
- **Pre-patch restart survival:** CONFIRMED across 4 sessions (PIDs 20080, 552, 16008, 36332)
- **Pre-patch movement validation:** CONFIRMED (forward + turning, WindowMessage input)
- **Pre-patch direct heading formula:** `degrees([[owner+0x330]+0x158])`
- **Legacy counter:** `owner+0x300` remains diagnostic/support evidence, not canonical direct heading
- **Pre-patch displacement validation:** CONFIRMED (API vs chain agreement)
- **Discovery evidence:** `docs/recovery/player-coordinate-chain-discovery-20260711.md`
- **Anti-RE analysis:** `docs/anti-re/analysis/live-session-20260711.md`
- **Coordinate promotion:** historical/pre-patch only — `owner+0x320/+0x324/+0x328`
- **Heading classification:** historical/pre-patch and formally provisional

---

## Historical context

## Previous promoted chain (DEAD — do not use)

The old chain `[[rift_x64+0x32EBC80]+0x320]` was promoted on 2026-05-27 and
validated across PIDs 34176, 25668, 41808, and 12664. By July, the `0x32EBC80`
global had zero references in that pre-patch binary. The old chain is preserved
in `docs/recovery/historical/` for audit only.

## Historical promotion gate results (PID 34176, 2026-05-27)

| Gate | Result |
|---|---|
| Reboot/relogin survival | Passed |
| API-now vs chain-now baseline | Max delta 0.001933594 |
| API-now vs chain-now after forward | Max delta 0.001955469 |
| API-now vs chain-now after reverse | Max delta 0.004768066 |
| Cheat Engine / x64dbg | Not used |
| Target memory writes | None |

## Historical PID epoch propagation (PID 12664, 2026-06-01)

| Check | Result |
|---|---|
| Static root reacquired | Passed |
| Owner address changed | Passed (proves no heap address treated as static) |
| Coordinate offsets stable | Passed |
| Facing offsets stable | Passed |
| API-now validation | Max delta 0.00248046875 |

## Required post-patch operating rule

Do not use `[[0x32EBDC0]+0x320]` as the current coordinate source while the root
pointer is null. Keep recovery fail-closed:

1. Bind the exact PID, HWND, module base, and process start.
2. Confirm the installed executable identity against the pre-patch baseline.
3. Use offline caller/xref evidence to locate replacement root candidates.
4. Read candidate owners without input and reject null or implausible layouts.
5. Capture fresh API coordinates and compare with candidate coordinate fields.
6. Revalidate the camera child and direct heading only after position agrees.
7. Require restart/relog survival and formal proof gates before promotion.
8. Require separate approval before movement, displacement proof, or live input.

`docs/recovery/current-truth.json` still describes an older candidate/support
state and is not authoritative for the reconciled heading classification. A
broader structured-truth migration should update it only after the formal
promotion gates above are satisfied.

## Canonical artifacts

| Artifact | Path |
|---|---|
| New chain discovery report | `docs/recovery/player-coordinate-chain-discovery-20260711.md` |
| Anti-RE analysis | `docs/anti-re/analysis/live-session-20260711.md` |
| AOB database | `artifacts/anti-re/coordinate-aob-database.json` |
| Global reference map | `artifacts/anti-re/data-global-reference-map.md` |
| Resolver script | `scripts/resolve-player-coords.py` |
| Pre-update shutdown handoff | `handoffs/current/PRE_UPDATE_SERVER_SHUTDOWN_HANDOFF_2026-07-14.md` |
| Pre-update executable baseline | `handoffs/current/pre-update-baseline/20260714T075857Z-preupdate-capture-v001/executable-identity.json` |
| Pre-update root signature | `signatures/rift_x64/root_preupdate-final-coord-root.json` |
| Facing discovery handoff | `docs/handoff-2026-07-12-facing.md` |
| Navigation/heading handoff | `docs/handoffs/2026-07-12-navigation-heading-complete-handoff.md` |
| Camera-vector facing cross-check | `scripts/read-player-facing.py` |
| Navigation heading consumers | `scripts/nav6.py`, `scripts/nav8.py`, `scripts/fresh_state.py` |
| Historical promotion report | `docs/recovery/static-owner-coordinate-chain-promoted-2026-05-27.md` |
