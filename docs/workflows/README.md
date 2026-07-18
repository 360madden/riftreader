# Workflows — Master Index

This directory replaces the fragmented `docs/recovery/` and `docs/handoffs/`
approach. Every common task has a **single entry point** with a clear
step-by-step workflow and a "what to do if it breaks" section.

**⚡ Quick decision tree:**

```
What do you need?
├─ I just logged in / started RIFT
│   → session-startup.md
│
├─ Game updated, my pointer chains are broken
│   → pointer-chain-reacquisition.md
│
├─ I need player coordinates right now
│   → coordinate-validation.md (Tier 1)
│
├─ I need validated coordinates (with API ground truth)
│   → coordinate-validation.md (Tier 2)
│
├─ Is my resolver still healthy?
│   → coordinate-validation.md (Tier 3)
│
├─ RRAPICOORD marker is broken/missing
│   → coordinate-validation.md (Tier 4)
│
├─ I want to capture AOB signatures for fast reacquisition
│   → aob-signature-capture.md
│
├─ I want to understand the owner object layout
│   → owner-layout-reference.md
│
├─ I want to build a combat bot
│   → combat-bot-roadmap.md
│
├─ I need to validate a new pointer chain
│   → pointer-chain-validation.md
│
├─ I need to do live navigation / route execution
│   → navigation-route.md
│
├─ I need the full memory/data checklist for auto-travel, navmesh, FOV, Godot overlay
│   → automated-travel-memory-data-catalog.md
│
├─ Game updated / root null — trimmed recovery playbook for next patch
│   → optimized-post-update-recovery-workflow.md
│
└─ What did we finish on 2026-07-18? (root promote + C2M multi-WP)
    → ../recovery/progress-2026-07-18-post-patch-root-and-c2m.md
```

## Document index

| Document | What it covers | When to use |
|---|---|---|
| [session-startup.md](session-startup.md) | Target resolution, module base check, resolver health, freshness gates | **Every session** — first thing after logging in |
| [../recovery/progress-2026-07-18-post-patch-root-and-c2m.md](../recovery/progress-2026-07-18-post-patch-root-and-c2m.md) | Durable milestone: root `0x32E07C0`, gates, C2M, decisions, next | **Resume after 2026-07-18** / handoff |
| [../recovery/current-truth.md](../recovery/current-truth.md) | Live promoted chain + binding rules | Every live session |
| [optimized-post-update-recovery-workflow.md](optimized-post-update-recovery-workflow.md) | Trimmed lane-split recovery (session seed vs static promote) | **Next client update** / root-null / PID drift |
| [pointer-chain-reacquisition.md](pointer-chain-reacquisition.md) | AOB signature scan, pointer family scan, neighborhood inspector, re-validation | Game update breaks chains |
| [coordinate-validation.md](coordinate-validation.md) | Tier 1-5 coordinate readback and validation | Need coordinates or resolver health check |
| [aob-signature-capture.md](aob-signature-capture.md) | Capturing, storing, and validating AOB signatures | Want faster reacquisition after updates |
| [owner-layout-reference.md](owner-layout-reference.md) | Canonical owner object offsets, layout, behavioral notes | Understanding what fields exist |
| [automated-travel-memory-data-catalog.md](automated-travel-memory-data-catalog.md) | Full pose/camera/FOV/W2S/navmesh/Godot data inventory for automated travel | Building overlays, click-to-move, navmesh apps, travel bots |
| [combat-bot-roadmap.md](combat-bot-roadmap.md) | Full Phase 0-6 plan for automated combat | Planning combat bot development |
| [pointer-chain-validation.md](pointer-chain-validation.md) | Promotion gates, displacement validation, reboot survival | Validating a new candidate chain |
| [navigation-route.md](navigation-route.md) | Route planning, turn-aware routing, route execution | Live navigation / waypoint following |

## Stale docs — what was replaced

The new structured docs replace these fragmented sources:

| Old approach | Replaced by |
|---|---|
| `docs/recovery/README.md` (400+ lines, 14 file references) | This index + decision tree |
| `docs/handoffs/` (40+ chronological files) | Per-workflow docs with decision trees |
| `docs/recovery/rebuild-runbook.md` (references stale PowerShell scripts) | `pointer-chain-reacquisition.md` |
| `docs/recovery/coordinate-recovery-workflow.md` (well-written, preserved as reference) | `coordinate-validation.md` (links to it) |
| Scattered owner layout notes across handoffs | `owner-layout-reference.md` |

## Key invariants (don't break these)

1. **Module base freshness** — always verify live module base matches `current-truth.json` before any memory read
2. **Facing target zero-vector** — block on `(0,0,0)` at 0x30C (fresh zone-in or stale base)
3. **API-now vs memory-now** — every coordinate claim needs fresh comparison
4. **No CE/SavedVariables as live truth** — use promoted static resolver or RRAPICOORD API
5. **Fail closed** — every gate blocks by default; explicit approval required to proceed

## Signature registry

Captured AOB signatures live in `../signatures/rift_x64/`. See [aob-signature-capture.md](aob-signature-capture.md).
