# Post-update exact-target active smoke handoff

_Created: 2026-04-28 18:34 -04:00_

## TL;DR

The April 28 client update changed live memory layout, but `main` has been recovered and validated for the current live session:

- live target: `rift_x64` PID `41220`, HWND `0xBD0D94`
- coord proof anchor: `0x216F87CDE18`
- coord source object: `0x216F87CDDD0`, coord offset `+0x48`
- actor-facing lead: `0x216FE3C6280 @ +0xD4`
- exact-target provenance: confirmed
- proof polling watchset: rebuilt and reader-accepted
- active movement smoke proof: passed with strict `coord-trace-anchor`

No camera truth was revalidated. No multi-segment v3 route-chain proof was run.

## Branch / repo state at handoff creation

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` |
| Last commit before this handoff | `eb9819f Refresh exact-target provenance and active smoke truth` |
| Branch relationship before this handoff | `main...origin/main [ahead 2]` |
| Worktree before this handoff | clean |

## Current live target

| Item | Value |
|---|---|
| Process | `rift_x64` |
| PID | `41220` |
| HWND | `0xBD0D94` |
| Window title | `RIFT` |
| Character/location | Atank / Bahralt Street |
| Client SHA256 | `33B35F2DC17BD9AF1CC2186DF2B62ED5232D77630BDB3C00895FD84C464BF3EC` |
| Client LastWrite | `2026-04-28 14:05:32 -04:00` |

Treat PID/HWND/address values as **session-bound**. Revalidate after any restart, relog, zone transition, or client update.

## Current truth

| Area | Current truth |
|---|---|
| Proof coord source | `coord-trace-direct-region` |
| Coord region | `0x216F87CDE18` |
| Coord source object | `0x216F87CDDD0` |
| Source coord offset | `+0x48` |
| Actor-facing source | `0x216FE3C6280` |
| Actor-facing basis | `+0xD4/+0xD8/+0xDC` |
| Actor yaw formula | `atan2(forwardZ, forwardX)` |
| Actor pitch formula | `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))` |
| Proof polling watchset | `scripts\captures\proof-polling-watchset.json` includes required `coord-trace-coords` at `0x216F87CDE18`, length `12` |
| Navigation-current | uses `AnchorSource=coord-trace-anchor` |

## Active movement proof result

Smallest post-update active movement proof passed.

| Metric | Value |
|---|---|
| Runner | `scripts\navigation\run-a-to-b-prototype.ps1` |
| Route file | `scripts\captures\post-update-inworld-20260428-141625\current-session-smoke-waypoints-active-proof.json` |
| Log file | `scripts\captures\post-update-inworld-20260428-141625\a-to-b-prototype-active-proof.ndjson` |
| Status | `success` |
| Stop reason | `arrived` |
| Anchor source | `coord-trace-anchor` |
| Pulse count | `1` |
| Input | one `w` pulse for `250 ms` |
| Initial planar distance | `2.59913956610242` |
| Final planar distance | `1.78405903199564` |
| Arrival radius | `2.1` |
| Elapsed | `2406 ms` |
| Initial position | `7448.36083984375, 863.5816650390625, 2973.037109375` |
| Final position | `7449.17529296875, 863.5852661132812, 2973.069091796875` |

Final post-active sanity also passed:

| Check | Result |
|---|---|
| Proof anchor trace matches process | `true` |
| Proof source | `coord-trace-direct-region` |
| Coord region | `0x216F87CDE18` |
| Memory coord valid | `true` |
| Facing valid | `true` |
| Effective position source | `memory` |
| Effective facing source | `memory-facing` |
| Final nav distance | `1.784059` |
| Final nav within arrival radius | `true` |

## Code changes in the milestone

| Path | Purpose |
|---|---|
| `scripts\resolve-proof-coord-anchor.ps1` | Fixed named splatting into trace refresh so proof reacquisition binds args correctly. |
| `scripts\capture-player-trace-cluster.ps1` | Fixed named splatting, 12-byte access watch, and `MaxCandidates=4`. |
| `scripts\refresh-discovery-chain.ps1` | Added exact `-ProcessId` / `-TargetWindowHandle` propagation through provenance child steps. |
| `scripts\refresh-actor-facing-discovery.ps1` | `-RunProvenance` now passes exact live target into the discovery chain. |
| `scripts\capture-player-source-accessor-family.ps1` | Added exact target args for reader calls and output target fields. |
| `scripts\capture-player-stat-hub-graph.ps1` | Added exact target args for reader calls and output target fields. |
| `scripts\export-proof-polling-watchset.ps1` | Added `-TargetWindowHandle` support and target fields. |
| `scripts\actor-facing-behavior-backed-lead.json` | Updated to current post-update lead `0x216FE3C6280 @ +0xD4`. |
| `docs\recovery\current-truth.md` | Updated with post-update coord/facing/provenance/watchset/active-smoke truth. |

## Validation completed

| Validation | Result |
|---|---|
| PowerShell parser checks on modified scripts | PASS |
| `git diff --check` | PASS, only LF-to-CRLF warnings |
| `scripts\test-player-source-chain-recovery.ps1` | PASS |
| `scripts\test-player-source-chain-fresh-rebuild.ps1` | PASS |
| `scripts\test-actor-facing-proof-suite.ps1` | PASS |
| `scripts\navigation\test-navigation-proof-suite.ps1` | PASS |
| Exact-target actor provenance run | PASS |
| Proof polling watchset export | PASS |
| Proof watchset reader smoke | PASS |
| Active movement smoke proof | PASS |
| Final post-active proof-anchor sanity | PASS |
| Final post-active telemetry preflight | PASS |
| Final post-active `--read-navigation-current` | PASS |

## Evidence root

Primary evidence folder:

`C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625`

Key files:

- `process-info.json`
- `refresh-actor-facing-discovery-runprovenance-exact-target.stdout.txt`
- `export-proof-polling-watchset-exact-target.stdout.txt`
- `record-session-proof-watchset-smoke.stdout.txt`
- `current-session-smoke-waypoints-active-proof.json`
- `run-a-to-b-prototype-active-proof.stdout.txt`
- `a-to-b-prototype-active-proof.ndjson`
- `resolve-proof-coord-anchor-after-active-proof.stdout.txt`
- `telemetry-preflight-after-active-proof.stdout.txt`
- `read-navigation-current-after-active-proof.stdout.txt`

## Remaining blockers / not done

| Priority | Gap | Notes |
|---:|---|---|
| 1 | Multi-segment route-chain proof | `--navigate-waypoints` single-segment smoke is green; `--navigate-waypoint-route` still needs a post-update live proof. |
| 2 | Camera truth | Camera yaw/pitch/distance remains stale/unverified after the April 28 update. |
| 3 | Durable restart proof | Current addresses are session-bound; restart/relog proof is not done. |
| 4 | Terrain/obstacle policy | Single straight smoke proof passed; broader route/terrain obstruction handling is not promoted. |
| 5 | Exact-target regression tests | Exact-target propagation was validated live, but dedicated regression coverage should be added. |

## Resume checklist

1. Confirm target process/window:
   - `Get-Process -Id 41220` is only valid if the same process is still alive.
   - Prefer exact PID/HWND for every live/proof helper.
2. Refresh ReaderBridge exact-target before comparing memory to addon/export values:
   - `pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\refresh-readerbridge-export.ps1 -Json -ProcessId <pid> -TargetWindowHandle <hwnd>`
3. Resolve proof coord anchor immediately before movement proof:
   - `pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\resolve-proof-coord-anchor.ps1 -ProcessId <pid> -TargetWindowHandle <hwnd> -Json`
4. Rebuild proof polling watchset if the process restarted:
   - `pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\export-proof-polling-watchset.ps1 -Json -ProcessId <pid> -TargetWindowHandle <hwnd>`
5. For next live movement, start with tiny proof only; do not jump directly to broad route-chain autonomy.

## Top 10 ranked next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit this handoff if not already committed. | Preserves the post-update recovery milestone as a durable resume point. |
| 2 | Add regression coverage for exact PID/HWND propagation in `refresh-discovery-chain.ps1`. | Prevents provenance from drifting back to unsafe process-name-only targeting. |
| 3 | Run one tiny `--navigate-waypoint-route` proof using the same exact-target discipline. | Promotes v3 route-chain after single-segment movement is green. |
| 4 | Create/reuse a fresh route that requires actual movement, not an already-arrived no-op. | Avoids false positive movement proof. |
| 5 | Add a restart/relog recovery check for coord anchor + facing lead. | Distinguishes session-bound truth from durable recovery behavior. |
| 6 | Revalidate camera branch on the updated client. | Camera truth is explicitly stale after the large update. |
| 7 | Extend docs/tests around proof watchset required `coord-trace-coords`. | Locks in the movement-polling invariant. |
| 8 | Keep historical April 23 addresses as historical only. | Prevents stale address reuse after the April 28 client layout change. |
| 9 | Add a small operator command to summarize current proof readiness. | Makes future resume faster and less error-prone. |
| 10 | Push `main` after review/commit. | Local `main` is ahead of `origin/main`; remote is not yet current. |
