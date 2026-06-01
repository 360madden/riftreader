# RiftReader Handoff — current-truth apply and gate-aware status wiring — 2026-06-01 06:17 UTC

## ✅ Current truth

| Item | Value |
|---|---|
| Branch / base HEAD | `main` at `d1a78e4` before this slice |
| Current target | PID `41808`, HWND `0x2B0A26`, process start `2026-06-01T01:50:50.903773Z`, module base `0x7FF6EE5D0000` |
| Tracked truth update | `docs/recovery/current-truth.json` applied from `.riftreader-local\current-truth-refresh-plan\latest\proposed-current-truth.json` |
| Apply summary | `.riftreader-local\current-truth-refresh-apply\latest\summary.json` |
| Backup before apply | `.riftreader-local\current-truth-refresh-apply\latest\current-truth-before-apply.json` |
| Apply boundary | No live input, movement, target-memory write, debugger/CE, provider write, Git mutation by helper, proof promotion, actor-chain promotion, or facing promotion |

The apply helper validated the dry-run proposal (`updateCount=34`) before writing tracked truth. The applied tracked truth now points to the latest exact-target no-input coordinate/nav readbacks and API-now match:

| Evidence | Path / value |
|---|---|
| Static coordinate readback | `scripts\captures\static-owner-coordinate-chain-readback-20260601-054735-005823\summary.json` |
| Nav-state readback | `scripts\captures\static-owner-nav-state-20260601-054735-766761\summary.json` |
| API-now reference | `scripts\captures\rift-api-reference-currentpid-41808-20260601-054745.json` |
| Max abs API-vs-chain delta | `0.004416406250129512` <= tolerance `0.25` |

## ✅ Workflow/status wiring added

| Surface | What changed |
|---|---|
| `tools/riftreader_workflow/current_truth_refresh_apply.py` | New explicit apply gate; dry-run by default; `--apply` writes tracked current truth only after validating plan safety flags and proposal identity. |
| `scripts/riftreader-current-truth-refresh-apply.cmd` | Thin launcher for the apply helper. |
| `tools/riftreader_workflow/navigation_pointer_discovery.py` | Now indexes three proof-support gates: three-pose route-progress gate, restart/relog survival packet, and turn-forward progress proof. |
| `tools/riftreader_workflow/status_packet.py` | Compact status now surfaces current-truth apply results, proof gate readiness, and the correct next action when gates are packaged. |
| `tools/riftreader_workflow/tool_catalog.py` | Catalog/bridge commands now include the apply gate and report-only facing gate helpers. |
| `scripts/riftreader-facing-target-three-pose-gate.cmd` / `scripts/riftreader-facing-target-restart-survival-packet.cmd` | Thin paste-safe launchers for existing report-only Python helpers. |

## ✅ Gate packet state

| Packet | Status | Path |
|---|---|---|
| Three-pose route-progress gate | `passed`; `3/3` poses; min progress `1.515752059073872` | `scripts\captures\facing-target-three-pose-gate-20260601-054258-066521\summary.json` |
| Restart/relog survival packet | `passed`; distinct process epochs; offsets stable | `scripts\captures\facing-target-restart-survival-packet-20260601-054826-920485\summary.json` |
| Turn-forward progress proof | `passed`; route progress `1.5254744940722471` | `scripts\captures\static-owner-turn-forward-experiment-20260601-054700-011212\summary.json` |

Navigation pointer discovery now reports `facingTarget = candidate-only-gates-packaged-requires-review`. This is **not** a promotion. The required next step is a separate candidate-facing promotion-readiness review packet that consumes the gate packets and static-root/source-site evidence.

## Validation

| Check | Result |
|---|---|
| `python -m py_compile ...` | Passed for changed Python helpers/tests |
| `python -m unittest scripts.test_current_truth_refresh_apply scripts.test_navigation_pointer_discovery scripts.test_tool_catalog scripts.test_status_packet` | Passed: `31` tests |
| Navigation pointer discovery regen | Passed; freshness `fresh`, no stale sources, proof gates all `passed` |
| Workflow status regen | Passed; no blockers/warnings after launcher inspection refresh |
| Validation ledger | `.riftreader-local\validation-runs\20260601-062452-801220\summary.md`; targeted tests passed in `1.770s` |

## Current blocker / next action

No local workflow blocker remains. Next safe action is to build a **separate candidate-facing promotion-readiness review packet** from the three-pose gate, restart/relog packet, turn-forward proof, and Ghidra/static-root source-site evidence. Keep `owner+0x30C/+0x310/+0x314` candidate-only unless that review passes and an explicit promotion gate is opened.
