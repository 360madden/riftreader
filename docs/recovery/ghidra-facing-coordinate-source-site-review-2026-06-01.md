# Ghidra facing/coordinate source-site review — 2026-06-01

## Verdict

The offline Ghidra pointer evidence supports a shared owner-layout cluster around
candidate facing target `owner+0x30C/+0x310/+0x314`, support-only scalar
`owner+0x304`, and the promoted coordinate chain `owner+0x320/+0x324/+0x328`.

This is **supporting evidence only**. It does **not** prove static-root/source
site ownership, restart/relog survival, three-pose displacement, or promotion
readiness by itself.

## Source artifact

| Field | Value |
|---|---|
| Pointer evidence | `scripts/captures/ghidra-static-analysis-20260601-043934/pointer-evidence.json` |
| Program | `rift_x64.exe` |
| Image base | `0x140000000` |
| Root RVA | `0x32EBC80` |
| Root address | `0x1432EBC80` |
| Promotion performed | `false` |

## Offset review

| Owner offset | Role in current lane | Hit count | Write-like count | First owner-layout write-like instruction | Interpretation |
|---|---|---:|---:|---|---|
| `0x304` | Support-only turn-rate/scalar | 80 | 28 | `14003fa33: MOV dword ptr [RDI + 0x304],R13D` | Same nearby owner writer cluster as facing/coordinate fields; keep support-only until dedicated proof. |
| `0x30C` | Candidate facing-target X | 65 | 26 | `14003fa41: MOV dword ptr [RDI + 0x30c],R13D` | Candidate-facing target appears in the same owner write sequence as promoted coordinate fields. |
| `0x314` | Candidate facing-target Z / constant component | 66 | 35 | `14003fa4f: MOV dword ptr [RDI + 0x314],0x3f800000` | Nearby constant write supports a structured vector/target component, not promotion alone. |
| `0x320` | Promoted coordinate X | 80 | 22 | `14003fa67: MOV dword ptr [RDI + 0x320],R13D` | Matches the promoted coordinate owner offset and appears in the same writer cluster. |
| `0x324` | Promoted coordinate Y | 57 | 21 | `14003fa6e: MOV dword ptr [RDI + 0x324],R13D` | Same owner write sequence as coordinate X/Z. |
| `0x328` | Promoted coordinate Z / constant component | 80 | 19 | `14003fa75: MOV dword ptr [RDI + 0x328],0x3f800000` | Same owner write sequence as promoted coordinates; supports layout continuity. |

## Safety and promotion boundary

| Boundary | Status |
|---|---|
| Offline-only artifact review | Passed |
| Live input sent by this review | No |
| Target memory read by this review | No |
| x64dbg / Cheat Engine attached | No |
| Provider writes | No |
| Truth/facing promotion | No |

## Remaining proof requirements

1. Formal three-pose displacement package for route progress against
   `current-facing-target-0x30C`.
2. Restart/relog survival packet with distinct pre/post process-start epochs.
3. Static-root/source-site review that ties the root chain and owner writes to a
   stable resolver contract, not just nearby offset hits.
4. Fresh API-now vs chain-now readback on the exact target immediately before
   any promotion review.
5. Separate proof/promotion review artifact; no automatic promotion from this
   source-site note.
