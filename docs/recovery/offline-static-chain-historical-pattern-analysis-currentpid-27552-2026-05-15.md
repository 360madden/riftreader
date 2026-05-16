# Offline historical-pattern analysis — stable static pointer chain for player coordinates

Generated UTC: `2026-05-15T08:20:04Z`
Status: **blocked-no-stable-static-chain**
Scope: **offline-only**. No live memory reads, no x64dbg attach/watchpoints, no Cheat Engine, no movement/input. The only external file read was the local installed `rift_x64.exe` binary for read-only RVA byte verification.

## Verdict

No stable static pointer chain is derivable from existing artifacts. The current PID proof anchor is valid coordinate truth for the last validated process epoch, while historical x64dbg/static-code evidence supplies **lead patterns** only. The strongest reusable pattern is: derive owner/register/field offset from a current access event, then resolve to a module/RVA/static-owner root; do not promote heap-only or copy-helper paths.

## Current PID proof anchor recap

| Field | Value |
|---|---|
| Target | `rift_x64` PID `27552` / HWND `0x3411E2` |
| Coord leaf | `0x27B1ED850C0` |
| Read region / coord offset | `0x27B1ED85080` / `0x40` |
| Proof support count | `6` |
| Max abs proof delta | `0.008501171875195723` |
| Latest ProofOnly | `passed-proof-only` at `2026-05-15T07:49:25.137137+00:00` |

## Historical evidence timeline

| Date | PID/HWND | Evidence | Best lead | Static-chain value | Why not stable |
|---|---|---|---|---|---|
| 2026-05-12 | `63412 / 0xB70082` | approved x64dbg hardware-read access capture | 0x20005B30800 coordinate leaf; rdi/object 0x20005B304E0; fields +0x320/+0x324/+0x328 | rift_x64.exe access RVAs 0x579F88/0x579F96/0x579FA4/0x579FD5/0x579FE9 are code leads only | single pose; no module/static root pointer; stale after relog/restart |
| 2026-05-13 | `2928 / 0xC0994` | grouped family snapshots, read-only code/RVA checks, pointer-family scan | 0x268DF21ED30 offset-corrected candidate; 0x268DF21ED20 base-ish sibling; one heap ref 0x268D753AE40 | RVA 0x57C2A5 code window matched; [rcx+0x10] aligns 0x268DF21ED20 -> 0x268DF21ED30 | register value/root not captured; pointer scan found heap-only refs, module hits 0 |
| 2026-05-14 | `23496 / 0x2C1024` | manual x64dbg access-event ingest from hardware-write hit | 0x27236F46750 exact coordinate copy; VCRUNTIME140.dll+0x1121C writes [rax+0x08] | copy/write helper classification; not rift_x64.exe owner/source | single pose; stale PID; helper-module write path; no caller/static root |
| 2026-05-15 | `27552 / 0x3411E2` | current-PID family scan + six-pose ProofOnly-backed proof anchor | 0x27B1ED850C0 proven coordinate leaf; read region +0x40; region+0x68 -> 0x27B1EC75C50 parent/container lead | strong current-PID proof, no access instruction yet | no current-PID x64dbg access event; parent lead is same private heap family; no restart/static root |

## Installed binary RVA check

This is a read-only check against the local installed game binary, not a live process check. It confirms whether historical code lead windows still exist in the on-disk `rift_x64.exe` image.

| RVA | Section | First 16 bytes | SHA-256 of 96-byte window | Matches stored current bytes? |
|---|---|---|---|---|
| `0x579F88` | `.text` | `7520F30F1040040F2E87240300007512` | `45c0f9b800dabab62fa8b3e30870b4944237b70c92c53e63406c81993430008c` | `n/a` |
| `0x579F96` | `.text` | `7512F30F1040080F2E87280300000F84` | `6f5fcab6c82c7cd835f38acd8545d70ef3365e859e791379bedabfcaebc4272f` | `n/a` |
| `0x579FA4` | `.text` | `0F84B400000041B601488D9F2C030000` | `5af9c7e416c1f63a0a2385c648917240f5140c26df4bd12e9e9458f644ec1d60` | `n/a` |
| `0x579FD5` | `.text` | `8B40084488334C8BB424980000008987` | `18277541d41df55f3ea36cf4247bdb497a13c7509448b0cf2c9483b595c31475` | `n/a` |
| `0x579FE9` | `.text` | `753680BC24E800000000752C4C396C24` | `162b9f7cd932ffb93e5ef16a4df56900327bdd1805376cf45f9421dd1cdc9812` | `n/a` |
| `0x57C2A5` | `.text` | `488974241048897C241841564883EC20` | `1ff9622e0526ba980571cfeaabd0df8eb0b48dab7d6efaa01da745c2b84174a9` | `True` |
| `0x47D555` | `.text` | `F803722E8B87940000008B8F80000000` | `acc70800c800a7fd69ac778dfa7a36d4539a2a882080091f68fe182bc0ffa7af` | `True` |

### Relevant disassembly snippets from installed binary

#### `0x579F88`

| Address | Instruction |
|---|---|
| `0x140579f88` | `jne 0x140579faa` |
| `0x140579f8a` | `movss xmm0, dword ptr [rax + 4]` |
| `0x140579f8f` | `ucomiss xmm0, dword ptr [rdi + 0x324]` |
| `0x140579f96` | `jne 0x140579faa` |
| `0x140579f98` | `movss xmm0, dword ptr [rax + 8]` |
| `0x140579f9d` | `ucomiss xmm0, dword ptr [rdi + 0x328]` |
| `0x140579fa4` | `je 0x14057a05e` |
| `0x140579faa` | `mov r14b, 1` |
| `0x140579fad` | `lea rbx, [rdi + 0x32c]` |
| `0x140579fb4` | `xor sil, sil` |

#### `0x579F96`

| Address | Instruction |
|---|---|
| `0x140579f96` | `jne 0x140579faa` |
| `0x140579f98` | `movss xmm0, dword ptr [rax + 8]` |
| `0x140579f9d` | `ucomiss xmm0, dword ptr [rdi + 0x328]` |
| `0x140579fa4` | `je 0x14057a05e` |
| `0x140579faa` | `mov r14b, 1` |
| `0x140579fad` | `lea rbx, [rdi + 0x32c]` |
| `0x140579fb4` | `xor sil, sil` |
| `0x140579fb7` | `mov rcx, qword ptr [rsp + 0x28]` |
| `0x140579fbc` | `call 0x140687f90` |
| `0x140579fc1` | `cmp byte ptr [rsp + 0xe0], 0` |

#### `0x579FA4`

| Address | Instruction |
|---|---|
| `0x140579fa4` | `je 0x14057a05e` |
| `0x140579faa` | `mov r14b, 1` |
| `0x140579fad` | `lea rbx, [rdi + 0x32c]` |
| `0x140579fb4` | `xor sil, sil` |
| `0x140579fb7` | `mov rcx, qword ptr [rsp + 0x28]` |
| `0x140579fbc` | `call 0x140687f90` |
| `0x140579fc1` | `cmp byte ptr [rsp + 0xe0], 0` |
| `0x140579fc9` | `movsd xmm0, qword ptr [rax]` |
| `0x140579fcd` | `movsd qword ptr [rdi + 0x320], xmm0` |
| `0x140579fd5` | `mov eax, dword ptr [rax + 8]` |

#### `0x579FD5`

| Address | Instruction |
|---|---|
| `0x140579fd5` | `mov eax, dword ptr [rax + 8]` |
| `0x140579fd8` | `mov byte ptr [rbx], r14b` |
| `0x140579fdb` | `mov r14, qword ptr [rsp + 0x98]` |
| `0x140579fe3` | `mov dword ptr [rdi + 0x328], eax` |
| `0x140579fe9` | `jne 0x14057a021` |
| `0x140579feb` | `cmp byte ptr [rsp + 0xe8], 0` |
| `0x140579ff3` | `jne 0x14057a021` |
| `0x140579ff5` | `cmp qword ptr [rsp + 0x30], r13` |
| `0x140579ffa` | `jne 0x14057a021` |
| `0x140579ffc` | `cmp byte ptr [rsp + 0xd0], 0` |

#### `0x579FE9`

| Address | Instruction |
|---|---|
| `0x140579fe9` | `jne 0x14057a021` |
| `0x140579feb` | `cmp byte ptr [rsp + 0xe8], 0` |
| `0x140579ff3` | `jne 0x14057a021` |
| `0x140579ff5` | `cmp qword ptr [rsp + 0x30], r13` |
| `0x140579ffa` | `jne 0x14057a021` |
| `0x140579ffc` | `cmp byte ptr [rsp + 0xd0], 0` |
| `0x14057a004` | `jne 0x14057a021` |
| `0x14057a006` | `test r12b, r12b` |
| `0x14057a009` | `jne 0x14057a021` |
| `0x14057a00b` | `cmp byte ptr [rsp + 0x20], r12b` |

#### `0x57C2A5`

| Address | Instruction |
|---|---|
| `0x14057c2a5` | `mov qword ptr [rsp + 0x10], rsi` |
| `0x14057c2aa` | `mov qword ptr [rsp + 0x18], rdi` |
| `0x14057c2af` | `push r14` |
| `0x14057c2b1` | `sub rsp, 0x20` |
| `0x14057c2b5` | `cmp qword ptr [rcx + 0x10], 0` |
| `0x14057c2ba` | `lea rbx, [rcx + 0x10]` |
| `0x14057c2be` | `mov r14, r8` |
| `0x14057c2c1` | `mov rsi, rdx` |
| `0x14057c2c4` | `mov rdi, rcx` |
| `0x14057c2c7` | `jbe 0x14057c341` |

#### `0x47D555`

| Address | Instruction |
|---|---|
| `0x14047d555` | `clc` |
| `0x14047d556` | `add esi, dword ptr [rdx + 0x2e]` |
| `0x14047d559` | `mov eax, dword ptr [rdi + 0x94]` |
| `0x14047d55f` | `mov ecx, dword ptr [rdi + 0x80]` |
| `0x14047d565` | `movzx edx, byte ptr [rax + r9]` |
| `0x14047d56a` | `mov dword ptr [rdi + 0x70], edx` |
| `0x14047d56d` | `shl edx, cl` |
| `0x14047d56f` | `inc eax` |
| `0x14047d571` | `movzx eax, byte ptr [rax + r9]` |
| `0x14047d576` | `xor edx, eax` |

## Cross-attempt pattern conclusions

| # | Conclusion |
|---:|---|
| 1 | The fastest successful coordinate recovery lane is current-PID grouped family scanning plus displacement tracking and immediate ProofOnly, not static-chain discovery. |
| 2 | Static-chain discovery stalls whenever evidence is heap-only, same-pose-only, copy-helper-only, or missing an owner/source register path. |
| 3 | Code RVAs are more durable than heap addresses: current installed rift_x64.exe still contains the historical lead windows at 0x579F88, 0x57C2A5, and 0x47D555. This is a code-lead fact, not a current coord-chain proof. |
| 4 | Do not force one old field offset. Historical observations include object+0x320, candidate spacing +0x10, current read-region +0x40, and current parent lead +0x68. The next proof must derive the base register and field offset from a current access event. |
| 5 | The current parent lead 0x27B1EC75C50 is useful as a future reference/owner-table seed, but it is inside the same private heap family and has no static-root provenance. |

## What this means for the current PID `27552`

| Question | Offline answer |
|---|---|
| Can we build a static chain now? | No. Existing artifacts do not contain a current-PID access event or root chain. |
| Does historical `rdi + 0x320` prove the current object layout? | No. It is a high-value pattern to watch for, not a forced offset. Current proof has `readRegion+0x40`, and prior transformed candidates used `+0x10` spacing. |
| Is `0x27B1EC75C50` an owner? | Not proven. It is a stable qword in the current coord neighborhood and a future reference/owner-table seed only. |
| Are historical RVAs useful? | Yes as code leads. `0x579F88`, `0x57C2A5`, and `0x47D555` exist in the installed binary, but they do not resolve a current heap object by themselves. |
| What would convert this to static truth? | Current access instruction + base register + field offset + module/static root + resolver readback + displaced poses + restart validation + ProofOnly. |

## Current blockers

| # | Blocker |
|---:|---|
| 1 | `no current-PID instruction/access provenance for 0x27B1ED850C0` |
| 2 | `no module/RVA/static-owner root to current coord leaf or parent lead` |
| 3 | `current parent lead is heap/private-region only` |
| 4 | `historical rift_x64 code RVAs are code leads only and not a resolved current chain` |
| 5 | `no restart validation for any chain shape` |

## Future rules if live work is approved later

| # | Rule |
|---:|---|
| 1 | If staying offline, keep refining packets/reports only; do not invent a chain. |
| 2 | If live work is later approved, watch the current 12-byte leaf 0x27B1ED850C0..0x27B1ED850CB and capture the instruction + base register + field offset. |
| 3 | Prioritize rift_x64.exe read hits with a clear base register over VCRUNTIME/memcpy write helpers. |
| 4 | Score a hit higher if it lands near the historical coordinate-read RVA cluster 0x579F88..0x579FE9 or produces a coherent owner object with X/Y/Z lane offsets. |
| 5 | Reject promotion until a derivedChain has module/RVA/static-owner root, API-now vs chain-now, three displaced poses, restart validation, and same-target ProofOnly. |

## Source artifacts

| Name | Path |
|---|---|
| `currentProofPointer` | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| `currentProofAnchor` | `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json` |
| `currentOfflineAnalysis` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-analysis-currentpid-27552-2026-05-15.md` |
| `currentParentLeadAnalysis` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-parent-lead-analysis-currentpid-27552-2026-05-15.md` |
| `currentNextScanPlan` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-next-scan-plan-currentpid-27552-2026-05-15.md` |
| `may12Candidate` | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-live-coord-access-20260512-approval-02\ingest\x64dbg-coordinate-chain-candidate.json` |
| `may12PointerScan` | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-live-coord-access-20260512-approval-02\pointer-scan-owner-0x20005B304E0.json` |
| `may13StaticLead` | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-static-lead-packet-20260513-195348-651818\static-lead-work-packet.json` |
| `may13PointerScan` | `C:\RIFT MODDING\RiftReader\scripts\captures\pointer-family-scan-20260513-195912-166777\summary.json` |
| `may13RvaCheck` | `C:\RIFT MODDING\RiftReader\scripts\captures\historical-x64dbg-hit-rva-check-20260513-194042-075604\summary.json` |
| `may13RvaDisasm` | `C:\RIFT MODDING\RiftReader\scripts\captures\historical-x64dbg-hit-rva-disasm-20260513-194417-078605\summary.json` |
| `may14Candidate` | `C:\RIFT MODDING\RiftReader\scripts\captures\x64dbg-access-event-ingest-20260514-221947-655978\x64dbg-coordinate-chain-candidate.json` |
| `riftExeFile` | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |

## Generated artifacts

| Artifact | Path |
|---|---|
| `summaryJson` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-historical-pattern-analysis-currentpid-27552-20260515-082004\summary.json` |
| `summaryMarkdown` | `C:\RIFT MODDING\RiftReader\scripts\captures\offline-static-chain-historical-pattern-analysis-currentpid-27552-20260515-082004\summary.md` |
| `trackedMarkdown` | `C:\RIFT MODDING\RiftReader\docs\recovery\offline-static-chain-historical-pattern-analysis-currentpid-27552-2026-05-15.md` |
