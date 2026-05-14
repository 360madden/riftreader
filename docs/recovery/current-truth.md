# RiftReader Current Truth

_Last updated: 2026-05-14T03:44:12Z._

## Verdict

**Movement is blocked.** The live `RRAPICOORD1` reference surface is usable again and the proof-pose wrapper now uses a wider RRAPICOORD scan window. Two consecutive robust read-only proof-pose runs selected **`family-snapshot-hit-000004` at `0x268D5A80730`** as the latest current-reference match. The no-attach x64dbg readiness packet now uses the **current-truth candidate** instead of hidden `latest/best` candidate fallback and passed preflight. The family-snapshot sequence helper now defaults to `RRAPICOORD1`, imports current-truth PID/HWND/start/module defaults, and prioritizes the current-truth candidate as the top family prior. Offline passive-stability analysis of the no-input sequence extracted **13 stable near-reference triplet candidates** for family-context seeding, but this is still **candidate-only** because there is no displaced-pose delta, no static chain, no restart validation, and no same-target `ProofOnly` pass.

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
| `ReaderBridge_RRAPICOORD1` | **current / usable for read-only proof** | Live `Inspect.Unit.Detail(player)`, `source=rift-api`, `savedVariablesUse=none`. Latest reference: `7403.4, 871.77, 3029.41` at `2026-05-14T03:19:00.9443165Z`. |
| ChromaLink world-state | stale / not authoritative | Still not the authority for coordinate proof in this lane. |
| SavedVariables | not live truth | Post-save snapshots only; never use as live movement truth. |

Key proof artifacts:

| Artifact | Result |
|---|---|
| `scripts/captures/riftscan-proof-pose-20260514-030047/pose-api-reference.json` | Latest RRAPICOORD reference used for readback scoring. |
| `scripts/captures/riftscan-proof-pose-20260514-030047/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-230104.json` | Latest readback: `ReferenceMatchCount=1`, selected `family-snapshot-hit-000004`. |
| `scripts/captures/rrapicoord-reference-refresh-20260513-231853/rift-api-reference-currentpid-2928-20260514-031853.json` | Fresh RRAPICOORD reference used for no-attach x64dbg readiness. |
| `scripts/captures/x64dbg-no-attach-readiness-packet-20260514-031908-072876/summary.json` | Passed no-attach readiness: exact target, fresh API coordinate, current-truth candidate, no debugger attach started. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/summary.json` | Passive no-input family sequence now works with `RRAPICOORD1` and current-truth priors; blocked intentionally because no displaced pose was captured. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-033507-237928/summary.json` | Plan-only smoke: no PID/HWND/prior supplied; helper bootstrapped all target fields and `currentTruth=0x268D5A80730` from current truth. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/delta-summary.json` | Offline passive-stability analysis: `13` stable near-reference candidates extracted; still blocked with `blocked-no-displaced-pose` and not promotion-eligible. |
| `scripts/captures/rrapicoord-scan-diagnostics-20260514-030154-581879/summary.json` | Usable marker present after direct robust scan. |
| `scripts/captures/rrapicoord-addon-state-diagnostics-20260514-030154-988294/summary.json` | Addon installed and live marker observed. |

## Movement gate

| Gate | Status |
|---|---|
| Movement allowed | **No** |
| Reason | Candidate is read-only heap evidence only; no movement-grade proof anchor, no static pointer chain, no restart validation, and same-target `ProofOnly` has not passed. |
| Required before movement | Fresh API/runtime reference + current memory candidate agreement + current proof anchor/static chain + same-target `ProofOnly`. |

## Best current coordinate candidate

| Field | Value |
|---|---|
| Candidate | `family-snapshot-hit-000004` |
| Address | `0x268D5A80730` |
| Candidate file | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/family-import-candidates.json` |
| Readback | `scripts/captures/riftscan-proof-pose-20260514-030047/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-230104.json` |
| Reference | `scripts/captures/riftscan-proof-pose-20260514-030047/pose-api-reference.json` |
| Evidence | `ReferenceMatchCount=1`, `StableDecodedCandidateCount=10`, max abs delta `4.960937758369255e-07`. |
| Truth status | **candidate-only, not movement proof** |
| Selection note | Two consecutive robust proof-pose runs selected `000004`; prior `000003` is now family-context only because newer readbacks did not match the current reference. Duplicate coordinate copies still need multi-pose disambiguation. |

## Latest coordinate reacquisition evidence

| Step | Artifact | Result |
|---|---|---|
| Fresh broad family snapshot | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/family-snapshot-summary.json` | Read-only scan captured `47,193` triplets / `12` near-reference triplets over `363,360,256` bytes. |
| Post-scan reference guard | `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-024349/post-scan-reference/fresh-reference-coordinate.json` | Passed: pre/post RRAPICOORD stable with max abs drift `0.0`. |
| Passive sequence helper repair | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/summary.json` | Read-only/no-input sequence captured two RRAPICOORD references and `33,554,432` bytes per pose from the current-truth family neighborhood; blocked with `blocked-no-displaced-pose` as expected. |
| Passive stability candidate extraction | `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/candidate-vec3.json` | Extracted `13` candidate-only stable near-reference triplets from the passive no-input sequence; best `snapshot-passive-stable-268D4B2A2A0-xyz` at `0x268D4B2A2A0`, `promotionEligible=false`. |
| Underpowered reference capture | `scripts/captures/riftscan-proof-pose-20260514-024955` | Blocked safely; no usable full marker from the narrow 512-byte context. Superseded, not proof evidence. |
| Proof-pose wrapper fix | `scripts/capture-riftscan-proof-pose.ps1` | Now passes `4096` context bytes, `512` max hits, `5` attempts, `1500ms` retry delay to the reference capture helper. |
| Repeat proof-pose confirmation | `scripts/captures/riftscan-proof-pose-20260514-030047/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-230104.json` | Second robust pass again selected `family-snapshot-hit-000004`; read-only only. |
| Milestone strategy gate | `scripts/captures/riftscan-milestone-review-20260514-030120.json` | Ready for more read-only proof; movement still not allowed. |

## Static-chain / pointer status

| Evidence | Result |
|---|---|
| `scripts/captures/pointer-family-scan-20260514-030426-089234/summary.json` | Direct scan for `0x268D5A80730` found `0` exact pointer refs. |
| `scripts/captures/pointer-family-scan-20260514-030436-657736/summary.json` | Family-base scan for `0x268D5A80000` found `19` heap refs, `0` module/RIFT-module hits. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-030612-600628/summary.json` | `19` owner windows inspected; `20` module-RVA hints found, top `0x263E5F8`, but candidate-only. |
| `scripts/captures/root-signature-batch-sweep-currentpid-2928-20260514-030832-821868/summary.json` | Manual top-RVA root sweep matched a self-derived owner signature only; no static root proven. |
| `scripts/captures/pointer-family-scan-20260514-030856-814392/summary.json` | Reverse pointer scan for self-derived owner base `0x26887C277C8` found `0` refs. |
| `scripts/captures/x64dbg-no-attach-readiness-packet-20260514-031908-072876/summary.json` | No-attach readiness passed with current-truth `family-snapshot-hit-000004`; stale hidden `latest/best` candidate fallback is now blocked by default. |
| `scripts/captures/x64dbg-coord-chain-plan-20260514-031908-113310/coord-chain-plan-summary.json` | Planned only; ready for current-turn approval, but no x64dbg attach/watchpoint/access event was executed. |
| Static pointer chain | **not proven** |

## Explicitly stale / invalid / not current best

| Item | Why not current truth |
|---|---|
| PID `57656` / HWND `0x5417BC` proof-anchor cache | Old process epoch. |
| `0x268D506BC50` / `family-snapshot-hit-000003` | Previous readback lead; latest robust readback did not match current RRAPICOORD reference. Keep only as family-context evidence. |
| `riftscan-proof-pose-20260514-024955` reference capture | Blocked by underpowered RRAPICOORD context; superseded by robust capture and wrapper fix. |
| `0x268D1FA6120` / old `family-snapshot-hit-000001` | Repeat readback returned `ReferenceMatchCount=0` and decoded near-zero floats. |
| `0x268D1EF0870` / prior start-reference snapshot candidate | Matched only an older snapshot start reference; failed later current-reference readback after drift. |
| SavedVariables coordinates | Post-save snapshots only, not live IPC. |
| Old RRAPICOORD references | Timestamped scoring references only after age budget expires. |

## Current blockers

- Movement-grade proof anchor missing.
- Same-target `ProofOnly` not passing.
- Static pointer chain not proven.
- Candidate restart validation not done.
- Duplicate heap coordinate copies are not yet disambiguated across multiple poses.
- Module-RVA hints are candidate-only and not connected to a stable/static root; owner-base reverse pointer scan found no refs.
- x64dbg access events have not been captured; any live debugger capture still requires explicit current-turn approval and the bounded attach policy.
- Displaced-pose or approved x64dbg/access evidence is still missing; passive stability candidates are family-context seeds only and not movement proof.
- ChromaLink world-state stale/unhealthy.

## Canonical files

| File | Purpose |
|---|---|
| `docs/recovery/current-truth.md` | This concise human dashboard. |
| `docs/recovery/current-truth.json` | Small machine-readable canonical truth. |
| `docs/recovery/historical/current-truth-full-2026-05-14-0216-before-trim.md` | Historical full chronology; stale/audit only. |
| `docs/handoffs/2026-05-14-0226-static-chain-heap-only-followup.md` | Latest static-chain follow-up handoff. |
| `scripts/captures/x64dbg-no-attach-readiness-packet-20260514-031908-072876/summary.json` | Latest no-attach x64dbg readiness packet; current-truth candidate, no attach. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/summary.json` | Latest passive family-snapshot sequence; RRAPICOORD default, current-truth prior first, no input. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-033507-237928/summary.json` | Latest current-truth bootstrapped plan-only sequence; no manual PID/HWND/prior needed. |
| `scripts/captures/family-snapshot-sequence-currentpid-2928-20260514-032849-991117/passive-stability-analysis/candidate-vec3.json` | Candidate-only passive stable triplets from the latest no-input family sequence; family-context seeds only. |

## Next best action

Use passive-stability candidates only as family-context seeds, then capture a displaced-pose/offline delta proof or approved bounded x64dbg access evidence. Movement/navigation remains blocked until current proof/static chain and same-target `ProofOnly` pass.
