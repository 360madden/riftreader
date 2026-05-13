# 2026-05-13 19:57 EDT — Context triage + reusable lead export

## ✅ Result

Continued the adaptive/static-chain workflow safely. The classifier now avoids wasting scans on obvious UI/addon/string-heavy leads, exports reusable target files, and demotes tagged/unaligned pseudo-pointers before follow-up scanning.

No movement, input, CE, x64dbg, breakpoints, provider writes, or proof promotion were used.

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

| File | Change |
|---|---|
| `scripts/rift_live_test/root_signature_family_classifier.py` | Added sanitized ASCII/context-kind triage, tagged/unaligned heap-like demotion, priority lead filtering, and reusable lead target export files. |
| `scripts/test_root_signature_family_classifier.py` | Expanded to 10 tests covering context classification, username masking, raw-hit context indexing, priority filtering, and target export de-duping. |
| `docs/recovery/current-truth.md` | Updated with the new triage/export results and bounded priority scan. |

## New artifacts

| Artifact | Verdict |
|---|---|
| `scripts/captures/root-signature-family-classifier-20260513-235458-178863/summary.json` | Passed. Classified `575` module-pointer hits. Priority parent leads are now `22` after filtering obvious non-entity contexts and tagged/unaligned pseudo-pointers. |
| `scripts/captures/root-signature-family-classifier-20260513-235458-178863/priority-parent-lead-targets.json` | Reusable target export for bounded follow-up pointer scans. |
| `scripts/captures/root-signature-family-classifier-20260513-235458-178863/non-player-parent-lead-targets.json` | Reusable broader target export. |
| `scripts/captures/pointer-family-scan-20260513-235504-655292/summary.json` | Bounded scan of top `8` priority leads; no module/static hits. Candidate-only. |
| `scripts/captures/riftscan-milestone-review-20260513-235622.json` | `ready-for-read-only-proof`, movement still false. |

## Key finding

The adaptive triage corrected a false-positive scan path:

| Evidence | Decision |
|---|---|
| A previous priority scan hit pseudo-pointer `0x26800000002` heavily. | Demoted as `tagged-or-unaligned-heap-like`; excluded from priority lead scans. |
| Top bounded priority scan target `0x2688C193360` had 2 heap refs and no module/static refs. | Candidate-only; no static root. |
| Context showed `Sanctuary`, `star_09.dds`, `FRIENDS`. | Likely string/resource/UI-adjacent, lower priority. |
| Known player chain still ranks highest. | Continue using it as the main candidate-only root gap. |

Known player chain remains:

```text
0x268D75396C0 = rift_x64.exe+0x263E950
  -> parent slot 0x268D7539700
  -> owner 0x268D753AE30
  -> coord-pointer storage 0x268D753AE40
  -> coord candidate 0x268DF21ED20
```

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\rift_live_test\root_signature_family_classifier.py scripts\root_signature_family_classifier.py scripts\test_root_signature_family_classifier.py` | Passed |
| `python scripts\test_root_signature_family_classifier.py -v` | Passed: 10 tests |
| `python scripts\root_signature_family_classifier.py --module-hint-sweep-json ... --lead-limit 8 --json` | Passed; generated bounded exports. |
| `python scripts\pointer_family_scan.py --target-file ...priority-parent-lead-targets.json ... --json` | Passed; no module/static hits. |
| `python scripts\riftscan_milestone_review.py --pid 2928 --hwnd 0xC0994 --process-name rift_x64 --write-summary --write-markdown --compact-json` | Passed; movement still false. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/recovery/current-truth.md and this handoff first. Current target is rift_x64 PID 2928 HWND 0xC0994. Do not use CE/x64dbg, do not send movement/input, and do not promote stale reference data. Fresh API/reference remains blocked. Continue static-chain recovery from scripts/captures/root-signature-family-classifier-20260513-235458-178863/summary.json. The classifier now filters obvious UI/addon/asset/path/string-heavy leads, masks username-bearing paths in previews, exports reusable target files, and excludes tagged/unaligned pseudo-pointers such as 0x26800000002. Bounded priority scan scripts/captures/pointer-family-scan-20260513-235504-655292/summary.json found no module/static hits. Known player chain remains 0x268D75396C0 -> 0x268D7539700 -> 0x268D753AE30 -> 0x268D753AE40 -> 0x268DF21ED20. Movement remains blocked until fresh API-now vs memory-now proof and ProofOnly pass.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Run the next bounded priority batch after excluding resource/UI-like contexts from the just-scanned targets. | Continue narrowing without scanning all low-score leads. |
| 2 | Add a context-kind rule for obvious asset/resource strings like `.dds`, `FRIENDS`, and zone/resource labels if they keep appearing. | Prevents repeated low-value scans. |
| 3 | Keep the known player parent slot `0x268D7539700` as the current root gap. | It remains the only high-confidence player-linked chain. |
| 4 | Keep tagged/unaligned heap-like values excluded from priority scans. | Prevents noisy pseudo-pointer paths like `0x26800000002`. |
| 5 | Prefer reusable exported target files over manual target JSON. | Reduces mistakes and supports PC-heavy workflow. |
| 6 | Recheck RRAPICOORD/ChromaLink freshness before proof-pose. | Static-chain work cannot replace API-now truth. |
| 7 | If fresh reference returns, run read-only proof-pose with same-target candidate file. | Candidate evidence needs API-now agreement before promotion. |
| 8 | Preserve all triage outputs as candidate-only. | No fresh proof anchor exists yet. |
| 9 | Re-run milestone review after each static/proof milestone. | Keeps movement gate honest. |
| 10 | Promote only after restart-stable resolver plus multi-pose API-now agreement. | Required for stable static coordinate chain. |
