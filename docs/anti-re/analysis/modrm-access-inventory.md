# ModRM Access Inventory

Created: 2026-07-11
Status: **needs execution**
Tool: `C:\RIFT MODDING\Assets\scripts\modrm_scanner.py`

## Purpose

Map every instruction in `rift_x64.exe` that accesses the known owner offsets
(`+0x300`, `+0x304`, `+0x30C`, `+0x310`, `+0x314`, `+0x320`, `+0x324`,
`+0x328`, `+0x438`, `+0x43C`, `+0x440`). This produces the complete set of
coordinate-accessing instructions needed for AOB signature extraction.

## Command

```powershell
python "C:\RIFT MODDING\Assets\scripts\modrm_scanner.py" `
  --binary "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" `
  --offset 0x320,0x324,0x328,0x30C,0x310,0x314,0x304,0x300,0x438,0x43C,0x440 `
  --json
```

## Expected Output

| Field | Description |
|---|---|
| Total instructions found | Count of ModRM instructions accessing target offsets |
| Per-offset breakdown | How many instructions access each offset |
| Function grouping | Which functions contain these instructions |
| RIP-relative operands | Which instructions use `[rip+disp]` (candidate static globals) |
| AOB candidates | Unique byte sequences suitable for signature creation |

## Analysis

_Pending execution._

## AOB Extraction

After ModRM scan completes, for each unique instruction sequence:
1. Extract 8-16 bytes of surrounding context
2. Identify which bytes are variable (addresses, displacements)
3. Replace variable bytes with `??` wildcards
4. Test uniqueness across the entire `.text` section
5. Store in `docs/anti-re/signatures/coordinate-access-aobs.json`
