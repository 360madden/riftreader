# 2026-05-13 20:06 EDT — Priority-offset context triage + scan result

## ✅ Result

Continued the static-chain recovery workflow with the current PID/HWND and no stale-data promotion. The classifier now demotes dotted UTF-16-like game/zone labels as non-entity context, regenerated the remaining priority batch, and the bounded read-only pointer scan found no module/static root in that batch.

No movement, input, reloadui, CE, x64dbg, breakpoints, provider writes, or proof promotion were used.

## Current live target / safety

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Process start | `2026-05-13T16:17:56.208370Z` |
| Module base | `0x7FF71CD90000` |
| Movement/navigation | **Blocked** |
| CE/x64dbg | **Not used** |
| Input/reloadui | **Not sent** |
| Proof promotion | **Not attempted** |

## What changed

| File | Change |
|---|---|
| `scripts/rift_live_test/root_signature_family_classifier.py` | Added `--priority-offset` batch export support, normalized dotted/UTF-16-like context text, expanded UI/asset/game-label classification, demoted tagged/unaligned heap-like pseudo-pointers, and now treats `game-label-string` as `obviousNonEntity`. |
| `scripts/test_root_signature_family_classifier.py` | Added tests for dotted context normalization, game-label non-entity demotion, and priority-offset window export. |
| `docs/recovery/current-truth.md` | Updated with the 00:02-00:04 UTC scan result and current blocked movement status. |

## New artifacts

| Artifact | Verdict |
|---|---|
| `scripts/captures/root-signature-family-classifier-20260514-000240-826658/summary.json` | Passed. `575` module-pointer hits; `6` owner families; `6` parent-slot families; `205` owner-pointer region clusters; `15` remaining clean priority parent leads after triage. |
| `scripts/captures/root-signature-family-classifier-20260514-000240-826658/priority-parent-lead-targets.json` | Remaining priority window from `--priority-offset 8`: `7` parent leads exported as `14` parent/owner targets. |
| `scripts/captures/pointer-family-scan-20260514-000246-569593/summary.json` | Passed read-only scan of `24` queued targets/ref-storages. No module/static hits; candidate-only. |
| `scripts/captures/riftscan-milestone-review-20260514-000430.json` | `ready-for-read-only-proof`; movement still false. |

## Key finding

| Evidence | Decision |
|---|---|
| Dotted strings such as `F.R.I.E.N.D.S`, `s.t.a.r._.0.9...d.d.s`, and `S.a.n.c.t.u.a.r.y` appear in nearby context. | Normalize/demote them as UI/asset/game-label non-entity context before spending scan time. |
| Priority parent leads dropped to `15` total after better context rules. | Current non-obvious priority lane is now small enough to exhaust in bounded batches. |
| Remaining priority-offset batch scan found `0` module/RIFT-module hits. | No static root found in this batch; keep candidate-only. |
| Known player chain still ranks highest and remains narrow. | Preserve as the best candidate-only root gap, but do not promote without fresh API-now vs memory-now proof. |

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
| `python -m py_compile scripts/rift_live_test/root_signature_family_classifier.py scripts/root_signature_family_classifier.py scripts/test_root_signature_family_classifier.py` | Passed |
| `python scripts/test_root_signature_family_classifier.py -v` | Passed: `12` tests |
| `python scripts/root_signature_family_classifier.py --module-hint-sweep-json ... --sample-limit 8 --lead-limit 8 --priority-offset 8 --json` | Passed; generated remaining priority batch. |
| `python scripts/pointer_family_scan.py --target-file ...priority-parent-lead-targets.json --depth 1 --json` | Passed; no module/static hits. |
| `python scripts/riftscan_milestone_review.py --pid 2928 --hwnd 0xC0994 --process-name rift_x64 --write-summary --write-markdown --compact-json` | Passed; movement still false. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/recovery/current-truth.md and docs/handoffs/2026-05-13-2006-priority-offset-context-triage.md first. Current target is rift_x64 PID 2928 HWND 0xC0994, process start 2026-05-13T16:17:56.208370Z, module base 0x7FF71CD90000. Do not use CE/x64dbg, do not send movement/input/reloadui, and do not promote stale reference data. Latest classifier artifact scripts/captures/root-signature-family-classifier-20260514-000240-826658/summary.json now demotes dotted UI/asset/game-label strings and shows only 15 clean priority parent leads. Priority-offset scan scripts/captures/pointer-family-scan-20260514-000246-569593/summary.json scanned the remaining priority batch and found no module/static hits. Known player chain remains 0x268D75396C0 -> 0x268D7539700 -> 0x268D753AE30 -> 0x268D753AE40 -> 0x268DF21ED20. Movement remains blocked until fresh API-now/reference vs memory-now proof and same-target ProofOnly pass.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Try to restore a fresh reference surface (`RRAPICOORD` live marker or ChromaLink `player.position`). | Static-chain candidates cannot be promoted without API-now/reference truth. |
| 2 | If fresh reference returns, run explicit read-only proof/readback using `same-target-candidates.json`. | Confirms whether `same-target-268DF21ED30-xyz` is real current coordinate data. |
| 3 | Re-run same-target `ProofOnly` only after the fresh reference/readback gate passes. | Prevents stale/candidate data from becoming movement truth. |
| 4 | If staying offline/read-only, widen into lower-priority family groups in bounded chunks. | The current clean priority parent-lead lane is exhausted with no static root. |
| 5 | Keep using `--priority-offset` windows instead of rescanning the same exported targets. | Avoids duplicate work and token/CPU waste. |
| 6 | Add a compact aggregate report over all priority-batch scans. | Makes it obvious which families are exhausted and which remain untested. |
| 7 | Preserve the known player parent chain as the main root-gap candidate. | It remains the strongest current-PID player-linked structure. |
| 8 | Do not use `game-label-string`, UI, addon, asset, path, string-heavy, or tagged/unaligned pseudo-pointer leads as priority unless new evidence links them to player coords. | Keeps scanning signal high. |
| 9 | Re-run milestone review after the next proof/static milestone. | Maintains the no-CE/no-movement/provider-read-only gate. |
| 10 | Promote only after module/RVA/static-owner provenance, multi-pose API-now agreement, and restart validation. | Required for a stable static coordinate pointer chain. |
