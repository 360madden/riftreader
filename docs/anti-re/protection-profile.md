# RIFT Protection Profile

Created: 2026-07-11
Binary: `rift_x64.exe` (64-bit PE, Gamebryo-based engine)

## Protection Stack

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Server-Side Validation                        │
│  • Movement speed / teleport detection                  │
│  • Bot behavior pattern analysis                        │
│  • Coin Lock (geographic IP anomaly)                    │
│  • Economy monitoring                                    │
│  → Cannot be bypassed from client                       │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Client Anti-Cheat Scanner                     │
│  • Custom "Warden-like" user-mode scanner               │
│  • Process name scanning (all running processes)        │
│  • DLL module scanning within rift_x64.exe              │
│  • Flags suspicious modules (e.g., mscoree.dll)         │
│  • No kernel driver (unlike EAC/BattlEye)               │
│  → External ReadProcessMemory is not blocked            │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Binary Protections                            │
│  • Standard Windows ASLR (base randomized per launch)   │
│  • No confirmed packer (Themida/VMProtect/Arxan)        │
│  • No code virtualization                               │
│  • No obfuscated IAT                                    │
│  • Encrypted network protocol                           │
│  → Binary loads cleanly in Ghidra/IDA                   │
├─────────────────────────────────────────────────────────┤
│  Layer 1: Engine-Level (Modified Gamebryo)              │
│  • Heavy dynamic memory allocation (heap objects)       │
│  • 64-bit / multicore in-house modifications            │
│  • Custom asset packaging (hash-named archives)         │
│  • Object addresses change every session                │
│  → This is the real challenge for RE                    │
└─────────────────────────────────────────────────────────┘
```

## What's NOT Protected

| Aspect | Status | Implication |
|---|---|---|
| Binary packing | **Unpacked** | Ghidra/IDA can load directly |
| IAT obfuscation | **Standard** | Import table is readable |
| Code virtualization | **None** | All code is native x86-64 |
| Anti-debug | **User-mode only** | x64dbg can attach (may trigger scanner) |
| Memory read protection | **None** | ReadProcessMemory works freely |
| Data structure integrity checks | **None** | No self-validation on game objects |

## What IS Protected (by architecture)

| Aspect | Mechanism | Impact |
|---|---|---|
| Object addresses | Heap allocation + ASLR | No stable pointer to player object |
| Root pointer | Manager/container pattern | Static globals point at containers, not instances |
| Accessor uniqueness | 197+ call sites share the same accessor | Can't identify player-specific code path by instruction alone |
| Update sensitivity | In-house engine modifications | Structure offsets stable, but root pointers can null |
| Network encryption | Custom protocol | Can't sniff coordinates from network |

## Coordinate Data Layout (Known)

Based on reverse engineering across multiple PID epochs:

```
Owner object (heap-allocated, address changes per session)
├── +0x300  unknown
├── +0x304  yaw-adjacent scalar (candidate turn rate)
├── +0x30C  facing target X (float)
├── +0x310  facing target Y (float)
├── +0x314  facing target Z (float)
├── +0x320  player X coordinate (float)
├── +0x324  player Y coordinate (float, vertical)
├── +0x328  player Z coordinate (float)
├── +0x438  catalog support field
├── +0x43C  catalog support field
└── +0x440  catalog support field
```

**Key observation:** Offsets within the object are stable across patches.
The problem is finding the object, not reading its fields.

## Known Static Globals

| Global | Status | Notes |
|---|---|---|
| `rift_x64+0x32EBC80` | **Null since 2026-06-02** | Was the promoted root; update nullified it |
| `rift_x64+0x32DD7E8` | **Candidate** | Container pointer; `+0x80` → child with coords |
| `rift_x64+0x335F508` | **Candidate** | Orientation/matrix root, not position |

## Accessor Code Patterns

The coordinate fields are accessed by multiple code paths. Key RVAs:

| RVA | Function | Notes |
|---|---|---|
| `0x3F8B0` | Constructor/writer | Writes owner field cluster; stores `rdi` to `rift_x64+0x335F508` |
| `0xC38390` | Reader | Reads `rift_x64+0x32DD7E8` container |
| `0x687F90` | Common accessor | `rcx + 0x48` — 197 call xrefs, not unique |
| `0x579F75..0x579FE3` | Compare/copy block | XYZ comparison and copy operations |
| `0x57C2A5` | `[rcx+0x10]` access | Code pattern matches known candidate spacing |

## Implications for Anti-RE Strategy

1. **AOB signatures will work** — the binary is unpacked, code is readable,
   and instruction patterns are stable
2. **RTTI will work** — MSVC C++ with RTTI means class names are in `.rdata`
3. **Hardware watchpoints will work** — no kernel anti-debug to block them
4. **The challenge is architectural** — finding the object root through dynamic
   allocation, not defeating protections
