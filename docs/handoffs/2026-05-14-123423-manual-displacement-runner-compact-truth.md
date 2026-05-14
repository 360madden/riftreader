# RiftReader handoff — manual displacement runner and compact truth summary

Generated: `2026-05-14T12:34:23Z`

## Verdict

`main` now has a Python-first, no-input runner for the next manually displaced
coordinate proof capture. Movement remains blocked.

## Current truth

| Field | Value |
|---|---|
| Route status | `api-memory-match` |
| Target | `rift_x64` PID `2928`, HWND `0xC0994` |
| Candidate | `api-family-hit-000001` at `0x268E2BC09E0` |
| Raw both-reference matches | `2` |
| Valid both-reference matches | `0` |
| Displaced readiness | `blocked` |
| Proof-anchor promotion | `false` |
| Movement allowed | `false` |

## What changed

| Area | Path |
|---|---|
| Manual displaced-pose runner | `scripts/rift_live_test/manual_displacement_capture.py` |
| Thin Python entry point | `scripts/capture_after_manual_displacement.py` |
| Compact truth summary helper | `scripts/rift_live_test/current_truth_compact_summary.py` |
| Thin compact-summary entry point | `scripts/current_truth_compact_summary.py` |
| Route HTML raw-vs-valid gate | `scripts/rift_live_test/coordinate_proof_route.py` |
| Regression tests | `scripts/test_manual_displacement_capture.py`, `scripts/test_current_truth_compact_summary.py`, `scripts/test_coordinate_proof_route.py` |

## New artifacts

| Artifact | Path |
|---|---|
| Route JSON | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-20260514-083422-raw-valid-html/coordinate-proof-route.json` |
| Route HTML | `scripts/captures/coordinate-proof-route-current-reacquire-20260514-20260514-083422-raw-valid-html/coordinate-proof-route.html` |
| Manual runner dry-run | `scripts/captures/manual-displacement-capture-20260514-20260514-083422-dry-run/summary.json` |
| Compact current-truth HTML | `docs/recovery/current-truth-compact-summary-20260514-123423.html` |
| Top 10 HTML summary | `docs/recovery/coordinate-proof-route-actions-1-10-summary-2026-05-14-123423-manual-displacement-runner.html` |

## Remaining blocker

The latest two-reference comparison still has raw matches from effectively the
same pose. The displacement gate correctly reduces valid both-reference matches
to `0`, so no candidate is promotion-ready and movement stays blocked.

## Resume prompt

Continue in `C:\RIFT MODDING\RiftReader` on `main`. Start by reading this
handoff and `docs/recovery/current-truth.json`. Do not use CE/x64dbg and do not
send movement/input. Ask the operator to manually move the player at least
1 meter, then run:

```powershell
python .\scripts\capture_after_manual_displacement.py --route-summary .\scripts\captures\latest-coordinate-proof-route.json --json
```

If the runner returns `passed`, review the new route for proof-anchor promotion.
If it returns `blocked`, use the recorded blockers and artifact paths; do not
fall back to stale absolute addresses.
