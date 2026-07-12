# Anti-RE Resolution

Created: 2026-07-11
Scope: Research, tools, and strategies for resolving player coordinates past RIFT's dynamic memory allocation and engine-level protections.

## Purpose

This folder contains all anti-RE research, signature databases, analysis scripts,
and resolution strategies for reading player coordinate data from the RIFT client
process. It consolidates work that was previously scattered across
`docs/recovery/`, `scripts/`, `Assets/scripts/`, and `Research/`.

## Protection Profile

RIFT uses **no commercial anti-RE packer** (no Themida/VMProtect/Arxan). The
binary is a standard unpacked PE64. The challenges are:

1. **Dynamic memory allocation** — Gamebryo engine allocates game objects on the
   heap; addresses change every session
2. **Standard ASLR** — Base address randomized per launch
3. **High fan-out accessors** — 197+ code paths touch coordinate fields, making
   unique static root identification impossible via traditional pointer chains
4. **Server-side validation** — Cannot be bypassed from the client

## Strategy Layers

| Priority | Strategy | Update Resistance | Status |
|---|---|---|---|
| 1 | AOB signature scanning | High | Research phase |
| 2 | RTTI vtable scanning | High | Research phase |
| 3 | Code-pattern reacquisition (hook the writer) | Very high | Partial — x64dbg access events |
| 4 | String-reference anchoring | Very high | Not started |
| 5 | Memory graph / SIGPATH | Research-grade | Partial — RiftScan xref analysis |

## Folder Structure

```
docs/anti-re/
├── README.md                          ← you are here
├── protection-profile.md              ← RIFT's protection stack analysis
├── strategy.md                        ← ordered resolution strategies
├── analysis/
│   ├── modrm-access-inventory.md      ← all instructions accessing known offsets
│   ├── rtti-class-inventory.md        ← RTTI class names found in binary
│   ├── string-reference-map.md        ← strings near coordinate code paths
│   └── call-graph-analysis.md         ← call graph from coordinate access sites
├── signatures/
│   ├── coordinate-access-aobs.md      ← AOB patterns for coordinate accessors
│   ├── rip-relative-resolver.md       ← RIP-relative resolution methodology
│   └── <signature-database>.json      ← machine-readable signature files
├── scripts/                           ← (see scripts/anti-re/)
└── artifacts/                         ← (see artifacts/anti-re/)
```

## Quick Start

1. Read `protection-profile.md` to understand what we're up against
2. Read `strategy.md` for the ordered approach
3. Check `analysis/` for latest inventory results
4. Check `signatures/` for extracted AOB patterns
5. Run scripts from `scripts/anti-re/` to generate new analysis

## Cross-References

| Related doc | Relationship |
|---|---|
| `docs/recovery/hybrid-fast-reacquire-strategy.md` | Target architecture that anti-RE work supports |
| `docs/recovery/optimized-player-actor-coordinate-chain-workflow.md` | Provenance-first discovery process |
| `docs/recovery/static-coordinate-chain-10-phase-plan-2026-05-21.md` | 10-phase promotion plan |
| `Assets/scripts/modrm_scanner.py` | ModRM instruction scanner (finds access sites) |
| `Assets/scripts/extract_binary_signatures.py` | Signature extraction pipeline |
| `Assets/scripts/discover_secondary_structs.py` | VTable/RTTI discovery |
| `scripts/postupdate_static_access_chain.py` | Capstone-based call-graph tracer |
| `Research/rift_research/scanners.py` | AOBScanner, Vec3Scanner, PointerScanner |
