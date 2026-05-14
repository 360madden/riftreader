# Coordinate proof preflight + broad family snapshot handoff

_Last updated: 2026-05-14 01:35 UTC._

## Verdict

Fresh RRAPICOORD reference was available for the 00:42 UTC readback, but it is historical now. The newest preflight and RRAPICOORD diagnostics are blocked because no fresh reference surface is currently available. The latest RRAPICOORD scan artifacts hit source/error/static text only, not a live `RRAPICOORD1|...source=rift-api...x/y/z...savedVariablesUse=none` marker. Movement remains blocked. The strongest candidate is still `family-snapshot-hit-000002` at `0x268E113FED0`; it matched the then-fresh RRAPICOORD reference in readback, but no static/module root, current proof-anchor gate, or fresh current reference exists yet.

## Current target

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Process start | `2026-05-13T16:17:56.208370Z` |
| Module base | `0x7FF71CD90000` |
| Movement | `blocked` |
| CE/x64dbg | Not used in this slice |

## New evidence

| Artifact | Result |
|---|---|
| `scripts/captures/coordinate-proof-preflight-20260514-003348-430776/summary.json` | Preflight passed read-only proof readiness; movement false. |
| `scripts/captures/riftscan-proof-pose-20260514-003555/` | Old same-target candidate set stable but no strict reference match. |
| `scripts/captures/family-scan-currentpid-2928-20260514-003713-458360/family-scan-summary.json` | 80 MiB targeted family scan; 10 near-reference hits; best `0x268E1122890` delta ~0.600. |
| `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-003904/family-snapshot-summary.json` | Broad family snapshot; exact candidate `0x268E113FED0` delta ~0.0000488. |
| `scripts/captures/coordinate-family-snapshot-currentpid-2928-20260514-004131/family-import-candidates.json` | Importable candidate packet generated from broad snapshot for readback. |
| `scripts/captures/manual-reference-check-currentpid-2928-20260513-204202/rift-api-reference-currentpid-2928-20260514-004203.json` | Fresh RRAPICOORD reference `7402.5898, 871.78, 3028.45`; no CE/movement/SavedVariables. |
| `scripts/captures/riftscan-proof-pose-20260514-004221/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-204222.json` | `ReferenceMatchCount=1`; best `family-snapshot-hit-000002` at `0x268E113FED0`; stable 4 samples. |
| `scripts/captures/current-pid-family-neighborhood-inspector-20260514-004343-502721/summary.json` | Neighborhood inspector confirmed the exact hit in a read-only 16 KiB window. |
| `scripts/captures/pointer-family-scan-20260514-004408-853398/summary.json` | 23 pointer targets scanned; 0 module/RIFT-module hits; heap-only owner evidence. |
| `scripts/captures/riftscan-milestone-review-20260514-005443.json` | Strategy gate now selects proof-backed `family-snapshot-hit-000002` from the family import candidate file; movement still false. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-005632-012315/summary.json` | 12 owner/ref-storage windows inspected read-only; no exact ref to `0x268E113FED0`; no static root. |
| `scripts/captures/root-signature-module-hint-sweep-20260514-005740-921073/summary.json` and sibling sweeps `005745`, `005746`, `005750` | New module-RVA sweeps were heap-only/low-score; no root promotion. |
| `scripts/captures/pointer-owner-batch-currentpid-2928-20260514-010553-091229/summary.json` | Repo-owned batch helper inspected 15 owner/ref-storage windows; top module-RVA hint `0x270FE10` repeated across 3 adjacent owners; no exact `0x268E113FED0` root promotion. |
| `scripts/captures/root-signature-module-hint-sweep-20260514-010614-614734/summary.json` and sibling sweeps `010631`, `010633`, `010637` | Follow-up sweeps for `0x270FE10`, `0x2759FA8`, `0x2650220`, and `0x26502B0`; all heap-only/low-score, no static/module root. |
| `scripts/captures/riftscan-milestone-review-20260514-010755.json` | Strategy gate remains `ready-for-read-only-proof`; selected candidate unchanged; movement remains false due stale proof pointer gate. |
| `scripts/captures/root-signature-batch-sweep-currentpid-2928-20260514-011513-452096/summary.json` | Automated root-RVA sweep selector consumed the owner batch and selected `0` new sweeps; all `10` hints were already swept for the current target or old root-signature fields. |
| `scripts/captures/coordinate-proof-preflight-20260514-011824-911933/summary.json` | Latest coordinate proof preflight blocked: ChromaLink stale/unhealthy, RRAPICOORD scan had no usable marker, previous RRAPICOORD reference too old. |
| `scripts/captures/rrapicoord-scan-diagnostics-20260514-012713-317516/summary.json` | Read-only scan-artifact diagnostic over latest 3 RRAPICOORD scans: 29 hits loaded; 3 `RRAPICOORD1` text hits; 0 marker-like records; 0 usable markers. Inferred cause: source/error/static text only, no live source/view/coordinate fields. |
| `scripts/captures/riftscan-milestone-review-20260514-012910.json` | Post-diagnostic strategy gate remains `ready-for-read-only-proof` and `movementAllowedByReview=false`; it does not override the stricter fresh-reference/preflight blocker. |
| `scripts/captures/rrapicoord-addon-state-diagnostics-20260514-013524-019157/summary.json` | Read-only addon-state diagnostic: repo addon contract passed; installed copies under both discovered AddOns roots match repo required files; latest scan diagnostic still has 0 usable markers. Blocker is live runtime marker not observed, not install drift. |
| `cmd /c scripts\validate-addon.cmd` | Lua syntax validation passed for 4 addons, including `RiftReaderApiProbe`. |
| `scripts/captures/riftscan-milestone-review-20260514-013621.json` | Post-addon-state strategy gate unchanged: selected family candidate remains read-only proof candidate; `movementAllowedByReview=false`; fresh-reference/preflight blocker still controls. |

## Proven truth vs candidate-only

| Item | Status |
|---|---|
| Fresh RRAPICOORD reference | Historical 00:42 UTC scoring reference only; not current now. |
| Current RRAPICOORD scan | Blocked: latest 3 scans have source/error/static `RRAPICOORD1` text only; no usable live marker. |
| `0x268E113FED0` | Strong current candidate; stable same-pose memory/readback match. |
| Static pointer chain | Not proven; pointer scan found no module/static root. |
| Movement/navigation use | Blocked. |
| Old proof-anchor cache | Historical/stale only; PID `57656`, HWND `0x5417BC`. |

## Code changes in this slice

- Added `scripts/coordinate_proof_preflight.py` and `scripts/rift_live_test/coordinate_proof_preflight.py` as a one-command preflight orchestrator.
- Updated `reference_freshness_watchdog.py` to accept RRAPICOORD reference files directly, not only raw scans.
- Updated `coordinate_proof_preflight.py` to pass the generated RRAPICOORD reference file into the watchdog.
- Updated `capture_current_pid_coordinate_family_snapshot.py` to emit importable candidate JSON/JSONL packets for readback.
- Updated `current_pid_family_neighborhood_inspector.py` to parse current readback summaries (`ReferenceCoordinate` / `CandidateReadbacks`).
- Added `scripts/pointer_owner_batch_inspector.py` and `scripts/rift_live_test/pointer_owner_batch_inspector.py` so owner/ref-storage batch analysis is repeatable instead of one-off. It reads pointer-family summaries, runs read-only owner inspections, ranks rows, extracts module-RVA hints, and writes durable JSON/Markdown summaries.
- Added `scripts/root_signature_batch_sweep.py` and `scripts/rift_live_test/root_signature_batch_sweep.py` so module-RVA sweep selection is automated. It consumes owner-batch summaries, skips already-swept current-target RVAs and stale root-signature field RVAs, runs or dry-runs root sweeps, and writes durable JSON/Markdown summaries.
- Updated `coordinate_proof_preflight.py` to promote explicit blocked child-command reasons into top-level blockers. Current benefit: `rrapicoord-no-usable-marker` is now visible at the top level instead of being obscured by the old stale-reference fallback.
- Added `scripts/rrapicoord_scan_diagnostics.py` and `scripts/rift_live_test/rrapicoord_scan_diagnostics.py` so blocked RRAPICOORD scan artifacts can be diagnosed offline without rereading process memory, sending input, using CE, or attaching x64dbg.
- Added `scripts/rrapicoord_addon_state_diagnostics.py` and `scripts/rift_live_test/rrapicoord_addon_state_diagnostics.py` so addon source/install state can be checked read-only before any live UI action.

## Resume prompt

Resume in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs/recovery/current-truth.md` and this handoff first. Continue from the current strongest candidate `family-snapshot-hit-000002` at `0x268E113FED0` using the readback artifact `scripts/captures/riftscan-proof-pose-20260514-004221/riftscan-riftreader-currentpid-2928-readback-wrapper-summary-20260513-204222.json` as historical candidate evidence only. Movement remains blocked. Passive pointer/owner/module-hint sweeps are currently exhausted for this owner batch: `scripts/root_signature_batch_sweep.py` selected `0` new RVAs. The newest preflight `scripts/captures/coordinate-proof-preflight-20260514-011824-911933/summary.json` blocks because there is no fresh reference surface. The newest RRAPICOORD diagnostic `scripts/captures/rrapicoord-scan-diagnostics-20260514-012713-317516/summary.json` shows the latest scans are source/error/static text only, with 0 marker-like records and 0 usable markers. The addon-state diagnostic `scripts/captures/rrapicoord-addon-state-diagnostics-20260514-013524-019157/summary.json` shows the repo addon contract and installed copies are good, so the likely blocker is that the live addon runtime marker is not loaded/refreshed/observable in the current session. Next best work is an operator-approved bounded live addon status/refresh check, then rerun fresh-reference preflight before any readback/proof or debugger access-chain tracing. Do not use stale PID `57656` proof anchors, old absolute pointers, old RRAPICOORD coordinates, or SavedVariables snapshots as current truth.
