# ProofOnly Refresh Handoff — Current PID Coordinate Proof

Generated UTC: `2026-05-15T07:53:27+00:00`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch at creation: `main`

## TL;DR

`ProofOnly` was rerun for the current RIFT target after the operator requested `run proofon`. The first attempt failed safely because the existing proof anchor exceeded the 60-second freshness window and the readback sample was unstable. A second no-input ProofOnly run refreshed the proof anchor and passed.

| Field | Current value |
|---|---|
| Target process | `rift_x64` |
| PID | `27552` |
| HWND | `0x3411E2` |
| ProofOnly status | `passed-proof-only` |
| Candidate | `api-family-hit-000001` |
| Proof pointer | `0x27B1ED850C0` |
| Support count | `6` |
| Latest coordinate | `X=7315.03076171875`, `Y=875.1163330078125`, `Z=3050.24462890625` |
| Coordinate recorded UTC | `2026-05-15T07:49:24.4282099Z` |
| Latest ProofOnly generated UTC | `2026-05-15T07:49:25.161515+00:00` |
| Movement sent | `False` |
| Movement attempted | `False` |
| Cheat Engine used | `False` |
| SavedVariables used as live truth | `False` |
| x64dbg used | `false` |

## Current durable state

| Artifact | Path | Notes |
|---|---|---|
| Current proof pointer | `docs/recovery/current-proof-anchor-readback.json` | Updated by the successful ProofOnly run. |
| Latest live-test pointer | `scripts/captures/latest-live-test-run.json` | Points at the successful ProofOnly run. |
| Successful ProofOnly run | `scripts/captures/live-test-ProofOnly-20260515-074836/run-summary.json` | `status=passed-proof-only`; no input. |
| Successful run directory | `scripts/captures/live-test-ProofOnly-20260515-074836` | Full run artifact folder. |
| Successful readback summary | `scripts/captures/proof-anchor-currentpid-27552-readback-summary-20260515-034919.json` | Runtime readback for current proof anchor. |
| Candidate source file | `scripts/captures/family-scan-currentpid-27552-20260515-022029-063377/api-family-vec3-candidates.jsonl` | Source candidate for `api-family-hit-000001`. |
| Current truth JSON | `docs/recovery/current-truth.json` | Validation passed after the ProofOnly refresh; not edited by this handoff. |
| Current truth Markdown | `docs/recovery/current-truth.md` | Not edited by this handoff. |

## Chronological event log

| Step | Event | Evidence | Result |
|---:|---|---|---|
| 1 | Operator requested ProofOnly with `run proofon`. | Chat request. | Treated as `ProofOnly`; no movement profile selected. |
| 2 | Verified repo context and located proof tooling. | `git status`, `rg ProofOnly`, proof scripts under `scripts/`. | Repo was on `main`. |
| 3 | Checked current coordinate recovery status. | `python scripts/coordinate_recovery_status.py --json` | Passed; target was PID `27552` / HWND `0x3411E2`. |
| 4 | Ran ProofOnly attempt 1. | `scripts/captures/live-test-ProofOnly-20260515-074616/run-summary.json` | Failed safely with `failed-internal-error`; no movement, no CE, no x64dbg. |
| 5 | Diagnosed attempt 1. | `scripts/captures/live-test-ProofOnly-20260515-074616/child-outputs/002-capture-proof-pose.json` | Root issue: `proof_anchor_age_out_of_range_seconds:2616.859`; readback was also unstable across samples. |
| 6 | Waited briefly and reran ProofOnly. | `python scripts/live_test.py --profile ProofOnly --pid 27552 --hwnd 0x3411E2 --process-name rift_x64 --no-gui` | Passed. |
| 7 | Successful ProofOnly refreshed current pointer. | `scripts/captures/live-test-ProofOnly-20260515-074836/run-summary.json` | `passed-proof-only`; `movementSent=false`; `movementAttempted=false`. |
| 8 | Ran post-run status/validation. | `coordinate_recovery_status.py`, `validate_current_truth.py`, `git diff --check` | All passed. |
| 9 | Created this handoff. | `docs/handoffs/2026-05-15-0753-proofonly-refresh-currentpid-27552-handoff.md` | Ready to commit with the refreshed proof pointer. |
| 10 | Ran milestone and validation checks after handoff creation. | `coordinate_recovery_status.py`, `validate_current_truth.py`, `riftscan_milestone_review.py`, `git diff --check` | Coordinate status/current-truth/diff checks passed; RiftScan milestone review blocked as expected with `no_supported_candidate_schema` because this proof used a RiftReader-owned candidate file, not a supported RiftScan provider match. |

## Exact command replay

```powershell
cd "C:\RIFT MODDING\RiftReader"
python .\scripts\coordinate_recovery_status.py --json
python .\scripts\live_test.py --profile ProofOnly --pid 27552 --hwnd 0x3411E2 --process-name rift_x64 --no-gui
python .\scripts\coordinate_recovery_status.py --json
python .\scripts\validate_current_truth.py --json
git --no-pager diff --check
git --no-pager status --short
```

## Validation after handoff creation

| Check | Result | Notes |
|---|---|---|
| `python scripts/coordinate_recovery_status.py --json` | Passed | Current target proof remains `current-target-proofonly-passed`. |
| `python scripts/validate_current_truth.py --json` | Passed | No current-truth validation errors/warnings. |
| `python scripts/riftscan_milestone_review.py` | Blocked expected | `no_supported_candidate_schema`; this is a RiftScan-provider strategy gate, not a contradiction of the RiftReader ProofOnly result. |
| `git diff --check` | Passed | No whitespace errors. |

## Safety boundaries preserved

| Boundary | Status |
|---|---|
| Live movement/input | Not used by ProofOnly. |
| Cheat Engine | Not used. |
| x64dbg attach/watchpoints | Not used. Current rule remains offline/read-only unless explicitly changed. |
| Software breakpoints / stepping / tracing | Not approved and not used. |
| SavedVariables live truth | Not used. |
| RiftScan provider writes | Not used by this handoff; consume only existing provider evidence unless separately authorized. |
| Static-chain promotion | Not performed. `0x27B1ED850C0` remains current-PID proof, not restart-stable static truth. |

## Important interpretation

- The first failed ProofOnly run should **not** be used as current proof. It is historical diagnostic evidence only.
- The second run is the current valid proof refresh.
- The current proof pointer `0x27B1ED850C0` is valid for PID `27552` / HWND `0x3411E2` only. If the game restarts or PID/HWND changes, treat it as stale and rerun current-PID family recovery rather than probing this absolute address.
- `docs/recovery/current-proof-anchor-readback.json` is modified by the passed ProofOnly run and should be committed with this handoff.

## Current uncommitted work expected before commit

| Path | Why modified |
|---|---|
| `docs/recovery/current-proof-anchor-readback.json` | Refreshed by successful ProofOnly. |
| `docs/handoffs/2026-05-15-0753-proofonly-refresh-currentpid-27552-handoff.md` | This handoff. |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/handoffs/2026-05-15-0753-proofonly-refresh-currentpid-27552-handoff.md first, then inspect git status and docs/recovery/current-proof-anchor-readback.json. The latest successful ProofOnly is scripts/captures/live-test-ProofOnly-20260515-074836/run-summary.json for PID 27552 / HWND 0x3411E2, candidate api-family-hit-000001 @ 0x27B1ED850C0, movementSent=false. Keep x64dbg offline/read-only unless I explicitly approve live attach/watchpoints in the current turn. Do not treat 0x27B1ED850C0 as restart-stable static truth; if PID/HWND changed, mark it stale and run current-PID family recovery.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Review the commit diff after this handoff is committed. | Confirms only intended proof-refresh documentation changed. |
| 2 | Rerun ProofOnly immediately before any future movement test. | The proof age window is short. |
| 3 | Do not rerun ProofOnly repeatedly unless freshness is needed. | Avoids churn and transient readback failures. |
| 4 | Keep `0x27B1ED850C0` current-PID-only. | It is not static-chain truth. |
| 5 | If ProofOnly fails again once, inspect readback instability and world/player state before escalating. | The first failure looked transient plus expired proof age. |
| 6 | If PID/HWND changes, use current-PID family scan recovery. | Avoids stale absolute-address probing. |
| 7 | Keep x64dbg offline/read-only under the current operator rule. | Reduces crash/recovery risk. |
| 8 | When live x64dbg is eventually approved, watch only the 12-byte XYZ leaf and detach quickly. | Keeps static-chain discovery surgical. |
| 9 | Update `current-truth.md/json` only if you want docs to mirror this exact 07:49 UTC proof refresh. | Current truth validation passed, but those files were not edited by this handoff. |
| 10 | Preserve the failed attempt path as diagnostic-only, not current truth. | It explains the transient failure without polluting current proof. |
