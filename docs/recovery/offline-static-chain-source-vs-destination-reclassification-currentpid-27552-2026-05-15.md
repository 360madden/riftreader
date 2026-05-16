# Offline source-vs-destination reclassification — player coordinate chain

Generated UTC: `2026-05-15T09:00:03Z`
Status: **source-triplet-primary-destination-owner-demoted**
Scope: **offline-only**. No live memory reads, no x64dbg attach/watchpoints, no Cheat Engine, no movement/input. This analysis uses only the installed `rift_x64.exe` static constructor evidence plus existing proof readback sample bytes.

## Verdict

The prior destination-owner arithmetic hypothesis (`coordLeaf = owner+0x320`, owner `0x27B1ED84DA0`) is now demoted to a **negative-control / low-priority** hypothesis for the current PID. Existing sampled bytes overlap the supposed owner object at offsets `+0x2E0..+0x36B`, and that overlap does **not** look like the object constructed by `0x52D6E0`.

The better current hypothesis is that the proven coord leaf `0x27B1ED850C0` is a **source/accessor triplet** returned by `0x687F90`, meaning:

```text
sourceObject = coordLeaf - 0x48 = 0x27B1ED85078
coord XYZ    = sourceObject+0x48/+0x4C/+0x50
read region  = sourceObject+0x8
```

`rift_x64.exe+0x32E1780` may still be the owner/service root, but the future chain should validate `root -> owner -> source/cache/selector -> source+0x48`, not assume `root+0x320` is the current proof leaf.

## Destination-owner overlap check

If `0x27B1ED850C0` were `owner+0x320`, then owner would be `0x27B1ED84DA0` and the existing proof sample at `0x27B1ED85080` would cover owner offsets `+0x2E0..+0x36B`. That lets us compare sampled bytes against fields initialized by the root-object constructor.

| Owner field | Address | Constructor/static expectation | Actual sampled value | Static source | Verdict |
|---|---|---|---|---|---|
| +0x2F8 | `0x27B1ED85098` | 0x1 constructor init | `0xD0` | 0x52D726 | sampled-mismatch-or-structural-contradiction |
| +0x300 | `0x27B1ED850A0` | 0xBF800000 / f32=-1.0 constructor init | `0xFFFF / f32=9.183409485952689e-41` | 0x52D7B8 | sampled-mismatch-or-structural-contradiction |
| +0x304 | `0x27B1ED850A4` | 0x0 constructor init | `0x0` | 0x52D7C2 | not-contradicting |
| +0x30C | `0x27B1ED850AC` | 0x0 constructor init | `0x0` | 0x52D7C9 | not-contradicting |
| +0x314 | `0x27B1ED850B4` | 0x0 constructor init | `0x0 / f32=0.0` | 0x52D7D0 | not-contradicting |
| +0x318 | `0x27B1ED850B8` | pointer/service value from 0x4A4360, expected pointer-like | `0x23` | 0x52D7D7/0x52D84C | sampled-mismatch-or-structural-contradiction |
| +0x32C | `0x27B1ED850CC` | 0x0 init / dirty byte likely 0 or 1 when live | `0x7B` | 0x52D853; 0x56D9A4; 0x579FAD | sampled-mismatch-or-structural-contradiction |
| +0x350 | `0x27B1ED850F0` | 0x0 constructor init | `0x1` | 0x52D85A | sampled-mismatch-or-structural-contradiction |
| +0x358 | `0x27B1ED850F8` | 0x0 constructor init | `0x3` | 0x52D861 | sampled-mismatch-or-structural-contradiction |
| +0x360 | `0x27B1ED85100` | 0x0 constructor init before registry setup | `0x1` | 0x52D868 | sampled-mismatch-or-structural-contradiction |

Interpretation: a few zero fields do not contradict the destination-owner hypothesis, but the combined mismatches around `+0x2F8`, `+0x300`, `+0x318`, `+0x32C`, `+0x350`, `+0x358`, and `+0x360` make `0x27B1ED84DA0` unlikely to be the `0x52D6E0` owner object.

## Source/accessor hypothesis now ranks first

| Item | Value | Why |
|---|---|---|
| Accessor function | `0x687F90` | returns `inputObject+0x48` |
| Source object if current leaf is accessor/source X | `0x27B1ED85078` | `coordLeaf - 0x48` |
| Existing proof read region relation | `0x27B1ED85080 = source+0x8` | The current captured sample covers source object neighborhood, not owner start. |
| Current XYZ under source hypothesis | `source+0x48/+0x4C/+0x50 = 0x27B1ED850C0/0x27B1ED850C4/0x27B1ED850C8` | Exactly matches the proven coord leaf triplet. |
| Stable sampled qword | `source+0x70 -> 0x27B1EC75C50` | This was the prior parent/container lead at read-region `+0x68`. |

## Updated static-chain search priority

| Rank | Candidate path | Status | Why |
|---:|---|---|---|
| 1 | `owner = qword [rift_x64.exe+0x32E1780]`; `source = qword [owner+0x400]` or selector-derived source; XYZ at `source+0x48/+0x4C/+0x50` | primary candidate | Fits `0x687F90` and current sample layout. |
| 2 | `sourceObject = 0x27B1ED85078`; find references/owners to that source object | offline seed only | Useful for a future read-only reference scan; not a root. |
| 3 | `coordBase = deref(rift_x64.exe+0x32E1780)+0x320` | demoted negative control | Existing overlap bytes do not resemble the constructed owner object. |

## What to change in future validation

1. Do **not** require `[rift_x64.exe+0x32E1780] == 0x27B1ED84DA0` as the primary pass condition.
2. First read root slot and validate the returned owner object's constructor signature.
3. Then validate source/cache path: `owner+0x400` and/or selector path should lead to source object `0x27B1ED85078` or another current source object whose `+0x48` triplet matches API-now.
4. Keep the destination-owner packet only as a negative control unless fresh access/readback proves otherwise.

## Blockers

| # | Blocker |
|---:|---|
| 1 | Source hypothesis still needs root-owner/source-cache readback before static-chain promotion. |
| 2 | Current root slot `0x32E1780` remains plausible as owner/service root, but expected owner cannot be derived as `coordLeaf-0x320`. |
| 3 | No live/API-now chain readback or restart validation was performed in this offline pass. |

## Generated artifacts

| Artifact | Path |
|---|---|
| `summaryJson` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-source-vs-destination-reclassification-currentpid-27552-20260515-090003\summary.json` |
| `summaryMarkdown` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-source-vs-destination-reclassification-currentpid-27552-20260515-090003\summary.md` |
| `trackedMarkdown` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-source-vs-destination-reclassification-currentpid-27552-2026-05-15.md` |
