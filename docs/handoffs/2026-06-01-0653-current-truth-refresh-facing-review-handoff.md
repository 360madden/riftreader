# RiftReader Handoff — fresh current-truth refresh + facing review — 2026-06-01 06:53 UTC

# **✅ RESULT — CURRENT TRUTH REFRESHED, FACING STILL CANDIDATE-ONLY**

This slice refreshed exact-target current-PID evidence, applied tracked current truth from the validated dry-run plan, regenerated the navigation dashboard, and recorded the latest candidate-facing review packet. It did **not** promote facing/turn-rate/actor truth.

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Base HEAD | `b2b71dc` — `Add facing promotion readiness review packet` |
| Target PID / HWND | `41808` / `0x2B0A26` |
| Process start | `2026-06-01T01:50:50.903773Z` |
| Module base | `0x7FF6EE5D0000` |
| Promoted coordinate resolver | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Candidate-facing chain | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` |
| Candidate-facing promotion | `false` — still gated |

## What changed

| Surface | Change |
|---|---|
| `docs\recovery\current-truth.json` | Refreshed to the 06:48 static readback and 06:49 API-now reference. |
| `docs\HANDOFF.md` | Added this resume section as the newest compact handoff. |
| `docs\handoffs\2026-06-01-0653-current-truth-refresh-facing-review-handoff.md` | New durable resume handoff for this slice. |

## Fresh evidence

| Evidence | Result | Path |
|---|---|---|
| Static owner coordinate readback | `passed`; stationary; coordinate `7259.82568359375, 821.4274291992188, 2994.700439453125` | `scripts\captures\static-owner-coordinate-chain-readback-20260601-064834-659174\summary.json` |
| Static owner nav/facing readback | `passed`; yaw `75.17711284220054`, pitch `4.941137747009679`, lookahead `9.962900304948523` | `scripts\captures\static-owner-nav-state-20260601-064844-619041\summary.json` |
| RRAPICOORD/API-now reference | `passed`; API coordinate `7259.8301, 821.43, 2994.7` | `scripts\captures\rift-api-reference-currentpid-41808-20260601-064857.json` |
| API-now vs chain-now | `passed`; max abs delta `0.004416406250129512` <= tolerance `0.25` | indexed in `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Current-truth dry-run plan | `passed`; update count `32`; generated `2026-06-01T06:50:13Z` | `.riftreader-local\current-truth-refresh-plan\latest\summary.json` |
| Current-truth apply | `passed`; applied `2026-06-01T06:56:04Z` | `.riftreader-local\current-truth-refresh-apply\latest\summary.json` |
| Navigation pointer dashboard | `passed`; freshness `fresh`; stale sources `[]`; generated `2026-06-01T06:53:05Z` | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Candidate-facing review packet | `passed`; verdict `candidate-facing-review-ready-for-explicit-promotion-gate` | `scripts\captures\facing-target-promotion-readiness-review-20260601-064955-374586\summary.json` |

## Current state

| Item | State |
|---|---|
| Coordinate resolver | Promoted and current for PID `41808`; no stale dashboard sources after the 06:53 refresh. |
| Candidate-facing target | Review-ready but candidate-only; `promotionAllowed=false`, `promotionPerformed=false`, `explicitPromotionGateRequired=true`, `freshPrePromotionReadbackRequired=true`. |
| Movement gate status | Current truth says movement gate is allowed only with exact PID/HWND/process-start/module-base re-check and fresh static-chain readback before input. |
| Next gated boundary | Any facing promotion, proof promotion, actor-chain promotion, debugger/CE attach, or new live movement/input must remain separate from this report-only/truth-refresh slice. |

## Safety boundary

| Boundary | State |
|---|---|
| New live input / movement | None sent by this slice |
| Target memory read by apply/review helpers | No |
| Current-truth write | Yes: tracked refresh only, no promotion |
| Proof/facing/actor promotion | No |
| x64dbg / Cheat Engine | Not used |
| Provider writes | None |
| SavedVariables as live truth | Not used |
| Git mutation by helpers | None |

## Validation

| Check | Result |
|---|---|
| Python compile | `python -m py_compile scripts\facing_target_promotion_readiness_review.py tools\riftreader_workflow\status_packet.py tools\riftreader_workflow\tool_catalog.py scripts\test_facing_target_promotion_readiness_review.py scripts\test_status_packet.py scripts\test_tool_catalog.py scripts\test_navigation_pointer_discovery.py` passed |
| Targeted validation ledger | `.riftreader-local\validation-runs\20260601-065540-434458\summary.md`; targeted unittest suite passed in `2.776s` |
| Review helper self-test | `cmd /c scripts\riftreader-facing-target-promotion-readiness-review.cmd --self-test --json` passed |
| Tool catalog self-test | `cmd /c scripts\riftreader-tool-catalog.cmd --self-test` passed |
| Current-truth apply gate | `cmd /c scripts\riftreader-current-truth-refresh-apply.cmd --apply --json` passed; no proof/facing/actor promotion |
| Workflow status | `cmd /c scripts\riftreader-workflow-status.cmd --compact-json --write` passed; `.riftreader-local\workflow-status\20260601-065648Z\compact-sitrep.json` reports latest handoff and fresh navigation dashboard |

## Current next action

Refresh exact-target static/nav/API readbacks immediately before any explicit facing-promotion gate, then run that gate as a separate operation. Do not promote facing/turn-rate/actor truth from the review packet alone.
