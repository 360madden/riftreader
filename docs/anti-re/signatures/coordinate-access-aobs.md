# Coordinate Access AOB Signatures

Created: 2026-07-11
Status: **needs generation** — requires ModRM scan + Ghidra analysis

## Purpose

Machine-readable AOB (Array of Bytes) patterns for identifying
coordinate-accessing instructions in `rift_x64.exe` at runtime.

## Schema

```json
{
  "schemaVersion": 1,
  "kind": "riftreader-coordinate-aob-database",
  "binary": "rift_x64.exe",
  "binaryHash": "<sha256>",
  "generatedAtUtc": "<ISO-8601>",
  "signatures": [
    {
      "id": "coord-write-0x320",
      "label": "Player X coordinate write",
      "targetOffset": "0x320",
      "aob": "F3 0F 11 ?? ?? ?? ?? ?? F3 0F 11 ?? 20",
      "mask": "xx??xxx?xxx??",
      "ripRelativeOffset": 3,
      "instructionLength": 8,
      "resolvedGlobalRva": "0xNNNNNNN",
      "functionRva": "0xNNNNN",
      "confidence": "high|medium|low",
      "notes": ""
    }
  ]
}
```

## Signature Extraction Workflow

```
1. Run modrm_scanner.py → list of instructions accessing +0x320, etc.
2. For each instruction:
   a. Read 8-16 surrounding bytes from .text section
   b. Identify which bytes are constant (opcode, ModRM, SIB)
   c. Identify which bytes are variable (RIP-relative displacement, immediate)
   d. Replace variable bytes with ?? wildcards
   e. Test uniqueness: count occurrences in full .text section
   f. If unique (count == 1): store as signature
3. Store in this file as JSON
4. At runtime: scan .text for signature → found address
5. Resolve RIP-relative: target = found_addr + instruction_length + displacement
```

## Signatures

_Pending generation from ModRM scan results._
