# Offline static-code pattern analysis — player coordinate static-chain leads

Generated UTC: `2026-05-15T08:28:23Z`
Status: **code-leads-only-no-static-chain**
Scope: **offline-only**. No live memory reads, no x64dbg attach/watchpoints, no Cheat Engine, no movement/input. The installed `rift_x64.exe` file was read from disk only.

## Verdict

The installed binary contains a strong coordinate compare/copy/update code pattern around `rift_x64.exe` RVA `0x579F75..0x579FE3`. This is the best static-code lead so far, but it still does **not** resolve a stable static pointer chain. It identifies likely source/destination registers and field offsets to classify a future current-PID access event.

## Current proof anchor context

| Field | Value |
|---|---|
| Target | `rift_x64` PID `27552` / HWND `0x3411E2` |
| Coord leaf | `0x27B1ED850C0` |
| Read region / offset | `0x27B1ED85080` / `0x40` |
| Proof support count | `6` |
| Latest ProofOnly | `passed-proof-only` at `2026-05-15T07:49:25.137137+00:00` |

## Exact byte-pattern hits in installed `rift_x64.exe`

| Pattern | Semantic | Occurrences | RVA(s) | Static-chain meaning |
|---|---|---:|---|---|
| `compare-source-x-to-dest-x` | `movss xmm0,[rax]; ucomiss xmm0,[rdi+0x320]` | `1` | `0x579F7D` | compare source X against destination/object X |
| `compare-source-y-to-dest-y` | `movss xmm0,[rax+0x4]; ucomiss xmm0,[rdi+0x324]` | `1` | `0x579F8A` | compare source Y against destination/object Y |
| `compare-source-z-to-dest-z` | `movss xmm0,[rax+0x8]; ucomiss xmm0,[rdi+0x328]` | `1` | `0x579F98` | compare source Z against destination/object Z |
| `copy-source-xy-to-dest-xy` | `movsd xmm0,[rax]; movsd [rdi+0x320],xmm0` | `2` | `0x56D98F`, `0x579FC9` | copy source X/Y into destination/object X/Y |
| `secondary-contiguous-copy-source-z-to-dest-z` | `mov eax,[rax+0x8]; mov [rdi+0x328],eax` | `1` | `0x56D99B` | secondary similar contiguous Z-copy pattern; primary 0x579F block has separated load/store shown in focused disassembly |
| `dirty-flag-near-dest-triplet` | `lea rbx,[rdi+0x32c]` | `2` | `0x579FAD`, `0x57A061` | destination/object dirty flag or sidecar immediately after XYZ |

## Code block interpretation

| Item | Inference |
|---|---|
| Best static code lead | `rift_x64.exe RVA 0x579F75..0x579FE3 coordinate compare/copy/update block` |
| Source pointer register | `rax after call 0x140687F90` |
| Destination/object register | `rdi` |
| Destination XYZ offsets | `X +0x320`, `Y +0x324`, `Z +0x328`; sidecar/dirty at `+0x32C` |
| Source XYZ offsets | `X +0x0`, `Y +0x4`, `Z +0x8` |
| Caveat | This proves code shape only. It does not prove the current proof leaf is rdi+0x320 nor provide rdi/static-root for PID 27552. |

## Focused disassembly window

Only the most relevant portion is shown. Full machine-readable disassembly for the window is in the summary JSON.

| RVA | Instruction | Why it matters |
|---|---|---|
| `0x579F75` | `mov rcx, r14` | passes source handle/object to resolver/helper |
| `0x579F78` | `call 0x140687f90` | call returns source coord pointer in `rax` |
| `0x579F7D` | `movss xmm0, dword ptr [rax]` | source X load |
| `0x579F81` | `ucomiss xmm0, dword ptr [rdi + 0x320]` | compare source X to destination/object X |
| `0x579F8A` | `movss xmm0, dword ptr [rax + 4]` | source Y load |
| `0x579F8F` | `ucomiss xmm0, dword ptr [rdi + 0x324]` | compare source Y to destination/object Y |
| `0x579F98` | `movss xmm0, dword ptr [rax + 8]` | source Z load |
| `0x579F9D` | `ucomiss xmm0, dword ptr [rdi + 0x328]` | compare source Z to destination/object Z |
| `0x579FAD` | `lea rbx, [rdi + 0x32c]` | sidecar/dirty field is after destination XYZ |
| `0x579FBC` | `call 0x140687f90` | second resolver/helper call for copy/update source |
| `0x579FC9` | `movsd xmm0, qword ptr [rax]` | source X/Y copy load |
| `0x579FCD` | `movsd qword ptr [rdi + 0x320], xmm0` | destination/object X/Y store |
| `0x579FD5` | `mov eax, dword ptr [rax + 8]` | source Z copy load |
| `0x579FE3` | `mov dword ptr [rdi + 0x328], eax` | destination/object Z store |

## Future event classifier

This is the practical offline output: how to classify a future current-PID access event if live x64dbg/read capture is explicitly approved later.

| Hit shape | Classification | Base formula | Expected register | Why useful |
|---|---|---|---|---|
| `ucomiss xmm0, [rdi+0x320/+0x324/+0x328] or mov [rdi+0x320/+0x328], ...` | destination/object coord field | `ownerBase = watchedAddress - fieldOffset` | `rdi` | Would reproduce the May 12 owner/component pattern for the current PID if hit by 0x27B1ED850C0 watch. |
| `movss xmm0, [rax/+4/+8], movsd xmm0, [rax], or mov eax, [rax+8]` | source coord triplet returned by resolver/helper call | `sourceBase = watchedAddress - sourceFieldOffset; also record rdi destination object if present` | `rax for source, rdi for destination sidecar` | Would show whether current proof leaf is source truth feeding an owner object rather than the owner field itself. |
| `VCRUNTIME/memcpy helper write or non-rift module hit` | copy-helper only | `do not derive static owner without caller/source path` | `not sufficient` | Explains why May 14 write hit must stay candidate-only. |

## Blockers

| # | Blocker |
|---:|---|
| 1 | `static code pattern identifies a coordinate update/copy routine but not a root pointer to the current object` |
| 2 | `rdi is an in-function object register; offline binary analysis alone cannot recover its current heap value or static owner` |
| 3 | `current proof leaf 0x27B1ED850C0 has no current-PID access event, so source-vs-destination classification is unknown` |
| 4 | `no chain can be promoted without current API-now vs chain-now, multi-pose, restart validation, and ProofOnly` |

## Generated artifacts

| Artifact | Path |
|---|---|
| `summaryJson` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-code-pattern-analysis-currentpid-27552-20260515-082823\summary.json` |
| `summaryMarkdown` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-code-pattern-analysis-currentpid-27552-20260515-082823\summary.md` |
| `trackedMarkdown` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-code-pattern-analysis-currentpid-27552-2026-05-15.md` |
