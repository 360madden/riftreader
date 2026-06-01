# RiftReader Handoff — Ghidra evidence surfaced + no-input truth refresh — 2026-06-01 07:48 UTC

# **✅ RESULT — SAFE LOCAL SURFACES REFRESHED, PROMOTION STILL GATED**

This slice made the latest offline Ghidra/static evidence visible in the compact
status and decision packets, refreshed exact-target no-input readbacks, applied a
tracked current-truth refresh from that evidence, and pushed all commits. It did
**not** run the explicit facing/proof-promotion gate.

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Final HEAD | `caaedaa` — `Refresh current truth from no-input readbacks` |
| Target PID / HWND | `41808` / `0x2B0A26` |
| Process start | `2026-06-01T01:50:50.903773Z` |
| Module base | `0x7FF6EE5D0000` |
| Promoted coordinate resolver | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Candidate-facing chain | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` |
| Candidate-facing promotion | `false` — still requires explicit promotion gate |

## Commits in this continuation

| Commit | Change |
|---|---|
| `014eb0b` | Indexed facing promotion-readiness review in the navigation dashboard. |
| `b137dad` | Indexed Ghidra static evidence in the navigation dashboard. |
| `ce52d20` | Surfaced `ghidraStaticEvidence` in compact workflow status. |
| `bb0a0b8` | Surfaced Ghidra evidence in compact decision packet and markdown. |
| `caaedaa` | Refreshed tracked current truth from fresh no-input readbacks/API-now evidence. |

## Current evidence

| Evidence | Result | Path |
|---|---|---|
| Static owner coordinate readback | `passed`; stationary; coordinate `7259.82568359375, 821.4274291992188, 2994.700439453125` | `scripts\captures\static-owner-coordinate-chain-readback-20260601-074133-448811\summary.json` |
| Static owner nav/facing readback | `passed`; yaw `75.17711284220054`, pitch `4.941137747009679`, lookahead `9.962900304948523` | `scripts\captures\static-owner-nav-state-20260601-074144-187124\summary.json` |
| RRAPICOORD/API-now reference | `captured`; API coordinate `7259.830078, 821.429993, 2994.699951` | `scripts\captures\rift-api-reference-currentpid-41808-20260601-074156.json` |
| API-now vs chain-now | `passed`; max abs delta `0.004394406249957683` <= tolerance `0.25` | indexed in `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Offline Ghidra static evidence | `passed`; root refs captured `200`; instructions scanned `8057130`; warning `ghidra-analysis-timeout-project-saved` | `scripts\captures\ghidra-static-analysis-20260601-071020\summary.json` |
| Navigation pointer dashboard | `passed`; freshness `fresh`; stale sources `[]`; generated `2026-06-01T07:42:37Z` | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Current-truth apply | `passed`; applied `2026-06-01T07:43:19Z` from plan generated `2026-06-01T07:43:14Z` | `.riftreader-local\current-truth-refresh-apply\latest\summary.json` |

## Current state

| Item | State |
|---|---|
| Coordinate resolver | Promoted and current for PID `41808`; latest API-now validation is current in tracked truth. |
| Ghidra evidence | Indexed in navigation dashboard, compact workflow status, and compact decision packet. It is support evidence only and does not promote anything. |
| Candidate-facing target | Review-ready but candidate-only; promotion still requires an explicit gate and immediate fresh pre-promotion readbacks. |
| Decision packet | `.riftreader-local\decision-packet\latest\decision-packet-compact.json` reports no stageable paths and next safe action `compact-workflow-status`. |
| Workflow status | `.riftreader-local\workflow-status\20260601-074448Z\compact-sitrep.json` reports clean Git and fresh navigation dashboard sources. |

## Safety boundary

| Boundary | State |
|---|---|
| New live input / movement | None sent by this slice |
| Target memory read | Yes, read-only static owner/API capture only |
| Target memory write | None |
| Current-truth write | Yes: tracked refresh only, no promotion |
| Proof/facing/actor promotion | No |
| x64dbg / Cheat Engine | Not used |
| Provider writes | None |
| SavedVariables as live truth | Not used |
| Git push | Pushed to `origin/main` |

## Validation

| Check | Result |
|---|---|
| Status packet compile/tests | `python -m py_compile tools\riftreader_workflow\status_packet.py scripts\test_status_packet.py`; `python -m unittest scripts.test_status_packet` passed |
| Decision packet tests | `python -m unittest scripts.test_decision_packet` passed |
| Decision packet safe checks | `python tools\riftreader_workflow\decision_packet.py --run-safe-checks --json` passed |
| Current truth JSON | `python -m json.tool docs/recovery/current-truth.json` passed |
| Sensitive artifact scans | working and staged scans passed for each committed slice |
| Targeted ledger | `.riftreader-local\validation-runs\20260601-073502-959650\summary.md` |
| Targeted ledger | `.riftreader-local\validation-runs\20260601-073934-119746\summary.md` |
| Targeted ledger | `.riftreader-local\validation-runs\20260601-074359-813649\summary.md` |
| Handoff doc diff check | `.riftreader-local\validation-runs\20260601-074740-284528\summary.md` |

## Current next action

The next meaningful action is an explicit candidate-facing promotion/proof gate.
Before that gate, refresh exact-target static coordinate, nav/facing, and
RRAPICOORD/API-now readbacks again and verify PID/HWND/process-start/module-base.
Do not treat the dashboard, readiness review, or Ghidra evidence as promotion.
