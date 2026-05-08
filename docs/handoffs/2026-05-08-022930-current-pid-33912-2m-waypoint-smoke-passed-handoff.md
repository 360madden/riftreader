# Handoff - current PID 33912 2m waypoint smoke passed

## TL;DR

Live target `rift_x64` PID `33912`, HWND `0xE0DB2` remains current-session movement-grade. After commit `96d4c51`, I ran a fresh no-input `ProofOnly`, generated a fresh 2m forward-key movement route with an intentional `/reloadui` post-save snapshot refresh, ran another fresh `ProofOnly`, and then ran a bounded 2m A/B waypoint smoke. The 2m smoke passed live: `success`, `arrived`, 4 pulses, distance `2.000000000000236m -> 0.6994920167255987m`, visual frame change `39.8806%`, followed by post-navigation `ProofOnly` pass. No CE was used. SavedVariables were only refreshed intentionally via `/reloadui`; they were not treated as live IPC.

## Current live truth

| Item | Value |
|---|---|
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Coord anchor | `rift-addon-coordinate-candidate-000001`, coord region/object `0x202FEA3E180` |
| Actor-facing lead | `0X202E570DB20 @ +0xD4`, promoted in `scripts\actor-facing-behavior-backed-lead.json` |
| Latest route | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\smoke-test-waypoints-2m-fixed-bearing.json` |
| Latest movement validation | 2m fixed-bearing A/B waypoint smoke passed: 4 pulses, `arrived`, `2.000000000000236m -> 0.6994920167255987m` |
| Latest post-movement proof | `ProofOnly` passed, coordinate `7436.4345703125, 885.2191772460938, 3056.560546875` at `2026-05-08T06:28:07.1262070Z` |
| Safety | exact PID/HWND, fresh proof before movement, no CE, no SavedVariables live truth |

## Key evidence

| Evidence | Path / Result |
|---|---|
| Pre-route ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-062201\run-summary.json`; `passed-proof-only`; `movementSent=false` |
| Route generation stdout | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\new-forward-smoke-route-2m.stdout.txt` |
| Route file | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\smoke-test-waypoints-2m-fixed-bearing.json`; bearing `-79.60378349460011` degrees; distance `2.0m`; arrival radius `0.7m` |
| Pre-move ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-062550\run-summary.json`; `passed-proof-only`; `movementSent=false` |
| Passing 2m waypoint smoke | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\a-to-b-prototype-2m-fixed-bearing.ndjson`; `success`, `arrived`, 4 pulses |
| 2m smoke stdout | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\run-a-to-b-prototype-2m-fixed-bearing.stdout.txt` |
| 2m route summary JSON | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\a-to-b-prototype-2m-fixed-bearing-summary.json` |
| 2m route summary Markdown | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-0622-2m\a-to-b-prototype-2m-fixed-bearing-summary.md` |
| Visual frame change | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-022731-069.png`; `changed=true`, `39.8806%` |
| Post-navigation ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-062740\run-summary.json`; `passed-proof-only`; `movementSent=false` |
| Post-navigation readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-33912-readback-summary-20260508-022802.json` |

## Important nuance

The 2m navigation session itself succeeded. The ad hoc outer PowerShell command I used to tee stdout threw after the script returned because `$LASTEXITCODE` was blank after `Tee-Object`; the authoritative NDJSON session result reports `exitCode=0`, `Status=success`, `StopReason=arrived`.

## Resume procedure

1. Start in `C:\RIFT MODDING\RiftReader`.
2. Check `git status --short`; this handoff/current-truth update may be uncommitted after commit `96d4c51`.
3. Read `docs\recovery\current-truth.md` top section and `docs\recovery\current-proof-anchor-readback.json`.
4. Re-bind exact live target before any live work: PID `33912`, HWND `0xE0DB2` if still alive; otherwise reacquire.
5. Before any movement, run fresh `ProofOnly`; do not trust stale proof age.
6. Next live slice should be bounded auto-turn validation with an intentionally offset route. Do not loop blind forward pulses.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit the 2m smoke docs/current-truth update after validation | The new live proof is useful and should not remain only in ignored captures. |
| 2 | Run `git diff --check` before the next commit | Catch whitespace drift in new handoff/current-truth edits. |
| 3 | Keep the 2m route summary JSON/Markdown paths in the handoff | They make the success auditable without replaying the full NDJSON. |
| 4 | Run fresh `ProofOnly` before any further live movement | Proof is age-gated and process-session-bound. |
| 5 | Next live slice: deliberate offset-route auto-turn validation | It is the next unproven navigation behavior after straight-line 2m success. |
| 6 | Use a small offset and tight stop conditions for auto-turn | Bounds risk while proving turn direction and convergence. |
| 7 | Capture baseline and wait for frame change around auto-turn input | Keeps visual evidence tied to exact PID/HWND input. |
| 8 | Watch for `moving-away` and auto-turn worsening stops | These are the new fail-closed safety paths to prove live. |
| 9 | Reacquire proof/facing if PID `33912` changes | Current addresses are not durable across Rift restarts. |
| 10 | Avoid CE and SavedVariables-as-live-truth | The current no-CE/live-proof path is working and safer. |
