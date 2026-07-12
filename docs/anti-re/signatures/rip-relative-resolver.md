# RIP-Relative Resolver Methodology

Created: 2026-07-11
Status: **design phase**

## Problem

In x86-64, most global variable accesses use RIP-relative addressing:
```asm
mov rax, [rip + 0x12345678]  ; load from global variable
mov [rip + 0x12345679], rdi   ; store to global variable
```

The displacement (`0x12345678`) is encoded in the instruction but resolves to
an absolute address only at runtime:
```
absolute_address = instruction_address + instruction_length + displacement
```

When we find an AOB signature match at runtime, we know the instruction
address but need to resolve the RIP-relative operand to find the static
global it references.

## Resolution Formula

```python
def resolve_rip_relative(instruction_addr, instruction_bytes, operand_offset):
    """
    Resolve a RIP-relative displacement to an absolute virtual address.

    instruction_addr: virtual address of the matched instruction
    instruction_bytes: raw bytes of the instruction
    operand_offset: byte offset within instruction where displacement starts
    """
    # Read the 32-bit signed displacement
    disp = int.from_bytes(instruction_bytes[operand_offset:operand_offset+4], 'little', signed=True)

    # Calculate absolute address
    # RIP points to the NEXT instruction, so add full instruction length
    instruction_length = len(instruction_bytes)
    absolute_addr = instruction_addr + instruction_length + disp

    return absolute_addr
```

## Implementation Plan

### Input
- AOB pattern (bytes + mask)
- Module base address (from process)
- Binary file (for offline displacement extraction)

### Process
1. Scan process `.text` section for AOB pattern
2. For each match, read the full instruction bytes
3. Decode the instruction (Capstone) to find operand positions
4. Extract displacement from the operand
5. Resolve: `target = match_addr + instruction_length + displacement`
6. Validate: target should be in a writable section (`.data`, `.rdata` writable, heap)

### Output
```json
{
  "aobId": "coord-write-0x320",
  "matchAddress": "0x7FF721234567",
  "instructionBytes": "F3 0F 11 05 78 56 34 12",
  "displacement": 0x12345678,
  "instructionLength": 8,
  "resolvedGlobalAddress": "0x7FF72457ABDF",
  "resolvedGlobalRva": "0x32EBC80",
  "section": ".data"
}
```

## Existing Code to Reuse

| Component | Source | Use |
|---|---|---|
| Capstone disassembler | `postupdate_static_access_chain.py` already imports it | Decode instructions |
| Memory reader | `rift_research/memory.py` | Read process memory |
| AOB scanner | `Research/rift_research/scanners.py` AOBScanner | Find pattern matches |
| PE section parser | `pefile` (used by `postupdate_static_access_chain.py`) | Get `.text` section bounds |

## Script: `scripts/anti-re/rip_relative_resolver.py`

_Todo: implement._
