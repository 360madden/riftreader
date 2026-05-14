# RiftReader Current Truth

_Last updated: 2026-05-14T02:48:05Z._

## Verdict

**Movement is blocked.** The live reference surface is repaired and the newest broad family snapshot produced a **stable current readback candidate**, but it is still **candidate-only**. Do not use it for navigation or movement polling until a current proof anchor/static chain and same-target `ProofOnly` pass.

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
| `scripts/captures/riftscan-proof-pose-20260514-024510/pose-api-reference.json` | Latest checked RRAPICOORD reference `7403.3999, 871.77, 3029.4099`. |
| `scripts/captures/rrapicoord-scan-diagnostics-20260514-020126-043153/summary.json` | `1` usable marker. |
| `scripts/captures/rrapicoord-addon-state-diagnostics-20260514-020130-043012/summary.json` | Addon installed and live marker observed. |

## Movement gate

| Gate | Status |
|---|---|
| Movement allowed | **No** |
| Reason | Candidate is read-only evidence only; no movement-grade proof anchor, no static pointer chain, no restart validation, and same-target `ProofOnly` has not passed. |
| Required before movement | Fresh API/runtime reference + current memory candidate agreement + current proof anchor/static chain + same-target `ProofOnly`. |

## Best current coordinate candidate

| Field | Value |
|---|---|
| Candidate | `family-snapshot-hit-000003` |
| Address | `0x268D506BC50` |
| Candidate file | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/family-import-candidates.json` |
| Readback | `scripts/captures/riftscan-proof-pose-20260514-024510/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-224524.json` |
| Evidence | `ReferenceMatchCount=7`, `StableDecodedCandidateCount=5`, max abs delta `4.960937758369255e-07`. |
| Truth status | **candidate-only, not movement proof** |
| Selection note | Rank-1 `family-snapshot-hit-000002` matched reference but was unstable across samples; coordination now prefers stable reference matches. |

## Latest coordinate reacquisition evidence

| Step | Artifact | Result |
|---|---|---|
| Fresh broad family snapshot | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/family-snapshot-summary.json` | Read-only scan captured `47,193` triplets / `12` near-reference triplets over `363,360,256` bytes. |
| Post-scan reference guard | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/post-scan-reference/fresh-reference-coordinate.json` | Passed: pre/post RRAPICOORD stable with max abs drift `0.0`. |
| Proof-pose readback | `scripts/captures/riftscan-proof-pose-20260514-024510/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-224524.json` | `ReferenceMatchCount=7`; stable selected candidate `family-snapshot-hit-000003` at `0x268D506BC50`. |
| Milestone strategy gate | `scripts/captures/riftscan-milestone-review-20260514-024659.json` | Ready for more read-only proof; movement still not allowed. |
| Prior stale guard smoke test | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-023611/family-snapshot-summary.json` | Correctly blocked stale snapshot use with `reference-drift-during-snapshot:1.3999>0.25`. |

## Static-chain / pointer status

| Evidence | Result |
|---|---|
| `scripts/captures/pointer-family-scan-20260514-021700-380199/summary.json` | Capped read-only scan hit `max-total-targets-reached:40`; top target heap-only; `0` module/RIFT-module hits. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-022426-567809/summary.json` | `24` owner windows inspected; `0` module-RVA hints. |
| `scripts/captures/root-signature-batch-sweep-currentpid-2928-20260514-022439-156492/summary.json` | Blocked as expected: no module-RVA hints to sweep. |
| Static pointer chain | **not proven** |

## Explicitly stale / invalid

| Item | Why not current truth |
|---|---|
| PID `57656` / HWND `0x5417BC` proof-anchor cache | Old process epoch. |
| `0x268D1FA6120` / old `family-snapshot-hit-000001` | Repeat readback returned `ReferenceMatchCount=0` and decoded near-zero floats. |
| `0x268D1EF0870` / prior start-reference snapshot candidate | Matched only an older snapshot start reference; failed later current-reference readback after drift. |
| SavedVariables coordinates | Post-save snapshots only, not live IPC. |
| Old RRAPICOORD references | Timestamped scoring references only after age budget expires. |

## Current blockers

- Movement-grade proof anchor missing.
- Same-target `ProofOnly` not passing.
- Static pointer chain not proven.
- Candidate restart validation not done.
- Latest owner batch found no module-RVA hints.
- ChromaLink world-state stale/unhealthy.

## Canonical files

| File | Purpose |
|---|---|
| `docs/recovery/current-truth.md` | This concise human dashboard. |
| `docs/recovery/current-truth.json` | Small machine-readable canonical truth. |
| `docs/recovery/historical/current-truth-full-2026-05-14-0216-before-trim.md` | Historical full chronology; stale/audit only. |
| `docs/handoffs/2026-05-14-0226-static-chain-heap-only-followup.md` | Latest static-chain follow-up handoff. |

## Next best action

Run a second stable read-only pose/family snapshot or proof-pose cycle against the selected stable family group, then use multi-pose evidence to decide whether bounded tracing/static-owner recovery is worth running. Movement remains blocked.
