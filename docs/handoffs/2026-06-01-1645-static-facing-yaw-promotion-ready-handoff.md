# RiftReader Handoff — static facing/yaw promotion-ready evidence — 2026-06-01 16:45 UTC

## Verdict

The static owner facing/yaw lane is ready for an explicit promotion-gate review.
No facing/yaw/actor-chain/proof promotion was performed in this slice. Git push
was not performed.

## Repo state

| Field | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| HEAD | `824c485` — `Index nested facing comparison evidence` |
| Remote state | `main...origin/main [ahead 1]` |
| Latest prior handoff | `docs/handoffs/2026-06-01-0800-window-tool-audit-readback-refresh-handoff.md` |

## Target identity

| Field | Value |
|---|---|
| Process | `rift_x64` |
| PID | `41808` |
| HWND | `0x2B0A26` |
| Process start | `2026-06-01T01:50:50.903773Z` |
| Module base | `0x7FF6EE5D0000` |
| Window | visible RIFT client `640x360` |

Latest launcher inspection:
`.riftreader-local/launcher-inspection/run-20260601-164142-429284/launcher-inspection-summary.json`.

## Proven/promoted coordinate resolver

| Field | Value |
|---|---|
| Coordinate chain | `[rift_x64+0x32EBC80]+0x320/+0x324/+0x328` |
| Latest coordinate readback | `scripts/captures/static-owner-coordinate-chain-readback-20260601-164141-279659/summary.json` |
| Coordinate | `x=7259.82568359375`, `y=821.4274291992188`, `z=2994.700439453125` |
| API-now reference | `scripts/captures/rift-api-reference-currentpid-41808-20260601-164156.json` |
| API vs chain max abs delta | `0.004394406249957683` |

## Static facing/yaw candidate

| Field | Value |
|---|---|
| Candidate chain | `[rift_x64+0x32EBC80]+0x30C/+0x310/+0x314` |
| Yaw formula | `atan2(owner+0x314 - owner+0x328, owner+0x30C - owner+0x320)` |
| Latest nav readback | `scripts/captures/static-owner-nav-state-20260601-164141-330587/summary.json` |
| Latest yaw | `80.82343415281247` |
| Planar lookahead | `9.962959413453623` |
| Promotion state | candidate-only; ready for explicit gate review |

## Fresh evidence packet

| Evidence | Path / value |
|---|---|
| Live camera-yaw multipose report | `scripts/captures/static-owner-camera-yaw-multipose-report-20260601-163443-380621/summary.json` |
| Nested facing comparison now indexed | `scripts/captures/static-owner-camera-yaw-classification-20260601-163407-394774/static-owner-facing-comparison-20260601-163413-934652/summary.json` |
| Dashboard | `.riftreader-local/navigation-pointer-discovery/latest/summary.json` |
| Latest readiness review | `scripts/captures/facing-target-promotion-readiness-review-20260601-164224-775550/summary.json` |
| Source-site review doc | `docs/recovery/ghidra-facing-coordinate-source-site-review-2026-06-01.md` |
| Current-truth dry-run plan | `.riftreader-local/current-truth-refresh-plan/latest/summary.json` |

Camera-yaw pack results:

| Stimulus | Signed yaw delta | Classification |
|---|---:|---|
| right `160px` | `32.46881501641559` | `visual-and-static-yaw-changed` |
| left `320px` | `-60.70561869415195` | `visual-and-static-yaw-changed` |
| right `160px` | `33.88312498834827` | `visual-and-static-yaw-changed` |

Dashboard state after the nested-artifact indexing fix:

| Field | Value |
|---|---|
| Status | `passed` |
| Candidate-facing status | `candidate-only` |
| Facing offset | `0x30C` |
| Fresh facing comparison max yaw delta | `33.88312498834827` |
| Coordinate drift | `0.0` |
| Promotion readiness | `review-passed-awaiting-explicit-promotion-gate-and-fresh-readback` |
| Stale sources | `currentTruth`, `familySnapshot` |

`currentTruth` is stale only because the latest truth-refresh plan is dry-run.
Applying tracked current truth remains a separate gate and was not done here.

## Code/doc changes already committed

Commit `824c485`:

- `tools/riftreader_workflow/navigation_pointer_discovery.py` now recursively
  finds nested `static-owner-facing-comparison-*` summaries, so live camera-yaw
  child evidence can refresh the dashboard facing comparison.
- `scripts/test_navigation_pointer_discovery.py` adds regression coverage for
  nested facing-comparison discovery.
- `docs/recovery/ghidra-facing-coordinate-source-site-review-2026-06-01.md`
  documents the latest source-site, live yaw, and readiness evidence.

## Validation already run

| Command | Result |
|---|---|
| `python scripts/test_navigation_pointer_discovery.py` | passed, 14 tests |
| `python tools/riftreader_workflow/navigation_pointer_discovery.py --self-test --json` | passed |
| `python -m py_compile tools/riftreader_workflow/navigation_pointer_discovery.py scripts/test_navigation_pointer_discovery.py` | passed |
| `git --no-pager diff --check` | passed; CRLF warnings only |
| `cmd /c scripts/riftreader-sensitive-artifact-scan.cmd --staged --json` | passed before commit |
| `cmd /c scripts/riftreader-facing-target-promotion-readiness-review.cmd --json` | passed |
| `cmd /c scripts/riftreader-workflow-status.cmd --compact-json --write` | passed |
| `cmd /c scripts/riftreader-decision-packet.cmd --compact-json --write` | passed |

## Safety boundary

| Boundary | Status |
|---|---|
| Live movement / mouse-look | Performed earlier with explicit approval for the 16:33 camera-yaw pack |
| Process attach / debugger | Approved by operator, but not used in this slice |
| Target memory writes | No |
| Cheat Engine | No |
| Provider writes | No |
| Current-truth apply | No; dry-run plan only |
| Facing/yaw/actor/proof promotion | No |
| Git push | No |

## Resume checklist

1. Run `git --no-pager status --short --branch` and confirm `main` is still
   ahead by `824c485`.
2. If promotion is explicitly approved, first refresh exact-target
   coordinate/nav/API readbacks again:
   - `cmd /c scripts\static-owner-coordinate-chain-readback.cmd --use-current-truth --samples 3 --interval-seconds 0.20 --expect-stationary --json`
   - `cmd /c scripts\static-owner-nav-now.cmd`
   - `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\capture-rift-api-reference-coordinate.ps1 -ProcessId 41808 -TargetWindowHandle 0x2B0A26 -Json`
3. Rebuild dashboard and readiness packet:
   - `cmd /c scripts\riftreader-navigation-pointer-discovery.cmd --json --write`
   - `cmd /c scripts\riftreader-facing-target-promotion-readiness-review.cmd --json`
4. Only then run the separate explicit facing/yaw promotion gate if approved.
5. Do not push until explicit Git push approval is given.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Ask/receive explicit facing/yaw promotion-gate approval. | Evidence is ready, but promotion remains gated. |
| 2 | Refresh exact-target coordinate/nav/API readbacks immediately before the gate. | Keeps pre-promotion evidence current. |
| 3 | Rerun promotion-readiness review after the fresh readbacks. | Confirms no target drift. |
| 4 | Run the dedicated promotion gate only if approved. | Avoids accidental promotion from dashboard or docs. |
| 5 | If promotion is not approved, keep chain candidate-only. | Maintains safety boundary. |
| 6 | Optionally approve current-truth apply separately. | Current truth is stale but a dry-run plan is ready. |
| 7 | Keep `owner+0x300` support-only. | It changes with camera-yaw but is not direct yaw truth. |
| 8 | Keep `owner+0x304` turn-rate candidate-only. | It needs its own proof lane. |
| 9 | Push `824c485` only after explicit push approval. | Branch is ahead by one local commit. |
| 10 | Avoid debugger attach unless promotion review finds a specific unresolved contradiction. | Current evidence path did not require attach. |
