# Handoff: Current PID 33912 offset-route auto-turn blocked

_Last updated: 2026-05-08 03:12 EDT / 07:12 UTC_

## TL;DR

Current-session movement proof is still good through the earlier 2m waypoint smoke, but the deliberate offset-route auto-turn validation is **not passed**. Multiple proof-gated runs failed before forward navigation. The newest blocker is turn-input convergence: key helper calls report success, but actor-facing does not reliably move toward the destination bearing, so the navigation prototype correctly refuses to send forward movement.

## Current target

| Fact | Value |
|---|---|
| Process | `rift_x64` |
| PID | `33912` |
| HWND | `0xE0DB2` |
| CE | Not used |
| SavedVariables live truth | Not used |

## Last good movement truth

| Fact | Value |
|---|---|
| Last passed active waypoint smoke | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\a-to-b-prototype-2m-fixed-bearing.ndjson` |
| Result | `success`, `arrived`, 4 pulses, distance `2.000000000000236m -> 0.6994920167255987m` |
| Post-pass proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-062740\run-summary.json` |

## Auto-turn blocker evidence

| Evidence | Result |
|---|---|
| Offset route | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-autoturn-currentpid-33912-20260508-0633-offset20\smoke-test-waypoints-autoturn-offset20.json` |
| First retry | `a-to-b-prototype-autoturn-offset20-retry.ndjson`: failed at `auto-turn-key:7` on `proof_anchor_age_out_of_range_seconds:65.587`; no forward navigation sent |
| 125ms retry | `a-to-b-prototype-autoturn-offset20-retry125.ndjson`: failed after 3 pulses; yaw/delta stayed `-71.56334872885803 / 11.955378182059235`; no forward navigation sent |
| PostMessage retry | `a-to-b-prototype-autoturn-offset20-postmessage.ndjson`: first pulse improved slightly to delta `13.651793251539019`, then no further convergence; no forward navigation sent |
| Shift+D/PostMessage retry | `a-to-b-prototype-autoturn-offset20-winps-shiftD75-postmessage.ndjson`: key helper reported success, yaw stayed `-73.08494464580617`, delta stayed `13.651793251539019`; no forward navigation sent |
| Post-blocker proof | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-071016\run-summary.json`; `movementSent=false`; current coordinate `7436.5458984375, 885.2191772460938, 3056.19580078125` |

## Code hardening completed

| File | Change |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1` | Added `-AutoTurnUsePostMessage` for explicit exact-HWND post-message turn trials. |
| `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1` | Added no-progress auto-turn guard via `AutoTurnMinImprovementDegrees` and `AutoTurnMaxNoImprovementPulses`; repeated non-converging pulses now fail closed earlier. |
| `C:\RIFT MODDING\RiftReader\scripts\navigation\test-run-a-to-b-proof-anchor-gate.ps1` | Existing proof-before-input regression remains green. |

## Validation run after hardening

| Command | Result |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\navigation\test-run-a-to-b-proof-anchor-gate.ps1` | Passed |
| `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1` | Passed all 7 steps |

## Next boundary

Do **not** treat auto-turn as validated. Before another auto-turn-to-forward run, prove the effective live turn key/backend in a bounded profile that records before/after actor-facing and exact input mode. Only allow forward movement after fresh proof and after alignment is already within threshold.

## Top 10 recommended next actions

| # | Action | Why |
|---|---|---|
| 1 | Add a Python turn-key profile runner for `a/d`, `A/D`, arrows, and any configured Rift turn binds | Python should own timing-sensitive live orchestration and compact JSON output. |
| 2 | Make the profile capture before/after yaw, coord delta, key mode, shell, and visual frame-change path | Current blocker is input success without reliable yaw convergence. |
| 3 | Run the profile with exact PID/HWND and fresh `ProofOnly` before each bounded key group | Keeps live-input proof current and prevents stale anchor mixing. |
| 4 | Promote only a key/backend combo that changes yaw in the expected sign twice in a row | Prevents one-off delayed/stale yaw from becoming route truth. |
| 5 | Add `AutoTurnMinImprovementDegrees`/`AutoTurnMaxNoImprovementPulses` docs to navigation docs | Operators need to understand the new fail-closed reason. |
| 6 | Add log summary fields for `auto-turn/no-progress` counts | Makes future blocker diagnosis visible in one summary. |
| 7 | Re-run offset route only after the turn profile identifies a reliable key/backend | Avoids more non-converging live pulses. |
| 8 | Keep `Navigation calls=0` as the safety success condition for failed auto-turn attempts | Failed alignment must not transition into forward movement. |
| 9 | Update `current-proof-anchor-readback.json` whenever auto-turn moves from blocked to validated | Keeps resume truth current. |
| 10 | Commit this blocker/hardening slice before more live experiments | Preserves the evidence and the safer fail-closed behavior. |
