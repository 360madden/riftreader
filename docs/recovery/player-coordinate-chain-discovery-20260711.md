# **BREAKTHROUGH — Player Coordinate + Heading Chain Found**

## Date: 2026-07-11

## Chain

```
Static global: rift_x64+0x32EBDC0  (.data section, RVA 0x32EBDC0)
  → Pointer to heap object
    → +0x320: X coordinate (float)
    → +0x324: Y coordinate (float)
    → +0x328: Z coordinate (float)
    → +0x300: Heading (cumulative rotation counter, mod 360 = degrees)
    → +0x304: Speed / turn rate (float)
```

## Verified Values (Session 2, PID 552)

| Source | X | Y | Z |
|---|---|---|---|
| Memory (`[[0x32EBDC0]+0x320]`) | 6974.50 | 840.31 | 3324.52 |
| API (SavedVariables fallback) | ~6974 | ~840 | ~3324 |
| Delta | <2 units (movement timing) | | |

## Restart Survival (3 sessions)

| Session | PID | Module base | X | Y | Z | Heading | Date |
|---|---|---|---|---|---|---|---|
| 1 | 20080 | 0x7FF728B80000 | 6964.14 | 841.08 | 3331.19 | — | 2026-07-11 ~18:00 |
| 2 | 552 | 0x7FF728B80000 | 6974.50 | 840.31 | 3324.52 | 192.75° | 2026-07-11 ~18:30 |
| 3 | 16008 | 0x7FF728B80000 | 6974.50 | 840.31 | 3324.52 | 22.94° | 2026-07-11 ~19:58 |

**Chain survives restart. Same binary, same ASLR base, same coordinate chain.**

## Movement Validation

| Test | Input | Before | After | Delta |
|---|---|---|---|---|
| Forward (W 500ms) | C# SendInput ScanCode | X=6964.14 | X=6974.50 | +10.36 |
| Left turn (A 500ms) | C# SendInput ScanCode | H=192.75° | H=122.44° | -70.31° |
| Right turn (D 500ms) | C# SendInput ScanCode | H=122.44° | H=143.49° | +21.05° |

## Heading Formula

```
heading_degrees = read_float(player_object + 0x300) % 360
```

- Cumulative rotation counter (increases with right turns, decreases with left)
- Mod 360 gives heading in degrees
- Verified with A/D key turns

## Field Map at Player Object

| Offset | Type | Meaning | Evidence |
|---|---|---|---|
| +0x300 | float (counter) | Heading: cumulative rotation, mod 360 = degrees | A/D turn tests |
| +0x304 | float | Speed or turn rate (2.14 → -1.22 during turns) | Movement tests |
| +0x308 | float | Unknown (near zero) | Static read |
| +0x30C | float | Previous X or movement start (zeros after idle) | Static read |
| +0x310 | float | Previous Y (zeros after idle) | Static read |
| +0x314 | float | Previous Z (zeros after idle) | Static read |
| +0x318 | pointer | Dormant object pointer (all-zero content when inactive) | Static read |
| +0x320 | float | **Current X** | API match + movement |
| +0x324 | float | **Current Y** | API match + movement |
| +0x328 | float | **Current Z** | API match + movement |

## Other Offsets at Same Object (PID 20080 snapshot)

| Offset | Value | Likely Meaning |
|---|---|---|
| +0x304 | 2.14 | Speed or turn rate |
| +0x308 | -0.00 | Unknown |
| +0x30C | 6952.58 | Previous X or movement start |
| +0x310 | 837.20 | Previous Y |
| +0x314 | 3330.42 | Previous Z |
| +0x318 | 1638.28 | Dormant object pointer |
| +0x320 | 6964.14 | **Current X** |
| +0x324 | 841.08 | **Current Y** |
| +0x328 | 3331.19 | **Current Z** |
| +0x80 | ptr → 0x214491F0738 | Sub-object pointer |

## Object Structure

The object at the target address has:
- Self-pointers at `+0x10`, `+0x30`, `+0x50`, `+0x70` (all → itself)
- Code pointers at `+0x00`, `+0x08`, `+0x18`, `+0x20`, `+0x28`, etc. (in `.text` range)
- This is a Havok/game engine object with vtable entries

## Key Discovery

The ModRM scanner found **offset 0x320 with 623 hits** — the highest density of any coordinate offset. This matches exactly. The ModRM instructions use `[RDI+0x320]` or `[RBX+0x320]` where the base register holds the heap object pointer.

## Resolver Script

```powershell
# One-shot read
python scripts\resolve-player-coords.py --pid <pid> --json

# Continuous polling (writes latest.json in rift-bridge format)
python scripts\resolve-player-coords.py --pid <pid> --watch --interval 200 --output .local\state\latest.json
```

## How to Read (Python)

```python
import ctypes
kernel32 = ctypes.windll.kernel32
handle = kernel32.OpenProcess(0x0010, False, PID)
base = 0x7FF728B80000  # module base (ASLR)

# Read player object pointer
obj_ptr = ctypes.c_ulonglong()
kernel32.ReadProcessMemory(handle, ctypes.c_void_p(base + 0x32EBDC0), ctypes.byref(obj_ptr), 8, None)

# Read coordinates
x = ctypes.c_float()
y = ctypes.c_float()
z = ctypes.c_float()
kernel32.ReadProcessMemory(handle, ctypes.c_void_p(obj_ptr.value + 0x320), ctypes.byref(x), 4, None)
kernel32.ReadProcessMemory(handle, ctypes.c_void_p(obj_ptr.value + 0x324), ctypes.byref(y), 4, None)
kernel32.ReadProcessMemory(handle, ctypes.c_void_p(obj_ptr.value + 0x328), ctypes.byref(z), 4, None)

# Read heading
heading_raw = ctypes.c_float()
kernel32.ReadProcessMemory(handle, ctypes.c_void_p(obj_ptr.value + 0x300), ctypes.byref(heading_raw), 4, None)
heading_deg = heading_raw.value % 360

print(f"X={x.value:.2f} Y={y.value:.2f} Z={z.value:.2f} heading={heading_deg:.1f}°")
```

## Global RVA

`0x32EBDC0` is at RVA `0x32EBDC0` in `rift_x64.exe` (build `STABLE-1-1152-a-1256395`).

This is NOT the container at `0x32DD7E8` — that's a global table of engine subsystems.
This is NOT the old dead root at `0x32EBC80` — zero references in the binary.

## Status

- **Restart survival:** CONFIRMED (3 sessions: PIDs 20080, 552, 16008)
- **Movement validation:** CONFIRMED (forward + turning)
- **Heading formula:** CONFIRMED (`+0x300 % 360`)
- **Discovery evidence:** `docs/recovery/player-coordinate-chain-discovery-20260711.md`
- **Anti-RE analysis:** `docs/anti-re/analysis/live-session-20260711.md`
- **Promoted:** NO — needs full multi-session displacement validation before navigation use
