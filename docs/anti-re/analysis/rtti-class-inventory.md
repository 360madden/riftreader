# RTTI Class Inventory

Created: 2026-07-11
Status: **needs execution**
Tool: `C:\RIFT MODDING\Assets\scripts\discover_secondary_structs.py`

## Purpose

Enumerate all MSVC RTTI class names in `rift_x64.exe`. Identify player/actor
entity classes that can be used for vtable-based instance discovery.

## Command

```powershell
python "C:\RIFT MODDING\Assets\scripts\discover_secondary_structs.py" `
  --binary "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" `
  --json
```

## Expected Output

| Field | Description |
|---|---|
| Total RTTI entries | Count of `.?AV` class names found |
| Player-related classes | Classes with names containing "player", "actor", "character", "entity" |
| VTable addresses | Address of each vtable in `.rdata` |
| Inheritance hints | VTable prefix relationships suggesting inheritance |

## Analysis

_Pending execution._
