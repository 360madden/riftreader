# Offline restart stale-proof handoff — coordinate proof blocked

Generated UTC: `2026-05-16T16:46:11Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch at creation: `main`

## TL;DR

The game/Codex session closed unexpectedly. Offline recovery preserved yesterday's static-chain analysis and converted the prior PID `27552` proof pointer into a blocker/historical reacquisition seed. No live RIFT memory, x64dbg, CE, movement, or input was used.

| Field | Value |
|---|---|
| Current live RIFT process | none detected by offline status check |
| Prior proof PID / HWND | `27552` / `0x3411E2` |
| Prior proof candidate | `api-family-hit-000001` |
| Prior proof address | `0x27B1ED850C0` |
| Current proof pointer status | `blocked-target-drift` |
| Movement allowed | `false` |
| x64dbg / CE | not used |
| SavedVariables as live truth | not used |
| Static chain | not discovered; candidate-only |

## Files preserved or updated

| Path | Purpose |
|---|---|
| `docs/recovery/current-proof-anchor-readback.json` | Replaced with a `blocked-target-drift` blocker. |
| `docs\recovery\historical\current-proof-anchor-readback-2026-05-15-pid27552-hwnd3411E2-historical.json` | Historical archive of the prior PID `27552` proof pointer. |
| `docs/recovery/current-truth.json` | Marked movement blocked / reacquisition required. |
| `docs/recovery/current-truth.md` | Human-readable stale/offline status update. |
| `docs\recovery\historical\current-truth-2026-05-15-pid27552-hwnd3411E2-stale-after-offline-restart.json` | Historical archive of previous current-truth JSON. |
| `docs\recovery\historical\current-truth-2026-05-15-pid27552-hwnd3411E2-stale-after-offline-restart.md` | Historical archive of previous current-truth Markdown. |
| `docs/recovery/offline-static-chain-*-currentpid-27552-2026-05-15.md` | Preserved yesterday's offline static-chain docs. |

## Static-chain interpretation preserved

| Lead | Current handling |
|---|---|
| `root -> owner -> source/cache/selector -> source+0x48/+0x4C/+0x50` | Primary future validation hypothesis. |
| `coordLeaf = owner+0x320` / `0x27B1ED84DA0` inferred owner | Demoted to negative-control / low-priority. |
| `rift_x64.exe+0x32E1780` | Plausible owner/service root lead only; not proven. |
| `0x27B1ED850C0` | Historical PID `27552` proof address; broad reacquisition/static-chain seed only. |

## Safety boundaries

| Boundary | Status |
|---|---|
| Live movement/input | Not used; blocked. |
| ProofOnly | Not run while game is offline/no live target. |
| Current-PID family scan | Not run while game is offline/no live target. |
| x64dbg live attach/watchpoints | Not used; remains offline/read-only unless explicitly approved. |
| Cheat Engine | Not used. |
| SavedVariables live truth | Not used. |

## Validation performed

| Check | Result | Notes |
|---|---|---|
| `python -m json.tool docs/recovery/current-proof-anchor-readback.json` | Passed | Current pointer blocker JSON is valid. |
| `python -m json.tool docs/recovery/current-truth.json` | Passed | Current truth JSON is valid. |
| `python scripts/validate_current_truth.py --json` | Passed | `artifactCount=51`; no errors or warnings. |
| `python -m unittest scripts.test_coordinate_recovery_status scripts.test_current_proof_pointer scripts.test_validate_current_truth` | Passed | 8 tests passed. |
| `python -m compileall scripts/coordinate_recovery_status.py scripts/test_coordinate_recovery_status.py` | Passed | Syntax check passed. |
| `python scripts/coordinate_recovery_status.py --json` | Blocked as expected | `live-target-not-running:rift_x64`; this is the intended offline/no-live-target gate. |
| `python scripts/riftscan_milestone_review.py` | Blocked as expected | No current selected candidate after pointer invalidation; movement/read-only proof remain blocked. |
| `git diff --check` | Passed | Whitespace check passed. |

## Resume instructions

1. Start/load RIFT into the character/world.
2. Rediscover exact PID/HWND/process epoch.
3. Sample fresh API/runtime coordinate truth.
4. Run current-PID family recovery; do not probe old absolute addresses as current truth.
5. Promote only after same-target multi-pose/readback support and `ProofOnly` pass.
6. Create a fresh handoff immediately after the new proof anchor is restored.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit this stale-proof/offline-doc preservation slice. | Prevents loss after another close/restart. |
| 2 | Push `main`. | Keeps remote recovery docs aligned. |
| 3 | Keep PID `27552` pointer historical. | It is not current after the game closed. |
| 4 | Do not run ProofOnly until the character/world is loaded. | Login/offline state is not proof-grade coordinate truth. |
| 5 | Begin next live recovery with fresh API/runtime truth. | Avoids stale SavedVariables/artifact reuse. |
| 6 | Use current-PID family recovery, not old-address probing. | Matches the successful fast lane. |
| 7 | Keep source/cache chain hypothesis primary. | Latest offline evidence supports it over `owner+0x320`. |
| 8 | Keep `owner+0x320` as negative control only. | Prevents static-chain false promotion. |
| 9 | Keep x64dbg offline/read-only unless explicitly re-approved. | Reduces crash/recovery cost. |
| 10 | After fresh ProofOnly, create a compact handoff immediately. | Protects continuity if Codex/game closes again. |
