# 2026-05-13 19:31 EDT — Parent-slot root signature + reference freshness blocker

## ✅ Result

Continued safely without movement/input/CE. Fresh reference proof remains blocked, so the work pivoted to the highest-signal offline/static-chain action: packaging the current parent-slot/owner evidence into a root-search signature packet.

## Current live target / safety

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Movement | **Blocked** |
| Cheat Engine | **Not used** |
| x64dbg | **Not launched** |
| Input/reloadui sent | **No** |
| Candidate status | **Candidate-only** |

## Fresh reference recheck

| Surface | Artifact | Verdict |
|---|---|---|
| RRAPICOORD runtime marker | `scripts/captures/reference-currentpid-2928-manual-20260513-keepgoing/rift-api-reference-scan-currentpid-2928-20260513-231902.json` | Blocked: current scan found partial/static `RRAPICOORD1` text but no usable `status=pass`, `source=rift-api`, `savedVariablesUse=none`, numeric `x/y/z` marker. |
| ChromaLink world-state | `scripts/captures/chromalink-world-state-reference-20260513-232015-658921/summary.json` | Blocked: endpoint reachable, but `player.position` stale at `2026-05-13T22:55:23.0397648+00:00`; freshness-clean player position is unavailable. |

**Important:** endpoint/process reachability is not coordinate freshness proof. Do not promote candidates or run movement from these stale/partial reference values.

## What changed

| Area | Change |
|---|---|
| Root-search packet helper | Added `scripts/rift_live_test/parent_slot_root_signature_packet.py`. |
| Operator wrapper | Added `scripts/parent_slot_root_signature_packet.py`. |
| Tests | Added `scripts/test_parent_slot_root_signature_packet.py`. |
| Docs | Updated `docs/recovery/current-truth.md` with the reference blocker and new root-signature packet. |

## Generated root-search packet

| Field | Value |
|---|---|
| Artifact | `scripts/captures/parent-slot-root-signature-packet-20260513-232733-606293/summary.json` |
| Status | `passed` |
| Root gap above | `0x268D7539700` |
| Selected module hint | `0x268D75396C0 = rift_x64.exe+0x263E950` (`-0x40` from parent slot) |
| Parent slot relation | `0x268D7539700 -> 0x268D753AE30` |
| Owner coord-pointer relation | `0x268D753AE40 -> 0x268DF21ED20` |
| Owner module fields | `+0x0=0x26AAE70`, `+0x8=0x272DBC0`, `+0xE0=0x263E950`, `+0x110=0x2657C80` |
| Safety verdict | `candidateOnly=true`, `movementProofEligible=false` |

## Validation

| Command | Result |
|---|---|
| `python -m py_compile scripts\rift_live_test\parent_slot_root_signature_packet.py scripts\parent_slot_root_signature_packet.py scripts\test_parent_slot_root_signature_packet.py` | Passed |
| `python scripts\test_parent_slot_root_signature_packet.py -v` | Passed: 3 tests |
| `python scripts\parent_slot_root_signature_packet.py ... --json` | Passed and generated the packet above |
| `python scripts\riftscan_milestone_review.py --pid 2928 --hwnd 0xC0994 --process-name rift_x64 --write-summary --write-markdown --compact-json` | Passed; wrote `scripts/captures/riftscan-milestone-review-20260513-232903.json`, verdict `ready-for-read-only-proof`, movement still false. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/recovery/current-truth.md and this handoff first. Current target remains rift_x64 PID 2928 HWND 0xC0994. Do not use CE, do not send movement/input, and do not treat stale RRAPICOORD/ChromaLink coordinates as proof. Fresh reference is currently blocked: RRAPICOORD scan only found partial/static marker text, and ChromaLink player.position is stale. Continue offline/static-chain work from scripts/captures/parent-slot-root-signature-packet-20260513-232733-606293/summary.json. Root gap is above parent slot 0x268D7539700; known chain is 0x268D75396C0 module hint 0x263E950 -> parent slot 0x268D7539700 -> owner 0x268D753AE30 -> coord-pointer storage 0x268D753AE40 -> coord candidate 0x268DF21ED20. Movement remains blocked until fresh API-now vs memory-now proof and same-target ProofOnly pass.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Restore/fix freshness-clean RRAPICOORD or ChromaLink player position before proof promotion. | Candidate readback cannot become movement truth without a fresh reference surface. |
| 2 | Use the root-signature packet to guide broad family/container scans above `0x268D7539700`. | The current chain gap is above the parent slot, not at the coord offset itself. |
| 3 | Batch-check sibling parent slots with the same predicates. | Confirms which fields are structural instead of player-only coincidence. |
| 4 | Keep `0x263E950` as a search seed only. | It is a strong module hint, not static-chain proof by itself. |
| 5 | Build a resolver candidate only after a module/static or restart-stable container owner is found. | Stable future discovery requires a chain, not an absolute heap address. |
| 6 | Require multi-pose API-now vs chain-now agreement before promotion. | Prevents offset-copy or stale snapshot promotion. |
| 7 | Re-run `scripts/riftscan_milestone_review.py` after any proof/source milestone. | Keeps movement gating and provider/consumer boundaries honest. |
| 8 | Preserve stale-cache warnings in readback/proof summaries. | Prevents the old PID `57656` proof cache from shadowing PID `2928`. |
| 9 | Document any live provider freshness fix immediately in `current-truth.md`. | Stops stale provider state from being reinterpreted later. |
| 10 | Only run `ProofOnly` after a fresh same-target proof anchor exists. | Same-target proof gate remains mandatory before navigation or movement. |
