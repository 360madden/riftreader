# RiftReader Current Truth

_Last updated: 2026-05-14T02:20:17Z._

## Verdict

**Movement is blocked.** The live reference surface is repaired and usable for **read-only proof**, but the best coordinate lead is still **candidate-only**. Do not use any coordinate candidate for navigation or movement polling until a current proof anchor/static chain and same-target `ProofOnly` pass.

## Current target epoch

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Process start | `2026-05-13T16:17:56.208370Z` |
| Module base | `0x7FF71CD90000` |

## Live truth source

| Surface | Status | Notes |
|---|---|---|
| `ReaderBridge_RRAPICOORD1` | **current / usable for read-only proof** | Live `Inspect.Unit.Detail(player)`, `source=rift-api`, `savedVariablesUse=none`. |
| ChromaLink world-state | stale / not authoritative | Still unhealthy/stale in latest preflight. |
| SavedVariables | not live truth | Post-save snapshots only; never use as live movement truth. |

Key proof artifacts:

| Artifact | Result |
|---|---|
| `scripts/captures/coordinate-proof-preflight-20260514-020050-354005/summary.json` | Passed `ready-for-read-only-proof`; movement false. |
| `scripts/captures/rift-api-reference-currentpid-2928-20260514-020051.json` | Fresh RRAPICOORD reference `7402.0, 871.78, 3029.4199`. |
| `scripts/captures/rrapicoord-scan-diagnostics-20260514-020126-043153/summary.json` | `1` usable marker. |
| `scripts/captures/rrapicoord-addon-state-diagnostics-20260514-020130-043012/summary.json` | Addon installed and live marker observed. |

## Movement gate

| Gate | Status |
|---|---|
| Movement allowed | **No** |
| Reason | No current movement-grade proof anchor, no static pointer chain, no restart validation, and same-target `ProofOnly` has not passed. |
| Required before movement | Fresh API/runtime reference + current memory candidate agreement + current proof anchor/static chain + same-target `ProofOnly`. |

## Best current coordinate candidate

| Field | Value |
|---|---|
| Candidate | `family-snapshot-hit-000001` |
| Address | `0x268D1FA6120` |
| Candidate file | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-020258/family-import-candidates.json` |
| Readback | `scripts/captures/riftscan-proof-pose-20260514-020339/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-220346.json` |
| Evidence | `ReferenceMatchCount=8`, `StableDecodedCandidateCount=10`, max abs delta `0.00003173828122271516` |
| Truth status | **candidate-only, not movement proof** |

## Static-chain / pointer status

| Evidence | Result |
|---|---|
| `scripts/captures/pointer-family-scan-20260514-021700-380199/summary.json` | Capped read-only scan hit `max-total-targets-reached:40`; top target heap-only; `0` module/RIFT-module hits. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-021250-664397/summary.json` | `16` owner windows inspected; `0` module-RVA hints. |
| Static pointer chain | **not proven** |

## Explicitly stale / invalid

| Item | Why not current truth |
|---|---|
| PID `57656` / HWND `0x5417BC` proof-anchor cache | Old process epoch. |
| `0x268E113FED0` / `family-snapshot-hit-000002` | Failed new fresh-reference readback with `ReferenceMatchCount=0`. |
| SavedVariables coordinates | Post-save snapshots only, not live IPC. |
| Old RRAPICOORD references | Timestamped scoring references only after age budget expires. |

## Current blockers

- Movement-grade proof anchor missing.
- Static pointer chain not proven.
- Restart validation not done.
- Same-target `ProofOnly` not passing.
- ChromaLink world-state stale/unhealthy.

## Canonical files

| File | Purpose |
|---|---|
| `docs/recovery/current-truth.md` | This concise human dashboard. |
| `docs/recovery/current-truth.json` | Small machine-readable canonical truth. |
| `docs/recovery/historical/current-truth-full-2026-05-14-0216-before-trim.md` | Historical full chronology; stale/audit only. |
| `docs/handoffs/2026-05-14-0220-current-truth-dashboard-trim.md` | Latest dashboard-trim handoff. |

## Next best action

Run bounded read-only owner/static-chain investigation from `family-snapshot-hit-000001`; do **not** move, navigate, or promote until same-target `ProofOnly` or equivalent static-chain proof passes.
