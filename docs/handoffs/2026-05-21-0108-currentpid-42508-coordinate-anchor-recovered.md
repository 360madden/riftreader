# Current-PID player coordinate anchor recovered — 2026-05-21 01:08 EDT

## Verdict

- Status: recovered and same-target `ProofOnly` passed.
- Current target: PID `42508`, HWND `0x80E00`, process `rift_x64`.
- Current proof status: `current-target-proofonly-passed`.
- Movement allowed effective: `true` after same-target ProofOnly.
- No Cheat Engine and no live x64dbg attach were used.

## Current promoted anchor

| Field | Value |
|---|---|
| Candidate ID | `api-family-hit-000001` |
| Address | `0x1FD21900420` |
| Candidate file | `C:\RIFT MODDING\RiftReader\scripts\captures\family-scan-currentpid-42508-20260521-050209-898718\api-family-vec3-candidates.jsonl` |
| Support count | `3` |
| Best max abs distance | `0.0077781250001862645` |
| Current coordinate | `x=7369.5185546875, y=868.3978271484375, z=2997.177978515625` |

## Recovery evidence

| Phase | Artifact / result |
|---|---|
| Target discovery | Exactly one current RIFT target after stale PID `17144` closed: PID `42508`, HWND `0x80E00` |
| Baseline screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260521-010035-119.png` |
| Recovery run | `C:\RIFT MODDING\RiftReader\scripts\captures\recover-currentpid-coord-anchor-fast-execute-42508-20260521-050050-298426\summary.json` |
| Pose batch | `C:\RIFT MODDING\RiftReader\scripts\captures\recover-currentpid-coord-anchor-fast-execute-42508-20260521-050050-298426\05-pose-batch-attempt-01-w-750ms\coordinate-anchor-batch-summary.json` |
| Promotion run | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-promote-currentpid-42508-20260521-010704` |
| ProofOnly run | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260521-050715\run-summary.json` |
| Current proof pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json` |
| Archived stale pointer | `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-proof-anchor-readback-2026-05-21-pid17144-hwnd2C0B22-historical.json` |

## Displacement proof

The recovery helper required API-coordinate displacement before promotion.

| Pose | API delta X | API delta Y | API delta Z | Planar distance | Displaced |
|---:|---:|---:|---:|---:|---|
| 1 | `0.0` | `0.0` | `0.0` | `0.0` | false |
| 2 | `3.2402` | `-0.83` | `-3.28` | `4.610563527379222` | true |
| 3 | `6.4204` | `-2.89` | `-6.51` | `9.14339303322395` | true |

Gate fields:

- `displacementEvidenceSatisfied`: true
- `displacedPoseCount`: 2
- `maxPlanarDisplacement`: 9.14339303322395
- `topCandidateDisplacedPoseSupportCount`: 2

## Validation completed

```powershell
python -m unittest scripts.test_recover_current_pid_coord_anchor_fast scripts.test_coordinate_recovery_status scripts.test_fast_world_launch
python -m compileall .\scripts\recover_current_pid_coord_anchor_fast.py .\scripts\test_recover_current_pid_coord_anchor_fast.py
python -m json.tool C:\RIFT MODDING\RiftReader\scripts\captures\recover-currentpid-coord-anchor-fast-execute-42508-20260521-050050-298426\summary.json
python -m json.tool C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260521-050715\run-summary.json
python -m json.tool C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json
python .\scripts\coordinate_recovery_status.py --json
```

Results:

- Unit tests: `40` passed.
- JSON artifact validation: passed.
- `coordinate_recovery_status.py --json`: exit `0`; status `current-target-proofonly-passed`.
- `git diff --check`: passed with only CRLF warnings.

## Safety summary

| Field | Value |
|---|---|
| movementSent during recovery | true |
| movementSent during ProofOnly | false |
| reloaduiSent | false |
| screenshotKeySent | false |
| noCheatEngine | true |
| x64dbgLiveAttachStarted | false |
| providerWrites | false |
| gitMutation from helpers | false |

## Notes for next session

- Treat PID `17144` and HWND `0x2C0B22` as historical only.
- Current movement-grade coordinate proof is tied to PID `42508` / HWND `0x80E00` and remains valid only while the same process epoch is live.
- If the client restarts or another RIFT client appears, re-run current target discovery and fail closed before using this anchor.
