# 2026-05-13 19:38 EDT — Root module-hint sweep follow-up

## ✅ Result

Continued the static-chain recovery lane safely. No movement, input, CE, x64dbg, breakpoints, provider writes, or proof promotion were used. The newest work broadened the search from the single parent slot to all live occurrences of the selected module hint `rift_x64.exe+0x263E950`.

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

## New helper

| File | Purpose |
|---|---|
| `scripts/rift_live_test/root_signature_module_hint_sweep.py` | Read-only Python helper that consumes a root-signature packet, scans the current process for the selected module hint, decodes hit context, and ranks owner-field / parent-slot candidates. |
| `scripts/root_signature_module_hint_sweep.py` | Thin operator wrapper. |
| `scripts/test_root_signature_module_hint_sweep.py` | Focused unit tests for qword decoding, ranking, parent-slot scoring, and stale field mismatch warnings. |

## New artifacts

| Artifact | Verdict |
|---|---|
| `scripts/captures/pointer-family-scan-20260513-233157-559293/summary.json` | Grouped pointer sweep confirmed no new parent-of-parent; known `owner <- parent slot` and `coord pointer <- storage` refs remain the only direct refs. |
| `scripts/captures/root-signature-module-hint-sweep-20260513-233734-920187/summary.json` | Passed. Scanned `575` live occurrences of `rift_x64.exe+0x263E950`; top owner and parent-slot candidates are the known player chain. Candidate-only. |
| `scripts/captures/riftscan-milestone-review-20260513-233744.json` | `ready-for-read-only-proof`, `movementAllowedByReview=false`. |

## Important finding

The broad live sweep confirmed the strongest current chain pieces:

```text
0x268D75396C0 = rift_x64.exe+0x263E950
  -> parent slot 0x268D7539700
  -> owner 0x268D753AE30
  -> coord-pointer storage 0x268D753AE40
  -> coord candidate 0x268DF21ED20
```

But it also found a stale/volatile field in older offline evidence:

| Field | Older packet expected | Live sweep observed | Action |
|---|---|---|---|
| owner `+0x110` | `0x2657C80` | `0x264C688` | Demote to weak/volatile clue until revalidated. Do not require it as a hard root predicate. |

This is exactly why current-process sweeps must verify old packet data before using it as logic.

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\rift_live_test\root_signature_module_hint_sweep.py scripts\root_signature_module_hint_sweep.py scripts\test_root_signature_module_hint_sweep.py` | Passed |
| `python scripts\test_root_signature_module_hint_sweep.py -v` | Passed: 5 tests |
| `python scripts\root_signature_module_hint_sweep.py ... --json` | Passed; generated the sweep artifact above |
| `python scripts\riftscan_milestone_review.py --pid 2928 --hwnd 0xC0994 --process-name rift_x64 --write-summary --write-markdown --compact-json` | Passed; movement still false |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/recovery/current-truth.md and this handoff first. Current target is rift_x64 PID 2928 HWND 0xC0994. Do not use CE/x64dbg, do not send movement/input, and do not promote stale reference data. Fresh API/reference remains blocked. Continue static-chain recovery from scripts/captures/root-signature-module-hint-sweep-20260513-233734-920187/summary.json and scripts/captures/parent-slot-root-signature-packet-20260513-232733-606293/summary.json. The known chain remains 0x268D75396C0 -> 0x268D7539700 -> 0x268D753AE30 -> 0x268D753AE40 -> 0x268DF21ED20, but owner +0x110 changed from expected 0x2657C80 to live 0x264C688, so treat +0x110 as volatile/weak. Movement remains blocked until fresh API-now vs memory-now proof and ProofOnly pass.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Build a parent-slot/module-hint family classifier from the 575-hit sweep. | Separate structural families from unrelated UI/string/module-hint hits. |
| 2 | Demote owner `+0x110` from hard predicate to volatile/weak clue in future root-search logic. | Live current-PID evidence disproved the older expected RVA. |
| 3 | Compare the 115 live parent-slot-like hits by owner shape. | Finds sibling structures that may reveal a container root. |
| 4 | Search above the top parent-slot-like family, not just the single player parent slot. | The direct parent-of-parent ref is still absent. |
| 5 | Keep `+0x0`, `+0x8`, `+0xE0`, `+0x10 coord pointer` as the stronger owner predicates for now. | These remained true in the live sweep. |
| 6 | Recheck RRAPICOORD/ChromaLink freshness before any proof-pose promotion. | Static-chain prep cannot replace API-now truth. |
| 7 | If live reference returns, run read-only proof-pose with the same-target candidate file. | Converts candidate evidence into proof evidence. |
| 8 | Keep milestone review after each static/proof milestone. | Prevents accidental movement permission creep. |
| 9 | Preserve generated sweep artifacts as candidate-only evidence. | They are useful PC-heavy analysis outputs but not movement truth. |
| 10 | Only promote after restart-stable resolver plus multi-pose API-now agreement. | This is required for a stable static coordinate chain. |
