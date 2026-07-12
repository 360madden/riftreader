# Live Client Session — 2026-07-11

## Target

| Field | Value |
|---|---|
| PID | `4736` |
| HWND | `0x4B0B54` |
| Module base | `0x7FF728B80000` |
| Binary | `rift_x64.exe` (60,024,256 bytes) |
| Game state | **Login/character select** — no coordinates in memory |

## Offline Analysis Results

### ModRM Scan (2948 instructions found)

| Offset | Count | Notes |
|---|---|---|
| `0x320` | 623 | Highest — primary coordinate field |
| `0x328` | 646 | Second highest — Z coordinate |
| `0x310` | 566 | Facing target |
| `0x318` | 528 | Extended facing |
| `0x308` | 400 | Unknown adjacent |
| `0x30C` | 38 | Facing X |
| `0x324` | 39 | Y coordinate |
| `0x304` | 35 | Turn rate |
| `0x314` | 41 | Facing Z |
| `0x31C` | 32 | Unknown adjacent |

**Top cluster:** RVA `0x72A264`, 15 hits, accesses `+0x318`, `+0x320`, `+0x328` —
primary coordinate read/write cluster. Raw AOB: `87 18 03 00 00 89 83 18 03 00 00 48 8B 97 20 03 00 00 4C 8B AF 28 03 00 00 48 8B B3 20 03 00 00`

**Cluster 13 (RVA `0x3FA35`):** 8 hits, RDI-based, writes `+0x304` through
`+0x314` — likely the nav-state update cluster. Raw: `AF 04 03 00 00 44 89 AF 08 03 00 00 44 89 AF 0C 03 00 00 44 89 AF 10 03 00 00 C7 87 14 03 00 00`

### RTTI Scan (363 classes found)

**Player-related (21):** All Havok physics character classes:
- `hkpCharacterContext`, `hkpCharacterMotion`, `hkpCharacterProxy`
- `hkpCharacterState`, `hkpCharacterStateInAir`, `hkpCharacterStateJumping`
- `hkpCharacterStateManager`, `hkpCharacterStateOnGround`
- `hkpEntity`, `hkpEntityEntityBroadPhaseListener`, `hkpEntityListener`
- `hkpContactMgrFactory`, `hkpDisableEntityCollisionFilter`
- `hkpNullContactMgrFactory`, `hkpPoweredChainMapper`

**World-related (13):** Havok physics world classes:
- `hkpWorld`, `hkpWorldCinfo`, `hkpWorldObject`
- `hkpKdTreeWorldManager`, `hkpWorldLinearCaster`, `hkpWorldRayCaster`

**Key insight:** No obvious "Player" or "Actor" class — the player entity is
managed through the Havok physics system. The player object is likely an
`hkpCharacterProxy` or `hkpEntity` subclass with custom offsets.

### Live Memory Check

| Address | Value | Notes |
|---|---|---|
| `rift_x64+0x32EBC80` | `0x0` | Old root — **null** (confirmed) |
| `rift_x64+0x32DD7E8` | `0x7FF72BE5D7A0` | Container — **has value** |
| `[0x32DD7E8]+0x80` | `0x0` | Child — null (game not in-world) |
| `rift_x64+0x335F508` | `0x0` | Orientation anchor — null |

### Container Neighborhood Scan

Container at `0x7FF72BE5D7A0` has valid pointers throughout its neighborhood.
The `+0x80` child slot is null because no character is loaded. Self-pointer at
`+0x048` suggests a circular/sentinel data structure.

**Nearby valid pointers:**
- `container+0x00`: `0x7FF72B8C6D20`
- `container-0x28`: `0x7FF72B8C6A68`
- `container-0x80`: `0x7FF72BE5D130`
- `container+0x0B0/0x0B8`: `0x7FF72BE5D868`
- `container+0x0C0`: `0x7FF72BE5D888`

No coordinate-like float triplets found in `.data`, `.rdata`, or container
neighborhood. **Game is at login/character select.**

## AOB Signature Candidates (Top Clusters)

| Cluster | RVA | AOB (wildcarded) | Hits |
|---|---|---|---|
| 1 | `0x72A264` | `87 ?? ?? ?? ?? 89 83 ?? ?? ?? ?? 48 8B 97 ?? ?? ?? ?? 4C 8B AF ?? ?? ?? ?? 48 8B B3 ?? ?? ?? ??` | 15 |
| 3 | `0x5E51EB` | `48 83 EC 20 48 8B D9 48 8B 89 ?? ?? ?? ?? 48 85 C9 75 28 48 8B 53 10 48 63 05 58 A9 8F 02 0F B6` | 14 |
| 5 | `0x786B2F` | `8B ?? ?? ?? ?? 48 85 C9 74 11 48 8B 01 BA 01 00 00 00 FF 10 48 89 B3 ?? ?? ?? ?? 48 8B 8B 08 03` | 10 |
| 6 | `0xB3368F` | `85 ?? ?? ?? ?? 44 88 A5 D8 04 00 00 48 89 85 ?? ?? ?? ?? 4C 8D 8D ?? ?? ?? ?? 48 8D 85 28 03 00` | 10 |
| 13 | `0x3FA35` | `AF ?? ?? ?? ?? 44 89 AF ?? ?? ?? ?? 44 89 AF ?? ?? ?? ?? 44 89 AF ?? ?? ?? ?? C7 87 ?? ?? ?? ??` | 8 |

## Next Steps

1. **Enter the game world** with a character — then rerun coordinate discovery
2. **Run full coordinate family scan** once in-world
3. **Test AOB signatures** from top clusters against live process
4. **Build RIP-relative resolver** for the top cluster signatures
