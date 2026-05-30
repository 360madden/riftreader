# Coordinate Validation

**What this covers:** Reading player coordinates from the promoted static resolver
and validating them against ground truth.

**When to use:** Whenever you need current player position — navigation loops,
waypoint checks, polling, or resolver health verification.

**Primary reference:** [`docs/recovery/coordinate-recovery-workflow.md`](../recovery/coordinate-recovery-workflow.md)
— the authoritative document. This file is a compact quick-reference.

## Quick reference

| Tier | What | Command | Speed |
|---|---|---|---|
| 1 | Instant chain readback | `python scripts/static_owner_coordinate_chain_readback.py --use-current-truth --json` | Milliseconds |
| 2 | Verified (API ground truth) | `/rap` + chain readback, compare deltas | 5–15s |
| 3 | Readiness gate (offline) | `python scripts/static_chain_promotion_readiness.py --json` | ~1s |
| 4 | RRAPICOORD repair | `repair_rrapicoord_addon_settings.py` → `/reloadui` | 15–30s |
| 5 | Full displacement re-proof | Movement + API + chain at multiple positions | 1–2 min |

## Promoted resolver

| Field | Value |
|---|---|
| Chain | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Root RVA | `0x32EBC80` |
| Survives restart | ✅ |
| Survives relog | ✅ |
| Validated | 2026-05-27, max delta 0.00477 vs RRAPICOORD API |

## Anti-patterns

| Don't | Use instead |
|---|---|
| `scan_current_pid_coordinate_family.py` (60–180s) | `--use-current-truth --json` (ms) |
| Old PID proof anchors (e.g., `0x23863A26E50`) | Module-RVA based resolver |
| Treat owner address as static | Re-deref `moduleBase + 0x32EBC80` each session |

## Decision tree

```
Need coordinates?
├─ Instant → static_owner_coordinate_chain_readback.py --use-current-truth --json
├─ Verified → /rap + chain readback, compare deltas ≤ 0.25
├─ Health check → static_chain_promotion_readiness.py --json
├─ /rap broken → rrapicoord_scan_diagnostics.py → repair → /reloadui → retry Tier 2
└─ Post-patch → Tier 5 displacement validation (movement + API + chain)
```
