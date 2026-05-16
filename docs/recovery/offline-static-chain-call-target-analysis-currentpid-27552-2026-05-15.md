# Offline call-target analysis — player coordinate static-chain leads

Generated UTC: `2026-05-15T08:35:36Z`
Status: **accessor-lead-only-no-static-chain**
Scope: **offline-only**. No live memory reads, no x64dbg attach/watchpoints, no Cheat Engine, no movement/input. The installed `rift_x64.exe` file was read from disk only.

## Verdict

The coordinate code lead is now sharper: `rift_x64.exe` RVA `0x687F90` is a tiny dynamic accessor that returns `rcx + 0x48`. The primary coordinate block at `0x579F75..0x579FE3` and the secondary block at `0x56D93C..0x56D99E` use that accessor to obtain a source XYZ triplet, then compare/copy into `rdi + 0x320/+0x324/+0x328`.

This improves the future watch-event classifier, but it still does **not** produce a stable static pointer chain. The current offline evidence stops at dynamic object/register roles; no module/global/static root reaches current proof leaf `0x27B1ED850C0`.

## Current proof anchor context

| Field | Value |
|---|---|
| Target | `rift_x64` PID `27552` / HWND `0x3411E2` |
| Coord leaf | `0x27B1ED850C0` |
| Read region / offset | `0x27B1ED85080` / `0x40` |
| Candidate | `api-family-hit-000001` |
| Support count | `6` |
| Latest ProofOnly | `passed-proof-only` at `2026-05-15T07:49:25.137137+00:00` |

## Accessor findings

| RVA | Observed code shape | Meaning |
|---|---|---|
| `0x687F90` | `call 0x1406891F0; lea rax,[rcx+0x48]; ret` | coordinate source accessor used by the 0x579F block; returns triplet pointer |
| `0x687F20` | `call 0x1406891F0; lea rax,[rcx+0x60]; ret` | neighbor accessor for a +0x60 vector/field family |
| `0x687E80` | `add rcx,0x60; ... call 0x141130A10` | nearby +0x60 transform helper; useful context but not the current coord leaf |

### `0x687F90` focused disassembly

| RVA | Instruction |
|---|---|
| `0x687F90` | `push rbx` |
| `0x687F92` | `sub rsp, 0x20` |
| `0x687F96` | `mov rbx, rcx` |
| `0x687F99` | `call 0x1406891f0` |
| `0x687F9E` | `lea rax, [rbx + 0x48]` |
| `0x687FA2` | `add rsp, 0x20` |
| `0x687FA6` | `pop rbx` |
| `0x687FA7` | `ret` |

Interpretation: when a future current-PID access event is inside the coordinate block immediately after this call, `rax` is not an independent root. It is the returned pointer `inputObject + 0x48`.

## Direct xref and coordinate-block implications

| Item | Value | Interpretation |
|---|---|---|
| Direct `call rel32` xrefs to `0x687F90` | `197` | High fan-out: accessor is common, so it is not a unique static root. |
| Coordinate-relevant xrefs present | `0x56D93C`, `0x56D97D`, `0x579F78`, `0x579FBC` | These are the important call sites to classify if a future access event hits the current leaf. |
| Primary coord update block | `0x579F75..0x579FE3` | Uses `r14` and `[rsp+0x28]` through `0x687F90`, then compares/copies into `rdi+0x320/+0x324/+0x328`. |
| Secondary coord copy block | `0x56D93C`, `0x56D97D`, `0x56D98F..0x56D99E` | Uses `rbp` through `0x687F90`, then copies XYZ into `rdi+0x320/+0x324/+0x328`. |

## Derived current-address formulas

These are **candidate-only arithmetic checks**. They are useful for classifying a later access event but are not proof by themselves.

| Hypothesis | Formula | Current-PID arithmetic |
|---|---|---|
| Source triplet via `0x687F90` | `rax = inputObject + 0x48`; XYZ at `rax/+4/+8` | If leaf is source X, input/source object would be `0x27B1ED85078`. |
| Destination/object field via `rdi` | XYZ at `rdi+0x320/+0x324/+0x328` | If leaf is destination X, owner/object would be `0x27B1ED84DA0`. |
| Current read region relation | leaf is read region `+0x40` | If the read region itself were source+0x48, source object would be `0x27B1ED85038`; candidate-only arithmetic. |
| Parent lead relation | `0x27B1EC75C50` -> leaf delta `0x10F470` | Does not align directly to `+0x48` or `+0x320`; still heap/container lead only. |

## Primary coordinate block details

| RVA | Instruction |
|---|---|
| `0x579F75` | `mov rcx, r14` |
| `0x579F78` | `call 0x140687f90` |
| `0x579F7D` | `movss xmm0, dword ptr [rax]` |
| `0x579F81` | `ucomiss xmm0, dword ptr [rdi + 0x320]` |
| `0x579F8A` | `movss xmm0, dword ptr [rax + 4]` |
| `0x579F8F` | `ucomiss xmm0, dword ptr [rdi + 0x324]` |
| `0x579F98` | `movss xmm0, dword ptr [rax + 8]` |
| `0x579F9D` | `ucomiss xmm0, dword ptr [rdi + 0x328]` |
| `0x579FAD` | `lea rbx, [rdi + 0x32c]` |
| `0x579FB7` | `mov rcx, qword ptr [rsp + 0x28]` |
| `0x579FBC` | `call 0x140687f90` |
| `0x579FC9` | `movsd xmm0, qword ptr [rax]` |
| `0x579FCD` | `movsd qword ptr [rdi + 0x320], xmm0` |
| `0x579FD5` | `mov eax, dword ptr [rax + 8]` |
| `0x579FE3` | `mov dword ptr [rdi + 0x328], eax` |

Key offline meaning:

- Source object 1: `r14`; source triplet pointer after call: `r14 + 0x48`.
- Source object 2: `[rsp+0x28]`; source triplet pointer after call: `[rsp+0x28] + 0x48`.
- Destination/object owner: `rdi` with XYZ fields at `+0x320/+0x324/+0x328` and sidecar/dirty byte at `+0x32C`.

## Secondary coordinate block details

The secondary block confirms the same destination field family through a separate call-site path:

| RVA | Instruction | Meaning |
|---|---|---|
| `0x56D939` | `mov rcx, rbp` | passes `rbp` as input object |
| `0x56D93C` | `call 0x140687f90` | resolves `rbp + 0x48` source pointer |
| `0x56D97A` | `mov rcx, rbp` | repeats source input object |
| `0x56D97D` | `call 0x140687f90` | resolves source pointer for copy |
| `0x56D98F` | `movsd xmm0, qword ptr [rax]` | source X/Y load |
| `0x56D993` | `movsd qword ptr [rdi + 0x320], xmm0` | destination X/Y store |
| `0x56D99B` | `mov eax, dword ptr [rax + 8]` | source Z load |
| `0x56D99E` | `mov dword ptr [rdi + 0x328], eax` | destination Z store |
| `0x56D9A4` | `mov byte ptr [rdi + 0x32c], r15b` | sidecar/dirty update |

## Future event classifier update

| Observed future access shape | Classification | Required capture fields |
|---|---|---|
| Future hit at `[rax]`, `[rax+4]`, or `[rax+8]` after `call 0x687F90` | source coord triplet | Record call site, input `rcx` object, resulting `rax`, and companion destination `rdi` if present. |
| Future hit at `[rdi+0x320/+0x324/+0x328]` | destination/object coord field | Owner/component base is `watchedAddress - fieldOffset`; expected register is `rdi`. |
| Future hit in `VCRUNTIME`, memcpy, or non-`rift_x64.exe` helper | copy-helper only | Do not promote; require caller/source path back into `rift_x64.exe` coordinate block. |
| Future hit at `0x56D9xx` or `0x579Fxx` current process RVA | strong code-shape match | Still requires multi-pose API-now versus chain-now and restart validation before movement use. |

## Why this is still not a stable pointer chain

| # | Blocker |
|---|---|
| 1 | no current-PID instruction/access event for 0x27B1ED850C0 under the offline-only boundary |
| 2 | 0x687F90 is a common dynamic accessor with 197 direct call xrefs, not a static root by itself |
| 3 | r14, [rsp+0x28], rbp, and rdi are dynamic in-function registers/locals in the observed coordinate blocks |
| 4 | no module/RVA global/static owner reaches the current proof leaf in available offline artifacts |

## Practical next offline-safe conclusion

The best current static-chain lead is no longer just "watch the current leaf". It is:

1. If live watch/read capture is later approved, watch the 12-byte current proof leaf window `0x27B1ED850C0..0x27B1ED850CB`.
2. Classify any `rift_x64.exe` hit against the two proven code windows:
   - source path: `0x687F90` caller where `rax = inputObject + 0x48`;
   - destination path: `rdi + 0x320/+0x324/+0x328`.
3. Only after a hit, attempt static-owner/root recovery from the captured `inputObject` or `rdi` owner; do **not** promote from code shape alone.

## Generated artifacts

| Artifact | Path |
|---|---|
| `summaryJson` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-call-target-analysis-currentpid-27552-20260515-083539\summary.json` |
| `summaryMarkdown` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-call-target-analysis-currentpid-27552-20260515-083539\summary.md` |
| `trackedMarkdown` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-call-target-analysis-currentpid-27552-2026-05-15.md` |
