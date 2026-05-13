# 2026-05-13 19:44 EDT — Root family classifier + non-player cluster triage

## ✅ Result

Continued the PC-heavy/offline static-chain workflow. I classified the full `575`-hit module-hint sweep into structural families, then probed the largest non-player heap-like cluster read-only. No movement, input, CE, x64dbg, breakpoints, provider writes, or proof promotion were used.

## Current live target / safety

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Movement | **Blocked** |
| CE/x64dbg | **Not used** |
| Input/reloadui | **Not sent** |
| Proof promotion | **Not attempted** |

## What changed

| File | Purpose |
|---|---|
| `scripts/rift_live_test/root_signature_family_classifier.py` | Offline classifier for module-hint sweep artifacts; groups owner-field and parent-slot candidates into structural families. |
| `scripts/root_signature_family_classifier.py` | Thin operator wrapper. |
| `scripts/test_root_signature_family_classifier.py` | Tests for field offset splitting, pointer classes, family grouping, region clustering, and non-player lead filtering. |
| `docs/recovery/current-truth.md` | Updated with classifier and cluster triage results. |

## New artifacts

| Artifact | Verdict |
|---|---|
| `scripts/captures/root-signature-family-classifier-20260513-234241-403707/summary.json` | Passed. Classified `575` module-pointer hits into `5` owner families, `5` parent-slot families, `205` owner-pointer region clusters, and `114` non-player parent-slot leads. |
| `scripts/captures/pointer-family-scan-20260513-234327-662584/summary.json` | Passed. Follow-up grouped pointer scan of the largest non-player heap-like cluster `0x268E2A30000`; no module/static hits. |

## Key evidence

| Finding | Evidence | Decision |
|---|---|---|
| Known player chain remains top family | Owner family `matched=0x0,0x8,0xE0|coord=known`, count `1`, top owner `0x268D753AE30`, coord pointer `0x268DF21ED20`. | Keep as strongest candidate-only player source chain. |
| Known parent slot remains unique high-confidence parent family | Parent family `offset=-0x40|ownerPointer=known`, count `1`, parent slot `0x268D7539700`. | Keep as current root gap. |
| Broad non-player heap-like parent family exists | Parent family `offset=-0x40|ownerPointer=heap-like`, count `114`, top score `15`. | Candidate-only triage pool, not proof. |
| Largest non-player cluster looks like UI/event data | Follow-up scan context includes `Event.Buff.Add`, `Event.Currency`, `Layout.Update`, `Mail_Read_Auction`; no module/static hits. | De-prioritize cluster `0x268E2A30000` unless later evidence links it to player coords. |
| Stale/volatile owner field remains flagged | `+0x110` expected `0x2657C80`, live observed `0x264C688`. | Do not use `+0x110` as hard predicate. |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\rift_live_test\root_signature_family_classifier.py scripts\root_signature_family_classifier.py scripts\test_root_signature_family_classifier.py` | Passed |
| `python scripts\test_root_signature_family_classifier.py -v` | Passed: 6 tests |
| `python scripts\root_signature_family_classifier.py --module-hint-sweep-json ... --json` | Passed; generated classifier artifact above |
| `python scripts\pointer_family_scan.py --target-file ...e2a3-family-pointer-targets.json ... --json` | Passed; generated non-player cluster scan above |
| `python scripts\riftscan_milestone_review.py --pid 2928 --hwnd 0xC0994 --process-name rift_x64 --write-summary --write-markdown --compact-json` | Passed; wrote `scripts/captures/riftscan-milestone-review-20260513-234615.json`, movement still false. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/recovery/current-truth.md and this handoff first. Current target is rift_x64 PID 2928 HWND 0xC0994. Do not use CE/x64dbg, do not send movement/input, and do not promote stale reference data. Fresh API/reference remains blocked. Continue static-chain recovery from scripts/captures/root-signature-family-classifier-20260513-234241-403707/summary.json plus root-signature sweep scripts/captures/root-signature-module-hint-sweep-20260513-233734-920187/summary.json. Known player chain is still 0x268D75396C0 -> 0x268D7539700 -> 0x268D753AE30 -> 0x268D753AE40 -> 0x268DF21ED20. Treat owner +0x110 as volatile. De-prioritize non-player cluster 0x268E2A30000 because follow-up scan showed UI/event/mail strings and no module/static hits. Movement remains blocked until fresh API-now vs memory-now proof and ProofOnly pass.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Classify the remaining non-player parent-slot leads by ASCII/context kind. | Quickly discard UI/addon/event families before expensive pointer scans. |
| 2 | Prioritize heap-like parent clusters that lack obvious UI strings. | Better chance of finding actual entity/container ownership. |
| 3 | Keep the known player parent slot `0x268D7539700` as the current root gap. | It remains the only high-confidence player-linked chain. |
| 4 | Keep `+0x110` demoted to weak/volatile. | Live current-PID evidence contradicts the older packet. |
| 5 | Add a compact lead-export mode if repeated target-file generation continues. | Reduces manual one-off glue and keeps PC-heavy scans reproducible. |
| 6 | Recheck RRAPICOORD/ChromaLink freshness before proof-pose. | Static-chain work cannot replace API-now truth. |
| 7 | If fresh reference returns, run read-only proof-pose with same-target candidate file. | Candidate evidence needs API-now agreement before promotion. |
| 8 | Preserve cluster triage outputs as candidate-only. | Useful search evidence, not movement truth. |
| 9 | Re-run milestone review after any proof/static-chain milestone. | Keeps movement gate honest. |
| 10 | Promote only after restart-stable resolver plus multi-pose API-now agreement. | Required for stable static coord chain. |
