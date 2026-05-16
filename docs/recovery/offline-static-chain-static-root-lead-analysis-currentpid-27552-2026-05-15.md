# Offline static-root lead analysis — player coordinate stable pointer chain

Generated UTC: `2026-05-15T08:48:13Z`
Status: **static-root-lead-only-not-validated**

> **Update / supersession note:** Later offline overlap analysis in `docs/recovery/offline-static-chain-source-vs-destination-reclassification-currentpid-27552-2026-05-15.md` demotes the simple destination-owner arithmetic (`coordLeaf = owner+0x320`, owner `0x27B1ED84DA0`) to a negative-control hypothesis. Keep `rift_x64.exe+0x32E1780` as a plausible owner/service root lead, but validate the source/cache path before relying on `root+0x320`.
Scope: **offline-only**. No live memory reads, no x64dbg attach/watchpoints, no Cheat Engine, no movement/input. The installed `rift_x64.exe` file and existing repo artifacts were read only.

## Verdict

A plausible restart-stable chain lead now exists, but it is **not validated**:

```text
rift_x64.exe+0x32E1780  ->  owner object candidate
owner+0x320/+0x324/+0x328 -> X/Y/Z
```

Why this is the best offline lead: `0x488460` is a lazy singleton getter backed by the module-relative slot `rift_x64.exe+0x32E1780`; several static call paths feed its returned object into the coordinate update routine `0x56D7E0`, which writes coordinates at `rdi+0x320/+0x324/+0x328`. The expected current owner would be `0x27B1ED84DA0` because the proven current leaf is `0x27B1ED850C0`.

This remains **candidate-only** until a future approved read-only validation proves that `[rift_x64.exe+0x32E1780] == 0x27B1ED84DA0` or that `[rift_x64.exe+0x32E1780] + 0x320/+0x324/+0x328` matches fresh API-now coordinates.

## Current proof anchor context

| Field | Value |
|---|---|
| Target | `rift_x64` PID `27552` / HWND `0x3411E2` |
| Current module base | `0x7FF71CD90000` |
| Coord leaf | `0x27B1ED850C0` |
| Read region / source offset | `0x27B1ED85080` / `0x40` |
| Latest ProofOnly | `passed-proof-only` at `2026-05-15T07:49:25.137137+00:00` |

## Best static-root lead

| Item | Value | Why it matters |
|---|---|---|
| Root slot | `rift_x64.exe+0x32E1780` | Lazy singleton returned by `0x488460`. |
| Current PID VA if module base unchanged | `0x7FF720071780` | Address to read in a future approved read-only validation; not read now. |
| Expected owner if destination-field hypothesis is correct | `0x27B1ED84DA0` | Because `coordLeaf - 0x320`. |
| Expected XYZ from owner | `owner+0x320/+0x324/+0x328` = `0x27B1ED850C0` / `0x27B1ED850C4` / `0x27B1ED850C8` | Matches the field offsets written by the coord update functions. |
| Read region relation | read region = owner `+0x2E0`; coord leaf = owner `+0x320` | Explains why scan evidence saw leaf at region `+0x40` while code uses object `+0x320`. |

## Related module-relative slots

| Getter | Slot | Offline meaning |
|---|---|---|
| `0x488460` | `rift_x64.exe+0x32E1780` | Allocates `0xF40` object, constructs via `0x52D6E0`, returns singleton; best static-root lead. |
| `0x488550` | `rift_x64.exe+0x32E1788` | Adjacent singleton, size `0xA8`; related service but not current coord owner lead. |
| `0x492B90` | `rift_x64.exe+0x32E1848` | Manager/service used to initialize owner `+0x3F8`; likely component registry, not owner root. |

## Direct-call evidence

| Evidence | Count | Details |
|---|---|---|
| `0x488460` direct callers | `3845` | Very broad singleton accessor; broadness prevents promotion by itself. |
| `0x56D7E0` direct callers | `14` | `0x547FD5`, `0x55F15B`, `0x55F29E`, `0x577BC0`, `0x577BDF`, `0x577C1F`, `0x577DA5`, `0x57A028`, `0x5A635D`, `0x5E53DA`, `0x5F8125`, `0x695911`, `0x715823`, `0x77C508` |
| `0x56D7E0` callers with recent `0x488460` | `5` | `0x5A635D`, `0x5F8125`, `0x695911`, `0x715823`, `0x77C508` |
| `0x579AD0` direct callers | `1` | `0x566551` |
| `0x566540` wrapper direct callers | `1` | `0xFB53C7` |

Interpretation: `0x488460` is too broad to be proof by itself, but the **specific** call paths that immediately feed its returned object into `0x56D7E0` make `rift_x64.exe+0x32E1780` the strongest offline static-root lead so far.

## Root getter `0x488460` evidence

| RVA | Instruction |
|---|---|
| `0x488464` | `mov rax, qword ptr [rip + 0x2e59315]`; rip->0x32E1780 |
| `0x48848E` | `mov rbx, qword ptr [rip + 0x2e592eb]`; rip->0x32E1780 |
| `0x488501` | `mov ecx, 0xf40` |
| `0x488518` | `call 0x14052d6e0` |
| `0x488520` | `mov qword ptr [rip + 0x2e59259], rbx`; rip->0x32E1780 |
| `0x488534` | `mov rax, rbx` |
| `0x488537` | `mov qword ptr [rip + 0x2e59242], rbx`; rip->0x32E1780 |

Key meaning:

- `0x488460` first reads `qword [rift_x64.exe+0x32E1780]`.
- If null, it allocates `0xF40` bytes and constructs the object via `0x52D6E0`.
- It stores the constructed pointer back to `rift_x64.exe+0x32E1780` and returns it in `rax`.

## Owner constructor field evidence

| RVA | Instruction |
|---|---|
| `0x52D7B8` | `mov dword ptr [rsi + 0x300], 0xbf800000` |
| `0x52D7C2` | `mov qword ptr [rsi + 0x304], r13` |
| `0x52D7C9` | `mov qword ptr [rsi + 0x30c], r13` |
| `0x52D7D0` | `mov dword ptr [rsi + 0x314], r13d` |
| `0x52D83E` | `mov qword ptr [rsi + 0x3f8], r13` |
| `0x52D845` | `mov qword ptr [rsi + 0x400], r13` |
| `0x52D84C` | `mov qword ptr [rsi + 0x318], rax` |
| `0x52D853` | `mov byte ptr [rsi + 0x32c], r13b` |
| `0x52D868` | `mov qword ptr [rsi + 0x360], r13` |

Constructor evidence supports that the singleton object has the same field neighborhood used by the coordinate update code: `+0x300`, `+0x304`, `+0x30C`, `+0x314`, `+0x318`, `+0x32C`, `+0x360`, `+0x3F8`, and `+0x400` all live inside the object allocated by `0x488460`.

## Coordinate update routine `0x56D7E0` evidence

| RVA | Instruction |
|---|---|
| `0x56D7F3` | `mov rdi, rcx` |
| `0x56D829` | `mov r14, qword ptr [rdi + 0x3f8]` |
| `0x56D83A` | `lea rsi, [r14 + 0x78]` |
| `0x56D849` | `mov rax, qword ptr [rsi]` |
| `0x56D84C` | `mov rbp, qword ptr [rax + rcx*8]` |
| `0x56D8FB` | `mov rcx, rbp` |
| `0x56D8FE` | `movss dword ptr [rdi + 0x300], xmm6` |
| `0x56D906` | `call 0x140687e80` |
| `0x56D90E` | `movss dword ptr [rdi + 0x304], xmm0` |
| `0x56D916` | `call 0x140687ef0` |
| `0x56D925` | `movss dword ptr [rdi + 0x308], xmm0` |
| `0x56D939` | `mov rcx, rbp` |
| `0x56D93C` | `call 0x140687f90` |
| `0x56D97A` | `mov rcx, rbp` |
| `0x56D97D` | `call 0x140687f90` |
| `0x56D98F` | `movsd xmm0, qword ptr [rax]` |
| `0x56D993` | `movsd qword ptr [rdi + 0x320], xmm0` |
| `0x56D99B` | `mov eax, dword ptr [rax + 8]` |
| `0x56D99E` | `mov dword ptr [rdi + 0x328], eax` |
| `0x56D9A4` | `mov byte ptr [rdi + 0x32c], r15b` |

Key meaning:

- `rdi = rcx`, so the function argument is the destination/owner object.
- `owner+0x3F8` is a component/registry pointer.
- A selected component/source object is resolved and fed through `0x687F90`.
- XYZ is copied into `owner+0x320/+0x324/+0x328`, and `owner+0x32C` is updated as sidecar/dirty state.

## Primary routine `0x579AD0` evidence

| RVA | Instruction |
|---|---|
| `0x579AE3` | `mov rdi, rcx` |
| `0x579AFA` | `lea r8, [rdi + 0x3f8]` |
| `0x579B04` | `lea rdx, [rdi + 0x360]` |
| `0x579B0B` | `call 0x14068fb70` |
| `0x579B54` | `mov rcx, rdi` |
| `0x579B7C` | `call 0x14053e710` |
| `0x579B9E` | `mov qword ptr [rsp + 0x28], rbx` |
| `0x579E29` | `mov r14, qword ptr [rsp + 0x28]` |
| `0x579F75` | `mov rcx, r14` |
| `0x579F78` | `call 0x140687f90` |
| `0x579F81` | `ucomiss xmm0, dword ptr [rdi + 0x320]` |
| `0x579F8F` | `ucomiss xmm0, dword ptr [rdi + 0x324]` |
| `0x579F9D` | `ucomiss xmm0, dword ptr [rdi + 0x328]` |
| `0x579FBC` | `call 0x140687f90` |
| `0x579FCD` | `movsd qword ptr [rdi + 0x320], xmm0` |
| `0x579FE3` | `mov dword ptr [rdi + 0x328], eax` |
| `0x57A025` | `mov rcx, rdi` |
| `0x57A028` | `call 0x14056d7e0` |

Key meaning:

- `0x579AD0` uses the same owner object convention: `rdi = rcx`.
- It compares the selected source triplet against `owner+0x320/+0x324/+0x328`.
- On mismatch or dirty-state path, it calls `0x56D7E0` with `rcx = rdi`.

## Selector/cache helper `0x53E710` evidence

| RVA | Instruction |
|---|---|
| `0x53E716` | `mov rax, qword ptr [rcx + 0x400]` |
| `0x53E733` | `cmp qword ptr [rcx + 0x3f8], rax` |
| `0x53E741` | `call 0x140492b90` |
| `0x53E749` | `lea r8, [rsi + 0x3f8]` |
| `0x53E753` | `lea rdx, [rsi + 0x360]` |
| `0x53E75A` | `call 0x14068fb70` |
| `0x53E76B` | `mov rdx, qword ptr [rsi + 0x3f8]` |
| `0x53E77C` | `movsxd rax, dword ptr [rip + 0x299934d]`; rip->0x2ED7AD0 |
| `0x53E78D` | `mov rax, qword ptr [rdx + 0x78]` |
| `0x53E791` | `mov rdi, qword ptr [rax + rcx*8]` |
| `0x53E795` | `mov qword ptr [rsi + 0x400], rdi` |

Key meaning:

- The owner has a cached selected component at `owner+0x400`.
- The owner also has a component/registry pointer at `owner+0x3F8` initialized through the `0x492B90` manager.
- If the current proof leaf is the **source** triplet, the useful validation check is whether `qword [owner+0x400] == 0x27B1ED85078` and then `[owner+0x400]+0x48` reaches `0x27B1ED850C0`.

## Candidate chain formulas to validate later

| Candidate | Formula | Expected current value if correct | Status |
|---|---|---|---|
| Destination owner static chain | `owner = qword [rift_x64.exe+0x32E1780]`; XYZ at `owner+0x320/+0x324/+0x328` | owner should be `0x27B1ED84DA0`; X should be `0x27B1ED850C0` | candidate-only |
| Source component cache chain | `owner = qword [rift_x64.exe+0x32E1780]`; `source = qword [owner+0x400]`; XYZ at `source+0x48/+0x4C/+0x50` | source should be `0x27B1ED85078`; X should be `0x27B1ED850C0` | candidate-only |
| Registry/source selector chain | `owner+0x3F8` registry plus selector offsets feeds `0x687F90` | owner `+0x3F8` address `0x27B1ED85198` should point at registry state | candidate-only |

## Why this is not promoted yet

| # | Blocker |
|---|---|
| 1 | offline analysis cannot read qword [rift_x64.exe+0x32E1780] for the current process |
| 2 | no current runtime proof yet that [rootSlot]+0x320 equals 0x27B1ED850C0 |
| 3 | source-vs-destination identity for the current proof leaf still requires a current access/readback classification |
| 4 | restart-stable promotion still requires restart validation plus API-now versus chain-now multi-pose agreement |

## Future validation packet, read-only if later approved

No live validation was run now. If a future turn approves read-only current-process validation, the minimal non-watchpoint checks are:

1. Read `qword [rift_x64.exe+0x32E1780]` for the current PID.
2. Check whether it equals owner candidate `0x27B1ED84DA0`.
3. Read floats at `owner+0x320/+0x324/+0x328` and compare with fresh API-now XYZ.
4. If that fails, read `qword [owner+0x400]` and check whether `source+0x48/+0x4C/+0x50` matches fresh API-now XYZ.
5. Only after multi-pose and restart validation, convert the successful candidate into a repo-owned resolver packet.

## Generated artifacts

| Artifact | Path |
|---|---|
| `summaryJson` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-static-root-lead-analysis-currentpid-27552-20260515-084830\summary.json` |
| `summaryMarkdown` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-static-root-lead-analysis-currentpid-27552-20260515-084830\summary.md` |
| `trackedMarkdown` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-static-root-lead-analysis-currentpid-27552-2026-05-15.md` |
