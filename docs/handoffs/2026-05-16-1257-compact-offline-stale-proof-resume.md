# Compact handoff — offline stale proof and static-chain resume

Generated UTC: `2026-05-16T16:57:11Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

The repo is clean and pushed at `e9087ff 2026-05-16 12:48:32 -0400 Record offline restart stale proof state`. The prior coordinate proof for PID `27552` / HWND `0x3411E2` is now intentionally blocked as stale (`blocked-target-drift`) because the game/Codex session closed and no live `rift_x64` process was available during the offline cleanup. Movement is blocked. Yesterday's offline static-chain analysis is preserved in git and should be treated as candidate-only evidence.

## Repo state

| Field | Value |
|---|---|
| `git status --short --branch` | `## main...origin/main` |
| `origin/main...HEAD` | `0	0` |
| HEAD | `e9087ff 2026-05-16 12:48:32 -0400 Record offline restart stale proof state` |
| Latest handoff before this | `docs/handoffs/2026-05-16-1246-offline-restart-stale-proof-handoff.md` |
| Current status command | `blocked / ['live-target-not-running:rift_x64'] / livePids=[]` |

## Current proof/truth state

| Field | Value |
|---|---|
| Current proof file | `docs/recovery/current-proof-anchor-readback.json` |
| Current proof status | `blocked-target-drift` |
| Proof target in blocker | PID `27552` / HWND `0x3411E2` / process `rift_x64` |
| Movement allowed | `False` |
| Latest validation status | `blocked-target-drift` |
| Latest ProofOnly status | `blocked-target-drift` |
| Current coordinate | `None` |
| Current truth | `docs/recovery/current-truth.md` + `docs/recovery/current-truth.json` |
| Current truth status | `no_current_candidate_movement_blocked_reacquisition_required` |
| Current blockers | `No live rift_x64 process was detected during offline recovery; current coordinate proof is blocked.; Prior PID 27552 / HWND 0x3411E2 proof pointer is historical only after game/Codex close.; Load character/world, collect fresh API/runtime truth, and rerun current-PID recovery before any ProofOnly/movement claims.; Static owner/source-chain provenance remains unresolved and candidate-only.` |

## Historical/stale anchor preserved

| Field | Value |
|---|---|
| Stale candidate | `api-family-hit-000001` |
| Stale address | `0x27B1ED850C0` |
| Stale candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-27552-20260515-022029-063377\api-family-vec3-candidates.jsonl` |
| Support count | `6` |
| Archived proof pointer | `docs\recovery\historical\current-proof-anchor-readback-2026-05-15-pid27552-hwnd3411E2-historical.json` |
| Reuse policy | `do-not-use-as-current-proof; do-not-use-for-movement; use only as broad family/reacquisition/static-chain hint after rescoring against the current target` |

## Static-chain evidence status

| Evidence | Current interpretation |
|---|---|
| Source/cache path | Primary future hypothesis: `root -> owner -> source/cache/selector -> source+0x48/+0x4C/+0x50`. |
| Destination-owner path | `coordLeaf = owner+0x320` / inferred owner `0x27B1ED84DA0` is demoted to negative-control. |
| Static root lead | `rift_x64.exe+0x32E1780` remains plausible owner/service root lead only; not proven. |
| Static chain | Not discovered. Requires fresh live/runtime validation later. |
| x64dbg/CE | Not used in offline cleanup. Keep x64dbg offline/read-only unless explicitly re-approved. |

## Preserved static-chain docs

- `docs\recovery\offline-static-chain-analysis-currentpid-27552-2026-05-15.md`
- `docs\recovery\offline-static-chain-call-target-analysis-currentpid-27552-2026-05-15.md`
- `docs\recovery\offline-static-chain-code-pattern-analysis-currentpid-27552-2026-05-15.md`
- `docs\recovery\offline-static-chain-historical-pattern-analysis-currentpid-27552-2026-05-15.md`
- `docs\recovery\offline-static-chain-next-scan-plan-currentpid-27552-2026-05-15.md`
- `docs\recovery\offline-static-chain-owner-signature-currentpid-27552-2026-05-15.md`
- `docs\recovery\offline-static-chain-parent-lead-analysis-currentpid-27552-2026-05-15.md`
- `docs\recovery\offline-static-chain-source-vs-destination-reclassification-currentpid-27552-2026-05-15.md`
- `docs\recovery\offline-static-chain-static-root-lead-analysis-currentpid-27552-2026-05-15.md`
- `docs\recovery\offline-static-chain-validation-packet-currentpid-27552-2026-05-15.md`

## Validation already performed before this compact handoff

| Check | Result |
|---|---|
| JSON format checks for current proof/current truth/historical archives | Passed |
| `python scripts/validate_current_truth.py --json` | Passed, `artifactCount=51` |
| `python -m unittest scripts.test_coordinate_recovery_status scripts.test_current_proof_pointer scripts.test_validate_current_truth` | Passed, 8 tests |
| `python -m compileall scripts/coordinate_recovery_status.py scripts/test_coordinate_recovery_status.py` | Passed |
| `git diff --check` before commit | Passed |
| `python scripts/coordinate_recovery_status.py --json` | Blocked as expected: `live-target-not-running:rift_x64` |
| `python scripts/riftscan_milestone_review.py` | Blocked as expected: no current selected candidate/proof after invalidation |

## Resume prompt

```text
Resume in C:\RIFT MODDING\RiftReader. Read docs/handoffs/2026-05-16-1257-compact-offline-stale-proof-resume.md first, then inspect git status and docs/recovery/current-proof-anchor-readback.json. Current repo HEAD should be e9087ff or newer. The old PID 27552 / HWND 0x3411E2 proof pointer 0x27B1ED850C0 is stale/historical only and current proof is blocked-target-drift. Do not run movement/input/ProofOnly/current-PID family scan until RIFT is loaded into the character/world and fresh API/runtime coordinate truth is available. Keep x64dbg offline/read-only unless explicitly re-approved. Static-chain evidence is candidate-only: source/cache path is primary, owner+0x320 is negative control.
```

## Next actions when game is back in-world

| # | Action | Why |
|---:|---|---|
| 1 | Rediscover exact PID/HWND/process epoch. | Old PID/HWND is stale. |
| 2 | Sample fresh API/runtime coordinate truth. | Establishes the live truth surface. |
| 3 | Run current-PID family recovery, not old-address probing. | Matches proven fast recovery strategy. |
| 4 | Require multi-pose/readback support before promotion. | Avoids dense-copy/static false positives. |
| 5 | Run same-target `ProofOnly`. | Required before movement. |
| 6 | Create/push a fresh handoff immediately after proof restoration. | Prevents another accidental close from losing state. |
