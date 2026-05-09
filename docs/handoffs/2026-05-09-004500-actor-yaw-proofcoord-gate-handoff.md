# Actor-yaw proof-coordinate gate handoff

Created: 2026-05-09 00:45 EDT / 2026-05-09 04:45 UTC
Repo: `C:\RIFT MODDING\RiftReader`
Branch: `main`
Target: `rift_x64` PID `49504`, HWND `0x5121A`

## TL;DR

Actor-yaw proof prep found and fixed a stale-coordinate hazard before sending any yaw stimulus. The promoted actor-yaw lead is still stale for current PID `49504`, and the current desktop visual baseline is blocked, so no turn/yaw stimulus was sent.

The safe progress in this slice is code hardening: actor-yaw candidate discovery now prefers the current proof-coordinate memory anchor over stale ReaderBridge/bootstrap coordinates, and the yaw candidate validation script now prefers the proof anchor for player-coordinate drift when exact PID/HWND is supplied.

Auto-turn remains blocked. No CE was used. SavedVariables were not used as live truth.

## Evidence

| Fact | Value |
|---|---|
| No-input actor-yaw status | `python .\scripts\actor_yaw_current_truth_status.py --json` reports the promoted lead belongs to old PID `33912`, HWND `0xE0DB2`. |
| Current-PID readback smoke | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-readback-smoke-currentpid-49504-20260509-043414\run-summary.json`; failed safely because behavior-backed lead timestamp predates current process start. |
| Stale-coordinate hazard | Pre-hardening current-PID candidate search used stale `PlayerCoord=7389.3896484375,872.92999267578,3050.9899902344` instead of latest proof coordinate `7395.18603515625,876.5137939453125,3050.689453125`. |
| Code fix | `reader\RiftReader.Reader\Program.cs` supplies a proof-coordinate override from `scripts\captures\telemetry-proof-coord-anchor.json` into `PlayerOrientationCandidateFinder`. |
| Finder contract | `reader\RiftReader.Reader\Models\PlayerOrientationCandidateFinder.cs` accepts optional player-coordinate override and records the override source in notes. |
| Yaw validation script fix | `scripts\test-actor-yaw-candidates.ps1` now prefers the proof anchor for player-current reads when exact PID/HWND is supplied. |
| Fresh candidate search after fix | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-currentpid-49504-20260509-0035\player-orientation-candidate-search-proofcoord.json`; `PlayerCoord=7395.18603515625,876.5137939453125,3050.689453125`; best pointer-hop `0x24A26F40DC0 @ 0xD4`; note includes `telemetry-proof-coord-anchor-current-memory`. |
| Live visual blocker | `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-004400\visual-gate-status.json`; `blocked-visual-baseline`, `readyForLiveInput=false`, blocker `desktop-capture-access-denied`. |
| MCP capture blocker | `capture_game_window` failed after focus with `The handle is invalid`. |
| Milestone review | `C:\RIFT MODDING\RiftReader\scripts\captures\riftscan-milestone-review-20260509-0045-actor-yaw-proofcoord-gate.json`; `ready-for-read-only-proof`, movement allowed by review `false`. |

## Validation performed

| Check | Result |
|---|---|
| Targeted C# tests | Passed `25/25`: candidate JSON output, candidate ledger, parser tests. |
| Yaw script regression | Passed: `pwsh -File .\scripts\test-actor-yaw-candidates-reversible-output.ps1`. |
| Fresh no-input candidate search | Passed and used proof-coordinate override. |
| Visual gate | Failed closed: `blocked-visual-baseline`, no live yaw stimulus sent. |
| RiftScan milestone review | Passed; `ready-for-read-only-proof`. |

## Resume rules

| Rule | Detail |
|---|---|
| No CE | Do not use Cheat Engine unless explicitly reauthorized. |
| No SavedVariables live truth | Do not use ReaderBridge/SavedVariables coordinates as current actor-yaw proof input. |
| Visual gate first | Current state is blocked. Restore desktop/window capture and rerun `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full`. |
| Proof second | Rerun `python .\scripts\live_test.py --profile ProofOnly --pid 49504 --hwnd 0x5121A --process-name rift_x64 --live --no-gui` immediately before any live stimulus. |
| Candidate screen | Use `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-currentpid-49504-20260509-0035\player-orientation-candidate-search-proofcoord.json` only if the target/process epoch remains current and a fresh proof gate still matches. Regenerate after movement/restart. |
| No auto-turn | Actor-facing/turn backend is still not promoted for PID `49504`. |

## Suggested next milestone

After desktop capture is restored, rerun visual gate + fresh `ProofOnly`, then run the bounded actor-yaw candidate stimulus against the proof-coordinate candidate screen. Do not combine the yaw proof with navigation route execution.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Read `docs\recovery\current-truth.md`, `docs\recovery\README.md`, and `docs\handoffs\2026-05-09-004500-actor-yaw-proofcoord-gate-handoff.md` first. Actor-yaw current-PID readback failed safely because the promoted lead is stale for PID `49504`. Candidate discovery was hardened to use `telemetry-proof-coord-anchor.json` current memory coordinates; the fresh candidate screen is `C:\RIFT MODDING\RiftReader\scripts\captures\actor-yaw-currentpid-49504-20260509-0035\player-orientation-candidate-search-proofcoord.json`, best pointer-hop `0x24A26F40DC0 @ 0xD4`. Live yaw stimulus was not sent because visual gate `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-004400\visual-gate-status.json` is blocked with `desktop-capture-access-denied`. Before any input, restore desktop capture, rerun visual gate, and rerun fresh `ProofOnly`. Do not use CE, do not use SavedVariables as live truth, and do not use auto-turn until actor-facing/turn-backend truth is promoted.
