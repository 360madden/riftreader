# Offline owner-signature analysis — player coordinate static-chain lead

Generated UTC: `2026-05-15T08:57:56Z`
Status: **owner-signature-assertions-ready-candidate-only**

> **Update / supersession note:** Later offline overlap analysis in `docs/recovery/offline-static-chain-source-vs-destination-reclassification-currentpid-27552-2026-05-15.md` shows the current proof leaf is more likely a source/accessor triplet than `owner+0x320`. Use these owner-signature assertions only after a future root-slot read yields the actual owner pointer; do not require owner `0x27B1ED84DA0` as the primary pass condition.
Scope: **offline-only**. No live memory reads, no x64dbg attach/watchpoints, no Cheat Engine, no movement/input. The installed `rift_x64.exe` file and existing repo artifacts were read only.

## Verdict

The `rift_x64.exe+0x32E1780` root lead now has a stronger offline validation signature. The constructor reached from the root getter (`0x488460 -> 0x52D6E0`) initializes a `0xF40` object with stable self-links, module-relative function/table pointers, and the same coordinate field neighborhood later used by the coordinate update routines.

This still does **not** promote a stable chain. It gives a future read-only validator a high-signal object-signature checklist so a wrong root pointer can be rejected before relying on XYZ floats.

## Current candidate context

| Field | Value |
|---|---|
| Root slot | `rift_x64.exe+0x32E1780` / current artifact VA `0x7FF720071780` |
| Expected owner | `0x27B1ED84DA0` |
| Expected coord fields | `owner+0x320/+0x324/+0x328` = `0x27B1ED850C0` / `0x27B1ED850C4` / `0x27B1ED850C8` |
| Source-cache alternative | `owner+0x400 -> 0x27B1ED85078` then `source+0x48 = 0x27B1ED850C0` |
| Latest ProofOnly | `passed-proof-only` at `2026-05-15T07:49:25.137137+00:00` |

## Constructor-derived object signature

| Assertion | Address to read later | Expected value | Static source |
|---|---|---|---|
| root-slot-points-to-owner | `0x7FF720071780` | `0x27B1ED84DA0` |  |
| owner-vtable-0 | `0x27B1ED84DA0` | `0x7FF71F3D5AF8` | 0x52D731..0x52D738 |
| owner-vtable-8 | `0x27B1ED84DA8` | `0x7FF71F3D5AE8` | 0x52D73E..0x52D749 |
| owner-self-10 | `0x27B1ED84DB0` | `0x27B1ED84DA0` | 0x52D71B |
| owner-fn-18 | `0x27B1ED84DB8` | `0x7FF71D2FBC50` | 0x52D74D..0x52D754 |
| owner-table-20 | `0x27B1ED84DC0` | `0x7FF71F3D1E58` | 0x52D71F..0x52D72D |
| owner-table-28 | `0x27B1ED84DC8` | `0x7FF71F3D1E48` | 0x52D758..0x52D766 |
| owner-self-30 | `0x27B1ED84DD0` | `0x27B1ED84DA0` | 0x52D79C |
| owner-fn-38 | `0x27B1ED84DD8` | `0x7FF71D2F7C60` | 0x52D75F..0x52D76A |
| owner-table-40 | `0x27B1ED84DE0` | `0x7FF71F3D1E58` | 0x52D71F..0x52D745 |
| owner-table-48 | `0x27B1ED84DE8` | `0x7FF71F3D1E48` | 0x52D758..0x52D780 |
| owner-self-50 | `0x27B1ED84DF0` | `0x27B1ED84DA0` | 0x52D7A0 |
| owner-fn-58 | `0x27B1ED84DF8` | `0x7FF71D2F7940` | 0x52D76E..0x52D775 |
| owner-table-60 | `0x27B1ED84E00` | `0x7FF71F3D1E58` | 0x52D71F..0x52D78F |
| owner-table-68 | `0x27B1ED84E08` | `0x7FF71F3D1E48` | 0x52D758..0x52D784 |
| owner-self-70 | `0x27B1ED84E10` | `0x27B1ED84DA0` | 0x52D7A4 |
| owner-fn-78 | `0x27B1ED84E18` | `0x7FF71D2F61E0` | 0x52D779..0x52D798 |
| owner-byte-2f8 | `0x27B1ED85098` | `0x1` | 0x52D726 |

## Coordinate/cache assertions

| Assertion | Type | Address to read later | Expected / comparison target |
|---|---|---|---|
| owner-coord-x | float-api-now-match | `0x27B1ED850C0` | `0x27B1ED850C0` |
| owner-coord-y | float-api-now-match | `0x27B1ED850C4` | `0x27B1ED850C4` |
| owner-coord-z | float-api-now-match | `0x27B1ED850C8` | `0x27B1ED850C8` |
| owner-selected-source-cache | qword-candidate | `0x27B1ED851A0` | `0x27B1ED85078` |

## Static constructor evidence

| RVA | Instruction pattern | Why useful |
|---|---|---|
| `0x52D71B` | `mov qword ptr [rcx + 0x10], rcx` | self pointer at owner+0x10 |
| `0x52D731..0x52D749` | writes `owner+0x0/+0x8` | primary object vtable/table values |
| `0x52D758..0x52D798` | writes `owner+0x28/+0x38/+0x48/+0x58/+0x68/+0x78` | repeated table/function-pointer family |
| `0x52D79C/0x52D7A0/0x52D7A4` | writes `owner+0x30/+0x50/+0x70 = owner` | strong self-link signature |
| `0x52D7B8..0x52D853` | initializes coord-neighborhood and registry/cache fields | same object contains `+0x300..+0x400` field family |

## How this improves future static-chain validation

| Before | After |
|---|---|
| Validate only `[root]+0x320` floats. | First validate root pointer plus object self-links/table pointers, then validate coord floats. |
| A copied coord triplet could look plausible. | A copied triplet is unlikely to also have the `0x52D6E0` owner-object signature. |
| Source-vs-destination ambiguity remained broad. | Destination-owner hypothesis now has a concrete owner object signature; source-cache remains separate at `owner+0x400 -> source+0x48`. |

## Why this is still not promoted

| # | Blocker |
|---|---|
| 1 | assertions are derived from offline static constructor analysis only |
| 2 | no current process memory was read to verify root slot or owner signature |
| 3 | coordinate fields remain candidate-only until API-now versus chain-now readback passes |

## Future read-only validation order

1. Read `qword [rift_x64.exe+0x32E1780]` and require `0x27B1ED84DA0` or a current-PID equivalent owner pointer.
2. Validate stable owner signature fields first, especially self-links `owner+0x10/+0x30/+0x50/+0x70` and module-relative table/function pointers.
3. Validate `owner+0x320/+0x324/+0x328` against fresh API-now XYZ.
4. If destination-owner fails but the owner signature passes, test source-cache path `owner+0x400 -> source+0x48/+0x4C/+0x50`.
5. Only after multi-pose and restart validation, promote into a stable resolver contract.

## Generated artifacts

| Artifact | Path |
|---|---|
| `summaryJson` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-owner-signature-currentpid-27552-20260515-085757\summary.json` |
| `summaryMarkdown` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-owner-signature-currentpid-27552-20260515-085757\summary.md` |
| `ownerSignatureAssertions` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-owner-signature-currentpid-27552-20260515-085757\owner-signature-assertions.json` |
| `trackedMarkdown` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-owner-signature-currentpid-27552-2026-05-15.md` |
