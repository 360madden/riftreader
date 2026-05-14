# 2026-05-13 20:20 EDT — Reference freshness watchdog gate

## ✅ Result

Added a reusable local watchdog that summarizes the latest ChromaLink and RRAPICOORD reference artifacts before proof work. It blocks early when reference surfaces are stale, preventing wasted scans or accidental promotion of candidate-only data.

No movement, input, reloadui, CE, x64dbg, breakpoints, provider writes, proof promotion, target memory reads, or target memory writes were used by the watchdog.

## Current live target / safety

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Movement/navigation | **Blocked** |
| Fresh reference | **Blocked** |
| CE/x64dbg | **Not used** |
| Input/reloadui | **Not sent** |
| Proof promotion | **Not attempted** |

## What changed

| File | Change |
|---|---|
| `scripts/rift_live_test/reference_freshness_watchdog.py` | New artifact-first freshness gate for ChromaLink + RRAPICOORD reference surfaces. It checks target metadata, ChromaLink freshness, RRAPICOORD usable-marker contract, and writes JSON/Markdown summaries. |
| `scripts/reference_freshness_watchdog.py` | Thin Python entry point. |
| `scripts/test_reference_freshness_watchdog.py` | Unit tests for marker parsing/usability, target matching, and verdict choice. |
| `docs/recovery/current-truth.md` | Updated with the watchdog result and current blocked reference status. |

## Watchdog result

| Artifact | Verdict |
|---|---|
| `scripts/captures/reference-freshness-watchdog-20260514-002036-448433/summary.json` | `blocked-fresh-reference-unavailable` |
| ChromaLink source | `scripts/captures/chromalink-world-state-reference-20260514-000940-897289/summary.json`; stale/not healthy, player position age `4457665.64 ms`. |
| RRAPICOORD source | `scripts/captures/rift-api-reference-scan-currentpid-2928-20260514-001004-attempt3.json`; `13` string hits, `0` usable markers. |

## Current interpretation

The main blocker is no longer candidate enumeration. The clean priority lane is already exhausted and the known player chain is still candidate-only. The next useful work must restore a fresh reference surface or use strictly offline/lower-priority exploration that is clearly labeled candidate-only.

Known player chain remains:

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
| `python -m py_compile scripts/rift_live_test/reference_freshness_watchdog.py scripts/reference_freshness_watchdog.py scripts/test_reference_freshness_watchdog.py` | Passed |
| `python scripts/test_reference_freshness_watchdog.py -v` | Passed: `4` tests |
| `python scripts/reference_freshness_watchdog.py --target-pid 2928 --target-hwnd 0xC0994 --process-name rift_x64 --json` | Blocked safely with `blocked-fresh-reference-unavailable`. |
| `python scripts/riftscan_milestone_review.py --pid 2928 --hwnd 0xC0994 --process-name rift_x64 --write-summary --write-markdown --compact-json` | Passed; `ready-for-read-only-proof`, movement still false. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/recovery/current-truth.md and docs/handoffs/2026-05-13-2020-reference-watchdog.md first. Current target is rift_x64 PID 2928 HWND 0xC0994. Do not use CE/x64dbg, do not send movement/input/reloadui, and do not promote stale reference data. Run python scripts/reference_freshness_watchdog.py --target-pid 2928 --target-hwnd 0xC0994 --process-name rift_x64 --json as the first gate before proof/readback. Latest watchdog artifact scripts/captures/reference-freshness-watchdog-20260514-002036-448433/summary.json blocks with stale ChromaLink and no usable RRAPICOORD marker. Clean priority lane is exhausted via scripts/captures/priority-scan-exhaustion-report-20260514-001700-212349/summary.json. Known player chain remains 0x268D75396C0 -> 0x268D7539700 -> 0x268D753AE30 -> 0x268D753AE40 -> 0x268DF21ED20. Movement remains blocked until fresh API-now/reference vs memory-now proof and same-target ProofOnly pass.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Make the reference watchdog the first gate in every coord-proof resume. | Prevents stale ChromaLink/RRAPICOORD data from wasting work. |
| 2 | Fix or refresh ChromaLink live telemetry outside RiftReader if provider edits are authorized. | ChromaLink is stale/not healthy and is the best live reference surface. |
| 3 | Fix or refresh RRAPICOORD marker emission if addon/provider work is authorized. | RRAPICOORD has marker strings but no usable pass/source/x-y-z marker. |
| 4 | Once watchdog passes, run same-target read-only proof/readback using `same-target-candidates.json`. | Converts candidate data into evidence against fresh API-now truth. |
| 5 | Re-run `ProofOnly` only after fresh reference/readback passes. | Keeps movement gated. |
| 6 | If staying offline-only, widen into lower-priority families but keep aggregate reports. | Current clean priority lane is exhausted. |
| 7 | Do not rescan the exhausted 15 priority leads unless input artifacts change. | Avoids duplicate CPU/token work. |
| 8 | Preserve known player chain as the main candidate-only root gap. | It remains the strongest player-linked structure. |
| 9 | Re-run milestone review after every proof/static milestone. | Maintains the no-CE/no-movement/provider-read-only boundary. |
| 10 | Promote only after fresh reference, memory-now agreement, ProofOnly, and restart validation. | Required for stable static coord chain. |
