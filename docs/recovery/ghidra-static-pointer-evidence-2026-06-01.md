# Ghidra static pointer evidence — 2026-06-01

## Verdict

Ghidra is now providing promotion-relevant static context, but this run is **candidate evidence only**. It does not promote facing, turn-rate, actor, or current-truth fields.

Key finding: the promoted root `rift_x64+0x32EBC80` is heavily referenced in code, and Ghidra found a compact owner-layout write cluster at `0x14003FA33..0x14003FA75` that writes `owner+0x304`, `owner+0x30C/+0x310/+0x314`, and `owner+0x320/+0x324/+0x328` through the same `RDI` owner pointer. This strongly supports that `0x30C` is part of the same owner layout as player coordinates, but the post-restart zero-vector readback still means the field is state-dependent/transient or reset in passive state, not promotion-ready.

## Run artifacts

| Artifact | Path |
|---|---|
| Ghidra import summary | `scripts/captures/ghidra-static-analysis-20260531-232046/summary.json` |
| Ghidra import log | `scripts/captures/ghidra-static-analysis-20260531-232046/analyzeHeadless.log` |
| Pointer evidence JSON | `scripts/captures/ghidra-static-analysis-20260531-232046/pointer-evidence.json` |
| Pointer evidence log | `scripts/captures/ghidra-static-analysis-20260531-232046/pointer-evidence.log` |
| Ghidra project | `scripts/captures/ghidra-static-projects/project-20260531-232046` |

## Root reference summary

| Field | Value |
|---|---:|
| Image base | `140000000` |
| Root RVA | `0x32EBC80` |
| Root address | `1432ebc80` |
| Root references captured | `200` (cap reached) |
| Root READ refs captured | `101` |
| Root WRITE refs captured | `99` |
| Instructions scanned for owner offsets | `5162625` |

Representative root refs:

- `1407c1eea` `READ` — `MOV RBX,qword ptr [0x1432ebc80]`
- `1407c1f1b` `READ` — `MOV RBX,qword ptr [0x1432ebc80]`
- `1407c1f9a` `WRITE` — `MOV qword ptr [0x1432ebc80],RBX`
- `1407c1fa9` `WRITE` — `MOV qword ptr [0x1432ebc80],RBX`
- `140970a57` `READ` — `MOV RBX,qword ptr [0x1432ebc80]`
- `140970a77` `READ` — `MOV RBX,qword ptr [0x1432ebc80]`
- `140970af6` `WRITE` — `MOV qword ptr [0x1432ebc80],RBX`
- `140970b05` `WRITE` — `MOV qword ptr [0x1432ebc80],RBX`
- `140488ea4` `READ` — `MOV RAX,qword ptr [0x1432ebc80]`
- `140488ece` `READ` — `MOV RBX,qword ptr [0x1432ebc80]`
- `140488f60` `WRITE` — `MOV qword ptr [0x1432ebc80],RBX`
- `140488f77` `WRITE` — `MOV qword ptr [0x1432ebc80],RBX`

## Priority owner-offset evidence

| Offset | Hits captured | Write-like | First relevant static hits |
|---|---:|---:|---|
| `0x304` | `80` | `28` | `14003fa33` write-or-destination: `MOV dword ptr [RDI + 0x304],R13D`<br>`140117c0e` write-or-destination: `MOVDQU xmmword ptr [RBX + 0x3040],XMM0`<br>`14013d1e3` write-or-destination: `MOVDQA xmmword ptr [RDI + 0x3040],XMM5`<br>`140198d24` write-or-destination: `MOV dword ptr [RBP + 0x304],EAX` |
| `0x30C` | `65` | `26` | `14003fa41` write-or-destination: `MOV dword ptr [RDI + 0x30c],R13D`<br>`1404d4a5d` write-or-destination: `MOV dword ptr [RBX + 0x30c],EBP`<br>`1404d6c66` destination-or-test: `CMP dword ptr [RDI + 0x30c],EBP`<br>`1404dc14a` read-or-source: `CMP EBX,dword ptr [RCX + 0x30c]` |
| `0x310` | `80` | `21` | `14003fa48` write-or-destination: `MOV dword ptr [RDI + 0x310],R13D`<br>`1400b13d3` write-or-destination: `MOVAPS xmmword ptr [RCX + RBX*0x1 + 0x310],XMM4`<br>`1400b14ee` read-or-source: `MOVAPS XMM1,xmmword ptr [RCX + R9*0x1 + 0x310]`<br>`14018c80c` write-or-destination: `MOVUPS xmmword ptr [RBP + 0x310],XMM1` |
| `0x314` | `66` | `35` | `14003fa4f` write-or-destination: `MOV dword ptr [RDI + 0x314],0x3f800000`<br>`14019b8e9` write-or-destination: `MOV dword ptr [RBP + 0x314],EAX`<br>`1404d4a6a` write-or-destination: `MOV dword ptr [RBX + 0x314],0x3f800000`<br>`1404dc123` read-or-source: `MULSS XMM0,dword ptr [RCX + 0x314]` |
| `0x320` | `80` | `22` | `14003fa67` write-or-destination: `MOV dword ptr [RDI + 0x320],R13D`<br>`1400b13db` write-or-destination: `MOVAPS xmmword ptr [RCX + RBX*0x1 + 0x320],XMM4`<br>`1400b1504` read-or-source: `MOVAPS XMM0,xmmword ptr [RCX + R9*0x1 + 0x320]`<br>`14018c817` write-or-destination: `MOV qword ptr [RBP + 0x320],RAX` |
| `0x324` | `59` | `21` | `14003fa6e` write-or-destination: `MOV dword ptr [RDI + 0x324],R13D`<br>`14057a89f` read-or-source: `UCOMISS XMM0,dword ptr [RDI + 0x324]`<br>`140a57b1a` write-or-destination: `MOV dword ptr [RSI + 0x324],EBP`<br>`140a58696` read-or-source: `MOV EAX,dword ptr [RBX + 0x324]` |
| `0x328` | `80` | `19` | `14003fa75` write-or-destination: `MOV dword ptr [RDI + 0x328],0x3f800000`<br>`14018c822` write-or-destination: `MOV dword ptr [RBP + 0x328],EAX`<br>`140198af9` write-or-destination: `MOVUPS xmmword ptr [RBP + 0x328],XMM1`<br>`140198bca` read-or-source: `MOV RAX,qword ptr [RBP + 0x328]` |
| `0x438` | `80` | `24` | `14003f399` write-or-destination: `MOVSS dword ptr [RCX + 0x438],XMM2`<br>`14004029c` write-or-destination: `MOVSS dword ptr [RDI + 0x438],XMM0`<br>`140048c7d` read-or-source: `MOVSS XMM0,dword ptr [RBP + 0x438]`<br>`140484b56` read-or-source: `LEA RAX,[RBP + 0x438]` |
| `0x43C` | `29` | `15` | `14003b33e` read-or-source: `MOV RCX,qword ptr [RSI + 0x43c0]`<br>`14003b356` write-or-destination: `MOV qword ptr [RSI + 0x43c0],RDI`<br>`14003b9e8` write-or-destination: `MOV qword ptr [RBX + 0x43c0],RBP`<br>`14003bec9` read-or-source: `MOV RCX,qword ptr [RBX + 0x43c0]` |
| `0x440` | `80` | `39` | `14003665e` read-or-source: `MOV RDX,qword ptr [RDI + 0x440]`<br>`1400367a4` read-or-source: `MOV RDX,qword ptr [RDI + 0x440]`<br>`14003e304` read-or-source: `MOV RBX,qword ptr [RSI + 0x440]`<br>`14003fd9a` write-or-destination: `MOV qword ptr [RDI + 0x440],RBX` |

## Interpretation

1. `0x30C/+0x310/+0x314` should not be dismissed as random: Ghidra found it written in the same owner-layout cluster as promoted coordinates.
2. The restart/relog zero-vector failure is therefore more likely a state/passive-reset issue than a simple wrong-offset issue.
3. `0x438/+0x43C/+0x440` remains worth investigating, but the first-pass offset search includes stack and larger-offset false positives, so it needs a refined decompiler/function pass before promotion scoring.
4. The analysis timed out after 300 seconds but saved the project and produced useful refs/hits; a longer/targeted Ghidra pass can improve function names and decompiler snippets.

## Safety boundary

No live RIFT input, movement, x64dbg, Cheat Engine, target-process memory read/write, provider write, current-truth update, or proof/actor/facing/turn-rate promotion was performed.
