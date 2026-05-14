# RiftReader Current Truth

_Last updated: 2026-05-14T02:41:56Z._

## Verdict

**Movement is blocked.** The live reference surface is repaired, but there is now **no validated current coordinate candidate**. The prior best candidate was repeat-tested and rejected, and the newest broad family snapshot exposed a reference-drift problem: the snapshot matched the start RRAPICOORD value, then failed readback against the newer/current RRAPICOORD value.

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
| `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-023611/post-scan-reference/fresh-reference-coordinate.json` | Latest checked RRAPICOORD reference `7403.3999, 871.77, 3029.4099`. |
| `scripts/captures/rrapicoord-scan-diagnostics-20260514-020126-043153/summary.json` | `1` usable marker. |
| `scripts/captures/rrapicoord-addon-state-diagnostics-20260514-020130-043012/summary.json` | Addon installed and live marker observed. |

## Movement gate

| Gate | Status |
|---|---|
| Movement allowed | **No** |
| Reason | No current coordinate candidate, no movement-grade proof anchor, no static pointer chain, no restart validation, and same-target `ProofOnly` has not passed. |
| Required before movement | Fresh API/runtime reference + current memory candidate agreement + current proof anchor/static chain + same-target `ProofOnly`. |

## Best current coordinate candidate

| Field | Value |
|---|---|
| Candidate | **None validated** |
| Address | `n/a` |
| Truth status | **no current candidate; reacquisition required** |
| Why | Repeat readback rejected the old candidate; the newest broad snapshot matched the start reference but failed against the newer/current reference. |

## Latest coordinate reacquisition evidence

| Step | Artifact | Result |
|---|---|---|
| Old candidate repeat readback | `scripts/captures/riftscan-proof-pose-20260514-022700/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-222716.json` | `ReferenceMatchCount=0`; old `0x268D1FA6120` decoded near-zero, so demoted. |
| Fresh broad family snapshot | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-022754/family-snapshot-summary.json` | Read-only scan captured `46,693` triplets / `14` near-reference triplets over `361,066,496` bytes; best start-reference address `0x268D1EF0870`. |
| Fresh snapshot readback | `scripts/captures/riftscan-proof-pose-20260514-022841/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-222855.json` | `ReferenceMatchCount=0`; candidates matched source preview but not current RRAPICOORD after drift from `7402.0` to `7403.3999` X. |
| Root fix | `scripts/capture_current_pid_coordinate_family_snapshot.py` | Now performs a default post-scan RRAPICOORD drift check and blocks snapshots when reference drift exceeds tolerance. |
| Guard smoke test | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-023611/family-snapshot-summary.json` | Correctly blocked stale snapshot use with `reference-drift-during-snapshot:1.3999>0.25`. |
| Milestone strategy gate | `scripts/captures/riftscan-milestone-review-20260514-024029.json` | Correctly blocked selected candidates after stale/readback gates rejected all current files. |

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
| `0x268D1EF0870` / new start-reference snapshot candidate | Matched only the snapshot start reference; failed current-reference readback after drift. |
| `0x268E113FED0` / `family-snapshot-hit-000002` | Failed new fresh-reference readback with `ReferenceMatchCount=0`. |
| SavedVariables coordinates | Post-save snapshots only, not live IPC. |
| Old RRAPICOORD references | Timestamped scoring references only after age budget expires. |

## Current blockers

- No validated current coordinate candidate after repeat readback.
- Movement-grade proof anchor missing.
- Static pointer chain not proven.
- Latest owner batch found no module-RVA hints.
- Restart validation not done.
- Same-target `ProofOnly` not passing.
- ChromaLink world-state stale/unhealthy.

## Canonical files

| File | Purpose |
|---|---|
| `docs/recovery/current-truth.md` | This concise human dashboard. |
| `docs/recovery/current-truth.json` | Small machine-readable canonical truth. |
| `docs/recovery/historical/current-truth-full-2026-05-14-0216-before-trim.md` | Historical full chronology; stale/audit only. |
| `docs/handoffs/2026-05-14-0226-static-chain-heap-only-followup.md` | Latest static-chain follow-up handoff. |

## Next best action

Run a fresh, shorter/current family snapshot with the post-scan drift guard. If it blocks again, reduce range/time or use a multi-pose sequence before any readback promotion. Do **not** promote any candidate until API-now versus memory-now agrees and same-target `ProofOnly` passes.
