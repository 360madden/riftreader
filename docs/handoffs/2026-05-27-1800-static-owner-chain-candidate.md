# Static Owner Coordinate Chain Candidate — PID 12148

Generated: 2026-05-27T18:00:00Z

## Verdict

`current-session-static-module-root-owner-plus-0x320-coordinate-chain`

A practical current-session static pointer-chain candidate for player coordinates was found:

```text
[rift_x64 + 0x32EBC80] + 0x320/+0x324/+0x328
```

Current readback resolves:

```text
rift_x64 base       = 0x7FF77AF40000
root address        = 0x7FF77E22BC80
[root] owner        = 0x238679C06A0
owner + 0x320 xyz   = 7259.5908203125, 821.5345458984375, 2988.985107421875
proof anchor xyz    = 7259.5908203125, 821.5345458984375, 2988.985107421875
max delta           = 0.0
```

This matches the historical owner-shape template `owner+0x320/+0x324/+0x328` and is a stronger result than the proof/API buffer chain. It is **not promoted** yet because restart/relog validation and fresh API-now vs chain-now validation have not been completed.

## Related static proof/playerPosition chain

The debugger caller path also exposed a static proof registry chain:

```text
[[rift_x64 + 0x32FFB68] + 0x0] + 0x40 = 0x23863A26E50
```

That descriptor is named `playerPosition` and resolves to the current proof anchor. It is useful as proof-buffer/static registry evidence, but the owner chain above is the better static coordinate-chain candidate.

## Key artifacts

| Artifact | Result |
|---|---|
| [`C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-candidate-20260527-175818-641508\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-candidate-20260527-175818-641508\summary.json) | First current-session owner-chain candidate packet, passed |
| [`C:\RIFT MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-175915-451509\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\static-owner-coordinate-chain-readback-20260527-175915-451509\summary.json) | Reusable helper readback, passed |
| [`C:\RIFT MODDING\RiftReader\scripts\captures\static-playerposition-chain-readback-20260527-175518-427128\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\static-playerposition-chain-readback-20260527-175518-427128\summary.json) | Static `playerPosition` proof-chain readback, passed |
| [`C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-173911-546819\summary.json`](C:\RIFT%20MODDING\RiftReader\scripts\captures\x64dbg-live-access-capture-20260527-173911-546819\summary.json) | Original access-provenance hit that exposed the caller stack |

## Reusable commands

Read the owner-coordinate chain:

```powershell
python .\scripts\static_owner_coordinate_chain_readback.py --pid 12148 --hwnd 0x640C0C --module-base 0x7FF77AF40000 --expected-proof-anchor 0x23863A26E50 --json
```

Read the proof/playerPosition chain:

```powershell
python .\scripts\static_playerposition_chain_readback.py --pid 12148 --hwnd 0x640C0C --module-base 0x7FF77AF40000 --expected-anchor 0x23863A26E50 --json
```

## Evidence chain from debugger hit

The hardware watch on proof anchor `0x23863A26E50` hit in a CRT copy helper. Its stack led to these `rift_x64` callers:

| RVA | Meaning |
|---:|---|
| `0x0847513` | Copies upstream source coordinate into proof/playerPosition registry |
| `0x1138378` | Registry copy shim calls buffer helper |
| `0x116299F` | Buffer copy helper calls CRT/memcpy-like routine |

Static disassembly showed:

- `rift_x64+0x488EA0` returns the singleton rooted at `rift_x64+0x32EBC80`.
- That singleton is currently `0x238679C06A0`.
- The singleton has live coordinate floats at `+0x320/+0x324/+0x328`.
- Those floats match the proof anchor exactly in this session.

## Safety

| Field | Result |
|---|---:|
| Cheat Engine | false |
| DebugActiveProcessStop | false |
| Provider writes | false |
| Proof promotion | false |
| Actor-chain promotion | false |
| Git mutation | false |

## Remaining promotion gates

| Gate | Status |
|---|---|
| Current-session static chain readback | passed |
| Matches historical `owner+0x320` shape | passed |
| Fresh API-now vs chain-now | not run in this packet |
| Displacement-confirmed coordinate change | not confirmed; prior W attempts produced no visual frame change |
| Restart/relog validation | not run |
| Explicit promotion approval | not granted |

## Next best step

Run a fresh no-CE API-now vs chain-now validation for `[rift_x64+0x32EBC80]+0x320`. If it matches, the next promotion-quality test is restart/relog validation of the same RVA/offset chain.
