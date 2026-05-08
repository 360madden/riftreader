# Handoff - current PID 33912 waypoint smoke passed after movement-bearing fix

## TL;DR

Live target `rift_x64` PID `33912`, HWND `0xE0DB2` is current-session movement-grade. I promoted fresh actor-facing truth, found and fixed a 180-degree movement-bearing convention bug, then validated a fixed 1m A/B waypoint smoke live. No CE was used. SavedVariables were refreshed only via intentional `/reloadui` post-save snapshot before route generation, not treated as live IPC.

## Current live truth

| Item | Value |
|---|---|
| Target | `rift_x64` PID `33912`, HWND `0xE0DB2` |
| Coord anchor | `rift-addon-coordinate-candidate-000001`, coord region/object `0x202FEA3E180` |
| Actor-facing lead | `0X202E570DB20 @ +0xD4`, promoted in `scripts\actor-facing-behavior-backed-lead.json` |
| Latest movement validation | Fixed-bearing A/B waypoint smoke passed: 1 pulse, `arrived`, `1.0000000000003622m -> 0.6652750379001031m` |
| Latest post-movement proof | `ProofOnly` passed, coordinate `7435.66650390625, 885.2191772460938, 3059.3740234375` at `2026-05-08T05:40:19.1871780Z` |
| Safety | exact PID/HWND, fresh proof before movement, no CE, no SavedVariables live truth |

## What changed

| File | Change |
|---|---|
| `reader\RiftReader.Reader\Navigation\NavigationMath.cs` | Forward-key movement bearing from actor-facing vectors now uses the opposite X/Z projection proven by live W-key movement. |
| `reader\RiftReader.Reader\Navigation\WaypointNavigator.cs` | Added a fail-closed stop when a forward pulse materially increases destination distance before the larger wrong-way tolerance is reached. |
| `scripts\navigation\new-forward-smoke-route.ps1` | Smoke-route generation now uses the same corrected forward-key movement bearing and labels it as `forward-key-movement-bearing`. |
| `reader\RiftReader.Reader\Navigation\WaypointNavigationConfiguration.cs` | Added optional provenance fields for route bearing metadata. |
| `reader\RiftReader.Reader\Navigation\WaypointNavigationConfigurationLoader.cs` | Validates `provenance.navigationBearingKind` when present; unsupported values fail closed. |
| `reader\RiftReader.Reader\Navigation\TomTomWaypointImporter.cs` | Preserves existing waypoint-file provenance when importing waypoints and writes schema JSON using camel-case field names. |
| `reader\RiftReader.Reader\Navigation\WaypointNavigationConfigurationStore.cs` | Preserves existing waypoint-file provenance, including extension metadata, when saving captured waypoints and writes schema JSON using camel-case field names. |
| `scripts\navigation\summarize-a-to-b-log.ps1` | Added optional `-MarkdownFile` output for compact route summary handoffs. |
| `reader\RiftReader.Reader.Tests\Navigation\WaypointNavigationTests.cs` | Updated navigation-facing expectations and added regression tests for current live vector mapping, material moving-away stop, route bearing provenance validation, and waypoint rewrite provenance preservation. |
| `reader\RiftReader.Reader.Tests\Navigation\TomTomWaypointImporterTests.cs` | Added regression coverage proving TomTom imports preserve extended provenance and write camel-case waypoint schema JSON. |
| `scripts\actor-facing-behavior-backed-lead.json` | Promoted current PID behavior-backed actor-facing lead `0X202E570DB20 @ +0xD4`. |
| `docs\recovery\current-truth.md` | Updated current truth with actor-facing, bearing fix, waypoint smoke, and post-navigation proof. |
| `docs\recovery\current-proof-anchor-readback.json` | Updated tracked current-session pointer/status for the fixed-bearing waypoint smoke. |
| `docs\navigation-waypoint-v1.md` | Updated bearing terminology and schema example for `forward-key-movement-bearing` provenance. |

## Key evidence

| Evidence | Path / Result |
|---|---|
| Actor-facing promotion session | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-currentpid-33912-da-20260508-052500\session.json` |
| Actor-facing default readback after promotion | `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-currentpid-33912-da-20260508-052500\capture-default-after-promotion.json` |
| Initial route failure before fix | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-051600\a-to-b-prototype-after-facing-promotion-correct-ids.ndjson`; `no-progress`, distance worsened `1.0000m -> 1.6381m` |
| Fixed route | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-051600\smoke-test-waypoints-fixed-movement-bearing.json`; bearing `-145.71781003282072` degrees |
| Passing waypoint smoke | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-051600\a-to-b-prototype-fixed-movement-bearing.ndjson`; `success`, `arrived`, 1 pulse |
| Visual change after waypoint smoke | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260508-013920-428.png`; `changed=true`, `17.9565%` |
| Post-navigation ProofOnly | `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-053953\run-summary.json` |
| Post-navigation readback | `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-33912-readback-summary-20260508-014015.json` |
| Generated A/B summary Markdown | `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-33912-20260508-051600\a-to-b-prototype-fixed-movement-bearing-summary.md` |

## Validation run

| Command / Check | Result |
|---|---|
| `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --filter "FullyQualifiedName~Navigation" --no-restore` | Passed, 54 tests |
| `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore` | Passed, 77 tests |
| Provenance preservation review fix | Added extension-data preservation and a regression test so richer route provenance is not dropped by waypoint rewrites |
| TomTom provenance preservation review fix | Added importer regression coverage so TomTom imports do not drop extended route provenance or write Pascal-case schema fields |
| Stale terminology sweep after doc cleanup | Passed; no stale pre-fix bearing terminology or duplicate commit-action wording matches |
| `python -m json.tool` on tracked current proof and actor-facing JSON | Passed |
| `python .\scripts\live_test.py --validate-profiles` | Passed, 5 profiles |
| `git diff --check -- . ':(exclude)scripts/captures'` | Passed |
| `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore` after provenance preservation hardening | Passed, 78 tests |
| `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --filter "FullyQualifiedName~TomTomWaypointImporterTests" --no-restore` | Passed, 3 tests |
| `dotnet test .\reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj --no-restore` after TomTom provenance regression | Passed, 79 tests |
| Current proof/actor-facing JSON sanity check | Passed; movement gate, no-CE/no-SavedVariables flags, actor-facing source match, distance improvement, and 15 referenced artifact paths are consistent |
| `python scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui` before fixed A/B | Passed |
| `run-a-to-b-prototype.ps1` fixed route | Passed live, `arrived` |
| `python scripts\live_test.py --profile ProofOnly --pid 33912 --hwnd 0xE0DB2 --no-gui` after fixed A/B | Passed |
| `.\scripts\navigation\summarize-a-to-b-log.ps1 -LogFile <fixed log> -MarkdownFile <summary.md>` | Passed; emitted JSON and Markdown summary |

## Resume procedure

1. Start in `C:\RIFT MODDING\RiftReader`.
2. Check `git status --short` and read `docs\recovery\current-truth.md` top section.
3. Re-bind exact live target before any live work: PID `33912`, HWND `0xE0DB2` if still alive; otherwise reacquire.
4. Before any movement, run fresh `ProofOnly`; do not trust stale proof age.
5. Next live slice should be bounded: a slightly longer fixed-bearing route or auto-turn validation. Do not loop blind forward pulses.

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit the current movement milestone, provenance validation, docs, and handoffs together | Current live proof is good and the full Reader test suite passes. |
| 2 | Keep the current live-vector regression test with the bearing fix | Locks the exact regression that caused wrong-way movement. |
| 3 | Verify the next live-generated route carries `forward-key-movement-bearing` metadata | The loader now accepts only that bearing kind when metadata is present. |
| 4 | Review the new material moving-away stop during the next live route | It should stop wrong-direction movement after one material worsening pulse. |
| 5 | Run a 2m fixed-bearing A/B smoke with fresh proof | Validates the fix beyond arrival-radius edge conditions. |
| 6 | Validate `--auto-turn-before-move` using a deliberately offset route | Ensures turn direction matches the corrected bearing convention. |
| 7 | Use the new `-MarkdownFile` summary output after future route runs | Makes future handoffs faster and less error-prone. |
| 8 | Preserve the current artifacts before restarting Rift | PID-bound proof/facing addresses are ephemeral and expensive to reconstruct. |
| 9 | Reacquire proof/facing before any future live movement if PID `33912` changes | The current addresses are process-session truth, not durable across process restarts. |
| 10 | Keep the provenance rewrite regression test with this milestone | Prevents future waypoint rewrites from dropping generated route proof/session metadata. |
