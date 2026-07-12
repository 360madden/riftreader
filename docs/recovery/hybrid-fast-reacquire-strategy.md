# Hybrid fast-reacquire coordinate strategy

Created: 2026-07-11
Updated: 2026-07-11 (anti-RE research integration)
Supersedes: pure static pointer chain assumption
Scope: realistic coordinate resolution strategy given RIFT's dynamic memory layout.

## Verdict

The **pure static pointer chain** (module RVA → owner → fixed offset) is
**not achievable** as the primary coordinate resolution method. The game's
dynamic memory layout, high-fan-out accessor patterns, and update-sensitive
structure invalidation make traditional static chains unreliable.

The realistic durable strategy is **fast reacquire + validate**: a layered
approach that uses a stable static global seed, fast current-PID candidate
discovery, and API-grounded validation each session.

## Evidence base

| PID epoch | Best candidate | Static root found? | Outcome |
|---|---|---|---|
| 60628 | `0x1FF08502BC8` | No — heap-only refs | candidate-only |
| 2928 | `0x268D1FA6120` | No — module hits 0 | candidate-only |
| 27552 | `0x27B1ED850C0` | No — same heap family | candidate-only |
| 67680 | `0x242E9932F70` | No — priority lane exhausted | candidate-only |
| 77152 | `[[rift_x64+0x32DD7E8]+0x80]+0x28` | No — container→dynamic child | candidate-only |

Every tested epoch produced heap-only candidate evidence. No epoch produced a
restart-stable module/RVA/static-owner resolver for the coordinate field.

Key findings:

- Accessor `rift_x64.exe+0x687F90` has **197 direct call xrefs** — too common
  to serve as a unique static root.
- Root-signature sweeps, family classifiers, and pointer-family scans
  consistently return heap-only/no-module-root results.
- The one previously promoted static root (`rift_x64+0x32EBC80`) went null
  after the 2026-06-02 update, proving update-sensitivity.
- Ghidra offline analysis of the updated binary captured **zero** old-root
  references.

## RIFT anti-RE protection profile

RIFT runs on a **heavily modified Gamebryo engine** (in-house 64-bit/multicore
modifications by Trion Worlds). The protection stack is lightweight client-side
with server-side validation:

```text
Layer 4: Server-side validation
  • Movement validation / teleport detection
  • Bot pattern detection
  • Coin Lock (geographic IP)

Layer 3: Client anti-cheat scanner (custom "Warden-like")
  • Process name scanning (user-mode)
  • DLL module scanning within game process
  • No kernel driver (unlike EAC/BattlEye)

Layer 2: Binary protections
  • Standard Windows ASLR (base address randomized per launch)
  • No confirmed packer (Themida/VMProtect/Arxan)
  • Encrypted network protocol

Layer 1: Engine-level (Gamebryo modified)
  • Heavy dynamic memory allocation (objects heap-resident)
  • Custom asset packaging (hash-named archives)
  • In-house 64-bit/multicore modifications
```

**Critical insight:** The binary is **not packed or obfuscated**. It can be
loaded into Ghidra/IDA without defeating a protector. The challenge is purely
the engine's dynamic memory allocation patterns — objects are heap-allocated
and their addresses change every session. Structure offsets within objects
(e.g., `+0x320` for coordinates) have historically remained stable across
patches, but the **root pointer** to the object changes.

## Why pure static chains fail — technical root cause

The Gamebryo engine uses a container/manager pattern:

1. A **static global** (module + RVA) points at a manager/container object
2. The container holds **pointers to dynamically allocated instances**
3. Instance addresses change every session (heap allocation)
4. The container's internal layout can change across updates
5. Multiple code paths (197+ call sites for the accessor) write to the same
   fields, making unique static-root identification impossible

This is not anti-RE protection in the traditional sense (no code
virtualization, no integrity checks on data structures). It is an architectural
property of the engine's memory management.

## Available tools in the local environment

| Tool | Location | Anti-RE bypass relevance |
|---|---|---|
| Ghidra 12.1 (headless + PyGhidra) | `C:\RIFT MODDING\Tools\ghidra_12.1_PUBLIC\` | Offline static analysis, xref tracing, decompilation, AOB extraction |
| x64dbg (full + headless + automate) | `C:\RIFT MODDING\Tools\x64dbg\release\` | Hardware watchpoints, instruction tracing, live debugging |
| Capstone disassembler | Used by `postupdate_static_access_chain.py` | Offline instruction analysis without Ghidra |
| ReClass.NET (x86/x64) | `RiftReader\tools\reverse-engineering\ReClass.NET\` | Memory structure modeling |
| Sysinternals (VMMap, ProcExp, ProcMon) | `C:\RIFT MODDING\Tools\SysinternalsSuite\` | Memory region classification, process analysis |
| Cheat Engine (Lua scripting) | `RiftReader\scripts\ce-*.lua`, `artifacts\cheat-engine\` | Float scanning, pointer scanning, memory snapshots |
| Reloaded.Memory.SigScan | `RiftReader\tools\reverse-engineering\downloads\` | .NET signature scanning library |
| YARA scanner | `x64dbg-skills\yara_scan.py` | Pattern-based binary classification |
| angr decompiler | `x64dbg-skills\decompile.py` | Automated decompilation without Ghidra |
| RiftScan pipeline | `C:\RIFT MODDING\Riftscan\` | Passive memory capture, cluster analysis, xref analysis |
| Research library | `C:\RIFT MODDING\Research\rift_research\` | Vec3Scanner, AOBScanner, PointerScanner, memory.py |

## Optimal strategy: ordered by priority

### Priority 1: AOB signature scanning (update-resistant)

Instead of chasing pointer chains through dynamic memory, scan for the **code
patterns** that access the coordinate data. These patterns survive updates
better than data pointers.

**Technique:** Find unique byte sequences in the `.text` section that access
known owner offsets. Replace variable bytes (RIP-relative displacements) with
wildcards. Scan at runtime to locate the access instructions, then resolve
RIP-relative operands to find static globals.

**Local tools:** `modrm_scanner.py` (already finds memory-access instructions
targeting specific offsets), `signature_match.py`, `extract_binary_signatures.py`,
`capture_root_signature.py`, Ghidra headless for signature extraction.

**What's missing:** A runtime AOB scanner that resolves RIP-relative operands
to find the static global addresses referenced by coordinate-accessing code.

### Priority 2: RTTI vtable-based object discovery

RIFT uses MSVC C++ with RTTI. Class names are stable across updates. Scan
`.rdata` for RTTI `CompleteObjectLocator` structures, find the player actor
class by name, then scan writable memory for pointers to that vtable.

**Local tools:** `discover_secondary_structs.py` (already finds vtable/RTTI
candidates), ReClass.NET for structure mapping.

**What's missing:** A runtime RTTI instance scanner that finds live player
object instances by vtable pointer.

### Priority 3: Code-pattern reacquisition (hook the writer, not the data)

The most update-resistant approach: find the code instruction that **writes**
the coordinate value, then intercept the live pointer from the register
context. Even if the object moves, the code that writes it is stable.

**Technique:** Hardware breakpoint on coordinate memory → when triggered,
examine register context → RCX/RDI/R8 contains the object base → set a
persistent watchpoint on the object base → build a stable read path.

**Local tools:** x64dbg hardware watchpoints, `x64dbg_access_event_ingest.py`
(normalizes access events into candidate packets), `x64dbg_live_access_capture.py`.

**What's missing:** An automated trace-to-static-root pipeline that walks
the call stack from an access event upward until it finds a module-global
reference.

### Priority 4: String-reference anchoring

Strings in the binary are very stable across updates. Find a unique string
near the coordinate code path (error messages, debug strings, format strings),
trace xrefs to find the containing function, then disassemble to find the
global variable that feeds into the coordinate calculation.

**Local tools:** Ghidra headless can extract string references.
`kananlib`-style `find_function_with_string_reference` is not yet implemented.

**What's missing:** A string → xref → function → global resolution pipeline.

### Priority 5: SIGPATH-style memory graph (advanced)

Take memory snapshots during different game states (idle, moving, different
zones), build memory access graphs, diff between snapshots to find stable
paths through dynamic allocations. This is research-grade but fully automated.

**Local tools:** RiftScan's `ByteDeltaAnalyzer`, `StructureClusterAnalyzer`,
`SessionXrefAnalysisService` already provide parts of this.

**What's missing:** Snapshot orchestration and automated path extraction.

## Architecture: three layers

```text
Layer 1: Static global seed
  │     Survives restart. Points at a container/manager object.
  │     Example: rift_x64+0x32DD7E8
  │     Purpose: fast anchor — avoids full memory scan.
  │
  ├──► Layer 2: Dynamic container child
  │       Heap-allocated. Layout is predictable within a session.
  │       Example: [seed]+0x80 → child, child+0x28/+0x2C/+0x30 = XYZ
  │       Purpose: actual coordinate storage.
  │
  └──► Layer 3: API validation gate
          Fresh API reference each session.
          Purpose: confirm candidate matches ground truth.
          Gate: ProofOnly pass required before any navigation use.
```

## Why this works where pure static chains fail

| Problem with pure static chains | How the hybrid handles it |
|---|---|
| Owner objects are heap-allocated, not at fixed offsets | Static global points at the container; container layout is stable even if the object inside moves |
| Accessor patterns have 100+ xrefs, not unique to player | We don't need a unique accessor — we need a stable global that points at the right container |
| Updates nullify promoted roots | Static globals survive updates more often than specific owner pointers; when they don't, the scan reacquire lane catches it |
| Full memory scans are slow (60–180s) | Static global seed narrows the search to a predictable container region |
| Heap addresses change every session | API validation proves the new session's candidate matches ground truth before use |

## Resolution formula

For the current best candidate:

```text
rift_x64+0x32DD7E8  (static global — survives restart)
  → [global]+0x80   (child pointer — dynamic, per-session)
    → child+0x28    (X coordinate)
    → child+0x2C    (Y coordinate)
    → child+0x30    (Z coordinate)
```

This is **not** a promoted static chain. It is a **candidate resolution path**
that must be validated against API ground truth each session before use.

## Session workflow

```text
1. Acquire target (PID/HWND/module base)
2. Read static global: [rift_x64+0x32DD7E8]
3. Walk container: [global]+0x80 → child
4. Read candidate XYZ: child+0x28/+0x2C/+0x30
5. Capture fresh API reference (ChromaLink or RRAPICOORD fallback)
6. Compare API-now vs candidate-now (per-axis deltas)
7. If delta < tolerance → candidate is session-valid
8. If delta > tolerance → candidate is stale, re-run fast scan
9. Navigation use only after ProofOnly pass
```

## What "reliable" means in this context

| Property | Pure static chain | Hybrid fast-reacquire |
|---|---|---|
| Restart survival | All-or-nothing (breaks on update) | **Layer 1** survives; Layers 2–3 revalidated |
| Speed | Fast (if chain is valid) | **Fast** — global read + container walk, no full scan |
| Update resilience | Breaks completely | **Degrades gracefully** — scan reacquire fills the gap |
| Confidence | High (if promoted) | **High after validation** — API proof every session |
| Maintenance | High (re-promote after every update) | **Lower** — only the global seed needs re-proof after updates |

## Failure modes and fallbacks

| Failure | Detection | Fallback |
|---|---|---|
| Static global goes null (update) | `[seed] == 0x0` | Fall back to full current-PID candidate scan |
| Container child pointer invalid | Readback fails or delta exceeds tolerance | Re-run fast reacquire from global seed |
| API reference unavailable | ChromaLink disconnected, RRAPICOORD stale | Block navigation; do not promote candidate |
| Candidate matches API but fails displacement | ProofOnly rejects | Candidate-only; do not navigate |
| Update changes container layout | Offset mismatch against API | Re-discover child offsets via static field matrix |

## Relationship to existing workflows

| Existing doc | How it relates |
|---|---|
| `optimized-player-actor-coordinate-chain-workflow.md` | Still valid for the provenance-first discovery process; this doc defines the **target architecture** that process should aim for |
| `static-coordinate-chain-10-phase-plan-2026-05-21.md` | Phase 1–4 (target lock → candidate → owner layout) still applies; Phase 8–10 (resolver → validation → promotion) should target the hybrid architecture, not a pure static chain |
| `post-update-pointer-chain-recovery-plan-2026-06-02.md` | This doc is the strategic context for that recovery plan; `rift_x64+0x32DD7E8` is the current best static global seed |
| `current-pid-coordinate-family-recovery-policy.md` | The fast reacquire lane is the primary reacquisition method; full family scans are the fallback |

## What to prove next

| # | Proof needed | Why |
|---|---|---|
| 1 | `rift_x64+0x32DD7E8` survives a RIFT restart/relog | Confirms Layer 1 is a durable static global |
| 2 | Container child layout (`+0x80`, `+0x28/+0x2C/+0x30`) is consistent across sessions | Confirms Layer 2 is predictable |
| 3 | Fast reacquire from global seed takes < 5 seconds | Confirms performance target |
| 4 | API-now vs candidate-now delta stays within tolerance across poses | Confirms Layer 3 validation works |
| 5 | Full workflow (acquire → read → validate → ProofOnly) completes without manual intervention | Confirms end-to-end reliability |

## Do not do

- Do not claim a static pointer chain is promoted until all five proofs above pass.
- Do not use candidate coordinates for navigation without ProofOnly pass.
- Do not assume container offsets are fixed across RIFT updates — re-verify after every update.
- Do not fall back to full memory scans when the global seed is valid — that wastes time.
- Do not skip API validation because "the readback looked stable." Stability is not proof.

## Immediate action plan (ordered by impact and feasibility)

| # | Action | Tool(s) | Effort | Impact |
|---|---|---|---|---|
| 1 | **Build AOB signature set** for the coordinate-accessing code paths around `0x3F8B0`, `0xC38390`, `0x687F90`. Use Ghidra to extract unique byte patterns with RIP-relative wildcards. Store as a reusable signature database. | Ghidra headless + `extract_binary_signatures.py` | Medium | High — signatures survive updates |
| 2 | **Run `modrm_scanner.py`** against the current `rift_x64.exe` to find every instruction that accesses `+0x320`, `+0x324`, `+0x328`, `+0x30C`, `+0x304`. This produces the complete set of coordinate-accessing instructions for AOB creation. | `modrm_scanner.py` | Low | High — maps all access sites |
| 3 | **Build a RIP-relative resolver** that takes an AOB match address and resolves `[rip+disp32]` operands to absolute global addresses. This converts code-pattern matches into static global pointers. | New script (Python/Capstone) | Medium | High — bridges code→data |
| 4 | **Run RTTI scan** on `rift_x64.exe` to enumerate all class names. Search for player/actor/entity-related class names. Build a vtable→instance scanner. | `discover_secondary_structs.py` + new RTTI parser | Medium | High — stable class names |
| 5 | **Build an automated call-stack walker** for x64dbg access events: when a hardware watchpoint fires on the coordinate field, walk the stack upward to find the first module-global reference. This converts a dynamic access into a static chain. | x64dbg trace + new Python script | High | Very high — solves the root problem |
| 6 | **Test `rift_x64+0x32DD7E8` restart survival.** This is the current best static global seed. If it survives restart, it becomes the foundation of the hybrid strategy. | `static_owner_coordinate_chain_readback.py` after restart | Low | High — validates Layer 1 |
| 7 | **Build a string→xref→global pipeline.** Scan the binary for unique strings near coordinate code paths, trace xrefs to find containing functions, extract global references from those functions. | Ghidra headless + new script | Medium | Medium — alternative root discovery |
