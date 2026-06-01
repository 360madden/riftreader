# RiftReader Handoff — window-tool audit classification + fresh pre-promotion readbacks — 2026-06-01 08:00 UTC

# **✅ RESULT — SAFE LOCAL AUDIT HARDENED, PROMOTION STILL GATED**

This slice hardened the live-input surface audit classification for the repo
window/control primitive, refreshed current exact-target no-input evidence, and
left candidate-facing promotion behind the required explicit gate.

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Final HEAD | `e2d8a09` — `Classify repo window tool in input audit` |
| Target PID / HWND | `41808` / `0x2B0A26` |
| Process start | `2026-06-01T01:50:50.903773Z` |
| Module base | `0x7FF6EE5D0000` |
| Promoted coordinate resolver | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Candidate-facing chain | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` |
| Candidate-facing promotion | `false` — still requires explicit promotion gate |

## Commits in this continuation

| Commit | Change |
|---|---|
| `e2d8a09` | Classified `tools\RiftReader.WindowTools\Program.cs` as an explicit repo window/control primitive in the live-input surface audit and added test coverage. |

## Current evidence

| Evidence | Result | Path |
|---|---|---|
| Static owner coordinate readback | `passed`; stationary; coordinate `7259.82568359375, 821.4274291992188, 2994.700439453125` | `scripts\captures\static-owner-coordinate-chain-readback-20260601-075735-998580\summary.json` |
| Static owner nav/facing readback | `passed`; yaw `75.17711284220054`, pitch `4.941137747009679`, lookahead `9.962900304948523` | `scripts\captures\static-owner-nav-state-20260601-075736-800286\summary.json` |
| RRAPICOORD/API-now reference | `captured`; API coordinate `7259.830078, 821.429993, 2994.699951` | `scripts\captures\rift-api-reference-currentpid-41808-20260601-075737.json` |
| API-now vs chain-now | `passed`; max abs delta `0.004394406249957683` <= tolerance `0.25` | indexed in `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Candidate-facing readiness review | `passed`; `reviewPassed=true`; `promotionAllowed=false`; `promotionPerformed=false`; `explicitPromotionGateRequired=true` | `scripts\captures\facing-target-promotion-readiness-review-20260601-075836-835459\summary.json` |
| Navigation pointer dashboard | `passed`; freshness `fresh`; stale sources `[]`; generated `2026-06-01T07:58:38Z` | `.riftreader-local\navigation-pointer-discovery\latest\summary.json` |
| Compact workflow status | `passed`; clean Git at `e2d8a09`; generated `2026-06-01T07:58:39Z` | `.riftreader-local\workflow-status\20260601-075839Z\compact-sitrep.json` |

## Current state

| Item | State |
|---|---|
| Coordinate resolver | Promoted and current for PID `41808`; latest API-now validation remains within tolerance. |
| Window/control primitive audit | `tools\RiftReader.WindowTools\Program.cs` is now classified as `repo-window-tool-input-capable` with disposition `repo-window-tool-explicit-target-only`. |
| Candidate-facing target | Review-ready but candidate-only; promotion still requires an explicit gate and immediate fresh pre-promotion readbacks. |
| Decision packet | `.riftreader-local\decision-packet\latest\decision-packet-compact.json` reports no stageable paths and next safe action `compact-workflow-status`. |
| Workflow status | `.riftreader-local\workflow-status\20260601-075839Z\compact-sitrep.json` reports clean Git and fresh navigation dashboard sources. |

## Safety boundary

| Boundary | State |
|---|---|
| New live input / movement | None sent by this slice |
| Target memory read | Yes, read-only static owner/API capture only |
| Target memory write | None |
| Current-truth write | None in this slice |
| Proof/facing/actor promotion | No |
| x64dbg / Cheat Engine | Not used |
| Provider writes | None |
| SavedVariables as live truth | Not used |
| Git push | Pushed to `origin/main` |

## Validation

| Check | Result |
|---|---|
| Audit helper compile | `python -m py_compile scripts\live_input_surface_audit.py scripts\test_live_input_surface_audit.py` passed |
| Audit tests | `python -m unittest scripts.test_live_input_surface_audit` passed; `10` tests |
| Live-input audit rerun | `python scripts\live_input_surface_audit.py --json` passed |
| Sensitive artifact scan | `scripts\riftreader-sensitive-artifact-scan.cmd --staged --json` passed; `0` findings |
| Diff check | `git --no-pager diff --cached --check` passed before commit |
| Navigation/status refresh | `scripts\riftreader-navigation-pointer-discovery.cmd --json --write`, workflow status, and decision packet passed |

## Current next action

The next meaningful action is an explicit candidate-facing promotion/proof gate.
Before that gate, refresh exact-target static coordinate, nav/facing, and
RRAPICOORD/API-now readbacks again and verify PID/HWND/process-start/module-base.
Do not treat the dashboard, readiness review, or Ghidra evidence as promotion.
