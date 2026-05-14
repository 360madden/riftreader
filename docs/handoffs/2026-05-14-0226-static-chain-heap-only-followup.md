# Static-chain heap-only follow-up handoff

_Last updated: 2026-05-14 02:26 UTC._

## Verdict

The current best coordinate candidate remains `family-snapshot-hit-000001` at `0x268D1FA6120`, but bounded pointer/owner follow-up is still heap-only. No module/RIFT-module static root or module-RVA hint was found. Movement remains blocked.

## Evidence

| Artifact | Result |
|---|---|
| `scripts/captures/pointer-family-scan-20260514-021700-380199/summary.json` | Capped depth scan stopped safely at `max-total-targets-reached:40`; top target heap-only; `0` module/RIFT-module hits. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-022426-567809/summary.json` | `24` owner windows inspected; `0` module-RVA hints. |
| `scripts/captures/root-signature-batch-sweep-currentpid-2928-20260514-022439-156492/summary.json` | Blocked as expected: no module-RVA hints to sweep. |
| `docs/recovery/current-truth.json` | Validator passes and now points at the latest heap-only evidence. |

## Current truth

| Item | Status |
|---|---|
| Live reference | `ReaderBridge_RRAPICOORD1`, usable for read-only proof |
| Best candidate | `family-snapshot-hit-000001` / `0x268D1FA6120` |
| Static chain | Not proven |
| Movement | Blocked |

## Next recommendation

Do **not** repeat the same module-hint sweep path for this owner batch. Next useful evidence needs a different source: bounded access-chain tracing, restart validation, or a fresh multi-pose family snapshot when safe. Keep all steps read-only/no-movement unless the movement gate is proven.
