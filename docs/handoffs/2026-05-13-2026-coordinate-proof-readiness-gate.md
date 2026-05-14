# 2026-05-13 20:26 EDT — Coordinate proof readiness gate

## ✅ Result

Added a fail-closed coordinate proof readiness gate. It combines the reference freshness watchdog and latest milestone review so stale reference truth blocks proof/readback even when a same-target candidate exists.

No movement, input, reloadui, CE, x64dbg, breakpoints, provider writes, proof promotion, target memory reads, or target memory writes were used by the gate.

## Current target / safety

| Field | Value |
|---|---|
| Process | `rift_x64.exe` |
| PID | `2928` |
| HWND | `0xC0994` |
| Movement/navigation | **Blocked** |
| Read-only proof/readback | **Blocked by readiness gate** |
| Fresh reference | **Blocked** |
| CE/x64dbg | **Not used** |
| Input/reloadui | **Not sent** |

## What changed

| File | Change |
|---|---|
| `scripts/rift_live_test/coordinate_proof_readiness_gate.py` | New fail-closed gate that composes reference watchdog + milestone review into a single proof-readiness verdict. |
| `scripts/coordinate_proof_readiness_gate.py` | Thin Python entry point. |
| `scripts/test_coordinate_proof_readiness_gate.py` | Unit tests for stale-reference blocking, pass condition, and target matching. |
| `docs/recovery/current-truth.md` | Updated with the readiness gate result. |

## Gate result

| Artifact | Verdict |
|---|---|
| `scripts/captures/coordinate-proof-readiness-gate-20260514-002618-599647/summary.json` | `blocked-coordinate-proof-readiness` |
| Reference input | `scripts/captures/reference-freshness-watchdog-20260514-002036-448433/summary.json`; `blocked-fresh-reference-unavailable`. |
| Milestone input | `scripts/captures/riftscan-milestone-review-20260514-002147.json`; `ready-for-read-only-proof`, but only as a strategy/read-only gate. |

Blocked fields:

| Field | Value |
|---|---|
| `readOnlyProofAllowed` | `false` |
| `movementAllowed` | `false` |
| Primary blockers | stale/not-healthy ChromaLink; no usable RRAPICOORD marker |

## Current interpretation

This closes the ambiguity between two layers:

| Layer | Meaning |
|---|---|
| Milestone review | A same-target candidate exists and provider boundaries are safe. |
| Reference watchdog | Fresh API/reference truth is unavailable. |
| Coordinate proof readiness gate | Final answer: **do not run proof/readback or movement yet**. |

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
| `python -m py_compile scripts/rift_live_test/coordinate_proof_readiness_gate.py scripts/coordinate_proof_readiness_gate.py scripts/test_coordinate_proof_readiness_gate.py` | Passed |
| `python scripts/test_coordinate_proof_readiness_gate.py -v` | Passed: `3` tests |
| `python scripts/coordinate_proof_readiness_gate.py --target-pid 2928 --target-hwnd 0xC0994 --process-name rift_x64 --json` | Blocked safely with `blocked-coordinate-proof-readiness`. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/recovery/current-truth.md and docs/handoffs/2026-05-13-2026-coordinate-proof-readiness-gate.md first. Current target is rift_x64 PID 2928 HWND 0xC0994. Do not use CE/x64dbg, do not send movement/input/reloadui, and do not promote stale reference data. Run python scripts/reference_freshness_watchdog.py --target-pid 2928 --target-hwnd 0xC0994 --process-name rift_x64 --json, then python scripts/coordinate_proof_readiness_gate.py --target-pid 2928 --target-hwnd 0xC0994 --process-name rift_x64 --json before proof/readback. Latest readiness gate scripts/captures/coordinate-proof-readiness-gate-20260514-002618-599647/summary.json blocks read-only proof and movement because fresh reference is unavailable. Clean priority lane is exhausted via scripts/captures/priority-scan-exhaustion-report-20260514-001700-212349/summary.json. Known player chain remains 0x268D75396C0 -> 0x268D7539700 -> 0x268D753AE30 -> 0x268D753AE40 -> 0x268DF21ED20. Movement remains blocked until fresh API-now/reference vs memory-now proof and same-target ProofOnly pass.
```

## Top 10 next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Use `coordinate_proof_readiness_gate.py` before proof/readback/movement. | It is now the combined fail-closed truth gate. |
| 2 | Refresh/fix ChromaLink live telemetry if provider edits are authorized. | Stale ChromaLink is the strongest blocker. |
| 3 | Refresh/fix RRAPICOORD marker emission if addon/provider work is authorized. | RRAPICOORD has hits but no usable coordinate marker. |
| 4 | Once readiness gate passes, run same-target read-only proof/readback. | Converts candidate evidence into live proof. |
| 5 | Re-run `ProofOnly` only after read-only proof/readback passes. | Keeps movement gated. |
| 6 | Do not rescan the exhausted clean priority lane. | It has already produced zero module/static hits. |
| 7 | If offline-only work continues, use lower-priority batch scans with exhaustion reports. | Maintains PC-heavy, AI-light workflow. |
| 8 | Preserve the known player chain as candidate-only root-gap evidence. | It remains the strongest player-linked structure. |
| 9 | Re-run milestone review after target/ref changes. | Maintains provider/read-only/no-CE boundaries. |
| 10 | Promote only after fresh reference, memory-now agreement, `ProofOnly`, and restart validation. | Required for stable static coordinate chain. |
