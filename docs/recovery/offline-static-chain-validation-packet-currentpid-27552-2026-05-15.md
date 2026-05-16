# Offline static-chain validation packet — player coordinates

Generated UTC: `2026-05-15T08:53:06Z`
Status: **candidate-packets-ready-blocked-no-readback-source**

> **Update / supersession note:** Later offline overlap analysis in `docs/recovery/offline-static-chain-source-vs-destination-reclassification-currentpid-27552-2026-05-15.md` makes the source-cache packet the primary candidate and demotes the destination-owner packet to a negative control unless fresh readback proves otherwise.
Scope: **offline-only**. No live memory reads, no x64dbg attach/watchpoints, no Cheat Engine, no movement/input.

## Verdict

I converted the current best static-root lead into two machine-readable, candidate-only resolver packets. Both are intentionally blocked by the offline resolver because no approved current memory image/readback was supplied.

This is the right offline outcome: the packets are ready for a future read-only validation pass, but they do **not** promote movement truth or stable static-chain truth now.

## Candidate packets

| Candidate | Chain expression | Packet | Resolver result |
|---|---|---|---|
| Destination owner | `coordBase = deref(rift_x64.exe+0x32E1780)+0x320` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-validation-packet-currentpid-27552-20260515-085306\candidates\candidate-destination-owner.json` | resolver exit `2`; expected blocker `['no-readback-source']` |
| Source cache | `coordBase = deref(deref(rift_x64.exe+0x32E1780)+0x400)+0x48` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-validation-packet-currentpid-27552-20260515-085306\candidates\candidate-source-cache.json` | resolver exit `2`; expected blocker `['no-readback-source']` |

## Current expected values

| Item | Value |
|---|---|
| Current proof leaf | `0x27B1ED850C0` |
| Expected destination owner | `0x27B1ED84DA0` |
| Expected source-cache object | `0x27B1ED85078` |
| Module base from current-truth artifact | `0x7FF71CD90000` |
| Root slot current VA from artifact module base | `0x7FF720071780` |

## RIP-reference census for root/related slots

| Slot | RVA | Ref count | First references |
|---|---|---|---|
| Best root slot | `rift_x64.exe+0x32E1780` | `4` | `0x488464 mov rax, qword ptr [rip + 0x2e59315]`, `0x48848E mov rbx, qword ptr [rip + 0x2e592eb]`, `0x488520 mov qword ptr [rip + 0x2e59259], rbx`, `0x488537 mov qword ptr [rip + 0x2e59242], rbx` |
| Adjacent service slot | `rift_x64.exe+0x32E1788` | `4` | `0x488554 mov rax, qword ptr [rip + 0x2e5922d]`, `0x48857E mov rbx, qword ptr [rip + 0x2e59203]`, `0x488610 mov qword ptr [rip + 0x2e59171], rbx`, `0x488627 mov qword ptr [rip + 0x2e5915a], rbx` |
| Component manager slot | `rift_x64.exe+0x32E1848` | `4` | `0x492B94 mov rax, qword ptr [rip + 0x2e4ecad]`, `0x492BBE mov rbx, qword ptr [rip + 0x2e4ec83]`, `0x492C50 mov qword ptr [rip + 0x2e4ebf1], rbx`, `0x492C67 mov qword ptr [rip + 0x2e4ebda], rbx` |

Interpretation:

- `rift_x64.exe+0x32E1780` has a small, self-contained reference set in the lazy getter path, supporting it as a real module-relative singleton slot.
- `rift_x64.exe+0x32E1848` is the broader manager slot used to initialize owner `+0x3F8`, not the direct coordinate owner root.
- The packets intentionally separate the destination-owner hypothesis from the source-cache hypothesis so future validation can fail one without discarding the other.

## Future read-only validation use

If read-only current-process validation is later approved, use the packet files in this order:

1. Destination owner packet: `candidate-destination-owner.json`
2. Source cache packet: `candidate-source-cache.json`

The resolver must receive a real current module map plus real readback/memory image. Expected fast-path pass conditions:

| Candidate | Required proof |
|---|---|
| Destination owner | `qword [rift_x64.exe+0x32E1780] == 0x27B1ED84DA0` and floats at `0x27B1ED850C0/0x27B1ED850C4/0x27B1ED850C8` match fresh API-now XYZ. |
| Source cache | `qword [rift_x64.exe+0x32E1780] == owner`, `qword [owner+0x400] == 0x27B1ED85078`, and floats at `0x27B1ED850C0/0x27B1ED850C4/0x27B1ED850C8` match fresh API-now XYZ. |

## Safety/blockers

| # | Blocker |
|---:|---|
| 1 | Candidate packets intentionally have no live/offline memory image readback. |
| 2 | Resolver should block with `no-readback-source` until a future approved read-only memory image is supplied. |
| 3 | Static root lead must not be promoted before multi-pose and restart validation. |

## Generated artifacts

| Artifact | Path |
|---|---|
| `runDirectory` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-validation-packet-currentpid-27552-20260515-085306` |
| `summaryJson` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-validation-packet-currentpid-27552-20260515-085306\summary.json` |
| `summaryMarkdown` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-validation-packet-currentpid-27552-20260515-085306\summary.md` |
| `destinationCandidate` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-validation-packet-currentpid-27552-20260515-085306\candidates\candidate-destination-owner.json` |
| `sourceCandidate` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-validation-packet-currentpid-27552-20260515-085306\candidates\candidate-source-cache.json` |
| `moduleMap` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-validation-packet-currentpid-27552-20260515-085306\candidates\module-map-currentpid-27552.json` |
| `trackedMarkdown` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-validation-packet-currentpid-27552-2026-05-15.md` |
