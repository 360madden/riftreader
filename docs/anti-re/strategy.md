# Anti-RE Resolution Strategy

Created: 2026-07-11
Scope: Ordered strategies for resolving player coordinates past RIFT's dynamic memory allocation.

## Core Principle

**Don't chase data — chase code.** Data addresses change every session. Code
patterns (instructions, AOB signatures, RTTI class names) are stable across
updates. The optimal strategy finds stable code anchors and resolves dynamic
data from them.

## Strategy Ranking

### Strategy 1: AOB Signature Scanning (Recommended Primary)

**Concept:** Find unique byte sequences in the `.text` section that identify
instructions accessing coordinate fields. Scan at runtime to locate these
instructions, then resolve RIP-relative operands to find static globals.

**Why it works:**
- Code instructions are compiled into the binary and don't change between sessions
- Only the RIP-relative displacements (addresses) change — replace with wildcards
- The instruction mnemonic + operand pattern is unique enough to identify

**Workflow:**
```
1. Ghidra: find instruction accessing +0x320 (X coordinate)
2. Extract 8-16 bytes of surrounding instructions
3. Replace variable bytes (addresses) with ?? wildcards
4. Store as AOB pattern
5. At runtime: scan .text for pattern → found_addr
6. Read RIP-relative displacement at found_addr + offset
7. Resolve: target = found_addr + instruction_length + displacement
8. Result: stable static global address
```

**Existing tools:**
- `Assets/scripts/modrm_scanner.py` — finds all instructions accessing specific offsets
- `Assets/scripts/extract_binary_signatures.py` — signature extraction pipeline
- `Assets/scripts/signature_match.py` — validates signatures against binary
- `scripts/capture_root_signature.py` — AOB pattern capture with wildcards
- `Research/rift_research/scanners.py` — AOBScanner class
- `RiftReader/tools/reverse-engineering/downloads/reloaded.memory.sigscan.3.1.9.nupkg` — .NET sig scanner

**Gap:** No runtime AOB→RIP-relative resolver exists yet. Need a script that:
1. Takes an AOB pattern
2. Scans the game's `.text` section at runtime
3. For each match, reads the RIP-relative displacement
4. Outputs the resolved static global address

**Priority:** HIGH — most feasible, highest update resistance

---

### Strategy 2: RTTI VTable Scanning

**Concept:** RIFT uses MSVC C++ with RTTI. Class names (`.?AVPlayerActor@@`)
are stable across updates. Scan `.rdata` for RTTI structures, find the player
actor class, then scan writable memory for pointers to that vtable.

**Why it works:**
- RTTI class names are embedded in the binary by the compiler
- They don't change unless the class is renamed
- VTable layout is determined by the class definition, not the heap

**Workflow:**
```
1. Scan .rdata for ".?AV" RTTI strings
2. Parse CompleteObjectLocator → TypeDescriptor → class name
3. Find vtable pointer from RTTI
4. Scan writable memory (heap) for qwords matching vtable address
5. Each hit is an instance of that class
6. Read coordinate fields from instance + known offsets
```

**Existing tools:**
- `Assets/scripts/discover_secondary_structs.py` — vtable/RTTI candidate discovery
- `RiftReader/tools/reverse-engineering/ReClass.NET/` — structure mapping
- x64dbg-skills: no direct RTTI scanner, but `enum_imports.py` and `find_xrefs.py` help

**Gap:** Need a runtime RTTI instance scanner that:
1. Parses RTTI structures from the binary
2. Identifies player/actor-related classes
3. Scans heap memory for vtable pointers
4. Outputs live instance addresses

**Priority:** HIGH — very stable across updates

---

### Strategy 3: Code-Pattern Reacquisition (Hook the Writer)

**Concept:** Find the code instruction that **writes** the coordinate value.
Set a hardware breakpoint on the coordinate memory. When it fires, the register
context contains the object base. Walk the call stack upward to find a
module-global reference.

**Why it works:**
- The code that writes coordinates is stable (compiled into binary)
- Register context at the access point contains the live object pointer
- Call stack walk can trace back to a static root

**Workflow:**
```
1. Set hardware watchpoint on coordinate address (12-byte XYZ window)
2. Character moves → watchpoint fires
3. Examine RIP, RCX/RDI/R8 (object base registers)
4. Note instruction: e.g., movss [rdi+0x320], xmm0
5. RDI = object base → how was RDI loaded?
6. Walk backward in the function: lea rdi, [rax+0x6AC]
7. RAX = parent object → set watchpoint on RAX
8. Repeat until reaching a module-global: mov rax, [rip+disp]
9. Result: module + RVA = static root
```

**Existing tools:**
- `scripts/x64dbg_access_event_ingest.py` — normalizes access events
- `scripts/x64dbg_live_access_capture.py` — bounded live capture
- `scripts/x64dbg_static_chain_resolve.py` — offline chain resolution
- x64dbg hardware watchpoints (native)

**Gap:** Need an automated call-stack→static-root walker that:
1. Takes an x64dbg access event
2. Walks the saved return addresses on the stack
3. For each frame, checks if the function references a module-global
4. Outputs the first module-global found as the static root candidate

**Priority:** HIGH — directly solves the root problem

---

### Strategy 4: String-Reference Anchoring

**Concept:** Find unique strings near the coordinate code path (error messages,
debug output, format strings). Trace xrefs from the string to find the
containing function. Disassemble the function to find global variable references.

**Why it works:**
- Strings are compiled into the binary and rarely change
- They provide stable anchors in the code
- Xref tracing is deterministic

**Workflow:**
```
1. Search binary for strings near coordinate code:
   - "player", "position", "coordinate", "actor"
   - Error messages in the coordinate update path
   - Debug/format strings
2. Find xrefs to the string (Ghidra: References → references to)
3. For each xref, find the containing function
4. Disassemble the function
5. Look for RIP-relative global references: mov reg, [rip+disp]
6. The global is likely the container/manager holding player data
```

**Existing tools:**
- Ghidra headless — string extraction and xref tracing
- `kananlib` (not installed) — `find_function_with_string_reference`
- `scripts/postupdate_static_access_chain.py` — partial call-graph tracing

**Gap:** Need a string→xref→global resolution pipeline

**Priority:** MEDIUM — reliable but requires manual string discovery

---

### Strategy 5: Memory Graph / SIGPATH (Advanced)

**Concept:** Take memory snapshots during different game states (idle, moving,
different zones). Build memory access graphs. Diff between snapshots to find
stable paths through dynamic allocations.

**Why it works:**
- Finds relationships that static analysis misses
- Automated — no manual pattern discovery
- Can find deeply nested pointers

**Existing tools:**
- RiftScan `ByteDeltaAnalyzer` — byte-level change detection
- RiftScan `StructureClusterAnalyzer` — groups structures into clusters
- RiftScan `SessionXrefAnalysisService` — cross-reference analysis
- `x64dbg_snapshot_diff.py` — memory snapshot comparison

**Gap:** Need snapshot orchestration and automated path extraction

**Priority:** LOW — research-grade, high effort

---

## Implementation Roadmap

### Phase 1: Intelligence Gathering (Week 1)

| Task | Script | Output |
|---|---|---|
| Run ModRM scanner on current binary | `modrm_scanner.py --binary rift_x64.exe --offset 0x320,0x324,0x328,0x30C,0x304` | Complete list of instructions accessing coordinate fields |
| Run RTTI discovery | `discover_secondary_structs.py` on current binary | Class name inventory |
| Extract AOB patterns from ModRM results | New: `extract_aob_from_modrm.py` | AOB signature database |
| Test `0x32DD7E8` restart survival | Restart RIFT → `static_owner_coordinate_chain_readback.py` | Validates Layer 1 |

### Phase 2: Tool Building (Week 2)

| Task | Script | Output |
|---|---|---|
| Build RIP-relative resolver | New: `rip_relative_resolver.py` | AOB match → absolute global address |
| Build RTTI instance scanner | New: `rtti_instance_scanner.py` | Live player object instances |
| Build call-stack walker | New: `callstack_static_root_walker.py` | Access event → static root chain |

### Phase 3: Integration (Week 3)

| Task | Script | Output |
|---|---|---|
| Integrate AOB scanning into fast reacquire | Update `recover_current_pid_coord_anchor_fast.py` | AOB-based reacquisition lane |
| Integrate RTTI into candidate validation | New validation gate | RTTI-backed candidate scoring |
| Build string→xref pipeline | New: `string_xref_global_resolver.py` | Alternative root discovery |

### Phase 4: Validation (Ongoing)

| Task | Script | Output |
|---|---|---|
| Cross-validate all strategies against each other | New: `cross_validate_roots.py` | Confidence scoring |
| Update survival testing | Restart RIFT after patches | Proves update resistance |
| Promotion readiness with new strategies | Updated promotion gates | Multi-strategy proof |
