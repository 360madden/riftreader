# Current RIFT live truth — PLAYER COORDINATE CHAIN CONFIRMED

Updated UTC: `2026-07-11T19:58:00Z`

# **✅ RESULT — CONFIRMED COORDINATE + HEADING CHAIN**

## Durable chain (restart-surviving)

```
Static global: rift_x64+0x32EBDC0  (RVA 0x32EBDC0, .data section)
  → Pointer to heap object
    → +0x320: X coordinate (float)
    → +0x324: Y coordinate (float)
    → +0x328: Z coordinate (float)
    → +0x300: Heading (cumulative rotation counter, mod 360 = degrees)
    → +0x304: Speed / turn rate (float)
```

## Verification across restarts

| Session | PID | Module base | X | Y | Z | Heading | Evidence |
|---|---|---|---|---|---|---|---|
| Session 1 | 20080 | 0x7FF728B80000 | 6964.14 | 841.08 | 3331.19 | — | API match (delta <2) |
| Session 2 | 552 | 0x7FF728B80000 | 6974.50 | 840.31 | 3324.52 | 192.75° | Movement + heading tests |
| Session 3 | 16008 | 0x7FF728B80000 | 6974.50 | 840.31 | 3324.52 | 22.94° | Restart survival confirmed |

**All three sessions: same binary, same ASLR base, same coordinate chain, same player position.**

## Movement validation

| Test | Input | Result |
|---|---|---|
| Forward (W key 500ms) | ScanCode via C# SendInput | X delta +10.36 (6964→6974) |
| Left turn (A key 500ms) | ScanCode via C# SendInput | Heading 192.75° → 122.44° |
| Right turn (D key 500ms) | ScanCode via C# SendInput | Heading 122.44° → 143.49° |

## Field map at player object

| Offset | Type | Meaning | Restart-stable? |
|---|---|---|---|
| +0x300 | float (counter) | Heading: cumulative rotation, mod 360 = degrees | ✅ |
| +0x304 | float | Speed or turn rate (2.14 → -1.22 during turns) | ✅ |
| +0x308 | float | Unknown (near zero) | — |
| +0x30C | float | Previous X or movement start (zeros after idle) | — |
| +0x310 | float | Previous Y (zeros after idle) | — |
| +0x314 | float | Previous Z (zeros after idle) | — |
| +0x318 | pointer | Dormant object pointer (all-zero content when inactive) | — |
| +0x320 | float | **Current X** | ✅ |
| +0x324 | float | **Current Y** | ✅ |
| +0x328 | float | **Current Z** | ✅ |

## Resolver script

```powershell
# One-shot
python scripts\resolve-player-coords.py --pid <pid> --json

# Continuous polling (writes latest.json in rift-bridge format)
python scripts\resolve-player-coords.py --pid <pid> --watch --interval 200 --output .local\state\latest.json
```

Output matches `watch_rift.py` JSON schema: `position.x/y/z`, `navigation.yawDeg`, `navigation.isMoving`, `transport: "memory-chain"`.

## Dead chain (historical)

The previous root `rift_x64+0x32EBC80` is **dead** — zero references in current binary. The old promoted chain `[[0x32EBC80]+0x320]` does not work. Do not use it.

## Status

- **Restart survival:** CONFIRMED across 3 sessions (PIDs 20080, 552, 16008)
- **Movement validation:** CONFIRMED (forward + turning)
- **Heading formula:** CONFIRMED (`+0x300 % 360`)
- **Discovery evidence:** `docs/recovery/player-coordinate-chain-discovery-20260711.md`
- **Anti-RE analysis:** `docs/anti-re/analysis/live-session-20260711.md`
- **Promoted:** NO — needs full multi-session displacement validation before navigation use

---

# Historical context

## Previous promoted chain (DEAD — do not use)

The old chain `[[rift_x64+0x32EBC80]+0x320]` was promoted on 2026-05-27 and validated across PIDs 34176, 25668, 41808, and 12664. It is now dead — the `0x32EBC80` global has zero references in the current binary. The old chain is preserved in `docs/recovery/historical/` for audit only.

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

## Required operating rule

Use the new `[[0x32EBDC0]+0x320]` chain as the current coordinate source. Keep live workflows fail-closed:

1. Find PID via `Get-Process rift_x64`
2. Find module base (fast-path known bases, then MZ scan)
3. Read `moduleBase + 0x32EBDC0` → heap object pointer
4. Read `object+0x320/+0x324/+0x328` for X/Y/Z
5. Read `object+0x300` mod 360 for heading
6. Before navigation, perform fresh same-target readback and reject stale values

## Canonical artifacts

| Artifact | Path |
|---|---|
| New chain discovery report | `docs/recovery/player-coordinate-chain-discovery-20260711.md` |
| Anti-RE analysis | `docs/anti-re/analysis/live-session-20260711.md` |
| AOB database | `artifacts/anti-re/coordinate-aob-database.json` |
| Global reference map | `artifacts/anti-re/data-global-reference-map.md` |
| Resolver script | `scripts/resolve-player-coords.py` |
| Historical promotion report | `docs/recovery/static-owner-coordinate-chain-promoted-2026-05-27.md` |
