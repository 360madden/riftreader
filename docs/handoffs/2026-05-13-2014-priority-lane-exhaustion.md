# 2026-05-13 20:14 EDT — Fresh-reference blocked; clean priority lane exhausted

## ✅ Result

Continued autonomously with the safest high-signal path:

1. rechecked fresh reference surfaces with no input;
2. confirmed both ChromaLink and RRAPICOORD remain blocked/stale;
3. regenerated the offset-0 priority classifier window under the newest context rules;
4. scanned offset-0 read-only against current PID/HWND;
5. generated a reusable aggregate exhaustion report.

No movement, input, reloadui, CE, x64dbg, breakpoints, provider writes, proof promotion, or target memory writes were used.

## Current live target / safety

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Process start | `2026-05-13T16:17:56.208370Z` |
| Module base | `0x7FF71CD90000` |
| Movement/navigation | **Blocked** |
| Fresh reference | **Blocked** |
| CE/x64dbg | **Not used** |
| Input/reloadui | **Not sent** |
| Proof promotion | **Not attempted** |

## What changed

| File | Change |
|---|---|
| `scripts/rift_live_test/priority_scan_exhaustion_report.py` | New reusable aggregate helper for classifier windows + pointer scans. It verifies same-target metadata and reports whether the priority lane has static/module hits. |
| `scripts/priority_scan_exhaustion_report.py` | Thin Python entry point. |
| `scripts/test_priority_scan_exhaustion_report.py` | Unit coverage for scan totals, target identity matching, and exhausted-lane verdicts. |
| `docs/recovery/current-truth.md` | Updated with fresh-reference blockers and the priority-lane exhaustion verdict. |
| `docs/handoffs/2026-05-13-2014-priority-lane-exhaustion.md` | This handoff. |

## Fresh-reference recheck

| Surface | Artifact | Verdict |
|---|---|---|
| ChromaLink world-state | `scripts/captures/chromalink-world-state-reference-20260514-000940-897289/summary.json` | Blocked: reachable but `not-healthy`, player position stale/not fresh/unavailable for navigation. Last player position observed `2026-05-13T22:55:23.0397648+00:00`, newest frame age about `4,457,665 ms`. |
| RRAPICOORD marker memory scan | `scripts/captures/rift-api-reference-scan-currentpid-2928-20260514-001004-attempt3.json` | Blocked: attempts found `8`, `6`, then `13` `RRAPICOORD1` string hits, but no usable `status=pass`, `source=rift-api`, `savedVariablesUse=none`, numeric `x/y/z` marker. |

## Priority-lane exhaustion evidence

| Artifact | Result |
|---|---|
| `scripts/captures/root-signature-family-classifier-20260514-001031-007727/summary.json` | Offset `0`, exported `8` of `15` clean priority parent leads. |
| `scripts/captures/pointer-family-scan-20260514-001038-968924/summary.json` | Scanned `25` queued target/ref-storage addresses; `18` heap hits; `0` module/RIFT-module hits. |
| `scripts/captures/root-signature-family-classifier-20260514-000240-826658/summary.json` | Offset `8`, exported remaining `7` of `15` clean priority parent leads. |
| `scripts/captures/pointer-family-scan-20260514-000246-569593/summary.json` | Scanned `24` queued target/ref-storage addresses; `17` heap hits; `0` module/RIFT-module hits. |
| `scripts/captures/priority-scan-exhaustion-report-20260514-001700-212349/summary.json` | Verdict: `priority-lane-exhausted-no-static-root`. Totals: `15` exported leads, `49` scanned targets, `35` heap hits, `0` module hits, `0` RIFT-module hits. |
| `scripts/captures/riftscan-milestone-review-20260514-001411.json` | `ready-for-read-only-proof`; movement still false. |

## Current interpretation

The current non-obvious clean priority parent-lead lane is exhausted and produced **no static/module root**. This does not invalidate the known player candidate chain; it means this particular broad classifier lane is not producing the stable root.

Known player chain remains candidate-only:

```text
0x268D75396C0 = rift_x64.exe+0x263E950
  -> parent slot 0x268D7539700
  -> owner 0x268D753AE30
  -> coord-pointer storage 0x268D753AE40
  -> coord candidate 0x268DF21ED20
```

## Validation run in this slice

| Command | Result |
|---|---|
| `python scripts/chromalink_world_state_reference.py --target-pid 2928 --target-hwnd 0xC0994 --process-name rift_x64 --json` | Blocked safely; no input/memory read. |
| `pwsh -File scripts/capture-rift-api-reference-coordinate.ps1 -ProcessId 2928 -TargetWindowHandle 0xC0994 -ProcessName rift_x64 -ScanAttempts 3 -Json` | Blocked safely; no usable RRAPICOORD marker. |
| `python scripts/root_signature_family_classifier.py --module-hint-sweep-json ... --priority-offset 0 --json` | Passed; exported offset-0 priority window. |
| `python scripts/pointer_family_scan.py --target-file ...001031.../priority-parent-lead-targets.json --depth 1 --json` | Passed; no module/static hits. |
| `python scripts/priority_scan_exhaustion_report.py ... --json` | Passed; verdict `priority-lane-exhausted-no-static-root`. |
| `python scripts/riftscan_milestone_review.py --pid 2928 --hwnd 0xC0994 --process-name rift_x64 --write-summary --write-markdown --compact-json` | Passed; movement still false. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/recovery/current-truth.md and docs/handoffs/2026-05-13-2014-priority-lane-exhaustion.md first. Current target is rift_x64 PID 2928 HWND 0xC0994, process start 2026-05-13T16:17:56.208370Z, module base 0x7FF71CD90000. Do not use CE/x64dbg, do not send movement/input/reloadui, and do not promote stale reference data. Fresh reference is still blocked: ChromaLink summary scripts/captures/chromalink-world-state-reference-20260514-000940-897289/summary.json is stale/not healthy, and RRAPICOORD scan scripts/captures/rift-api-reference-scan-currentpid-2928-20260514-001004-attempt3.json has no usable marker. Clean priority root-family lane is exhausted: scripts/captures/priority-scan-exhaustion-report-20260514-001700-212349/summary.json says 15 exported leads, 49 scanned targets, 35 heap hits, 0 module/RIFT-module hits. Known player chain remains 0x268D75396C0 -> 0x268D7539700 -> 0x268D753AE30 -> 0x268D753AE40 -> 0x268DF21ED20. Movement remains blocked until fresh API-now/reference vs memory-now proof and same-target ProofOnly pass.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Fix/refresh ChromaLink live telemetry or RRAPICOORD marker emission before proof promotion. | Fresh reference is now the main blocker, not lack of candidate scans. |
| 2 | If fresh reference returns, run explicit same-target read-only proof/readback using `same-target-candidates.json`. | Tests whether the selected candidate aligns with API-now. |
| 3 | Re-run `ProofOnly` only after fresh reference/readback passes. | Prevents stale/candidate data from becoming movement truth. |
| 4 | Add a small freshness watchdog around ChromaLink/RRAPICOORD. | Prevents wasting future scans when reference surfaces are stale. |
| 5 | If staying offline/read-only, move to lower-priority broad family groups in explicit batches with the aggregate reporter. | Current clean priority lane is exhausted. |
| 6 | Keep `priority_scan_exhaustion_report.py` in the loop after each batch. | It prevents duplicate scanning and makes coverage obvious. |
| 7 | Preserve the known player chain as the main candidate-only root gap. | It remains the strongest player-linked structure. |
| 8 | Do not prioritize UI/addon/asset/path/string-heavy/game-label/tagged pseudo-pointer leads unless new evidence links them to coords. | Keeps scan signal high. |
| 9 | Re-run milestone review after every proof/static milestone. | Keeps no-CE/no-movement/provider-read-only gates honest. |
| 10 | Promote only after module/RVA/static-owner provenance, multi-pose API-now agreement, same-target ProofOnly, and restart validation. | Required for a stable static coordinate pointer chain. |

