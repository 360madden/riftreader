# Current Truth

_Last updated: April 30, 2026 (live `rift_x64` PID `41220`, HWND `0xBD0D94`;
coord anchor refreshed, actor-facing/yaw re-promoted from exact-window D/A
validation, telemetry preflight green, and read-only navigation-current using
memory-facing is green)._

## Current status

| Area | Status |
|---|---|
| Client executable | changed by the April 28, 2026 update; current `rift_x64.exe` SHA256 is `33B35F2DC17BD9AF1CC2186DF2B62ED5232D77630BDB3C00895FD84C464BF3EC`, size `59918272`, LastWrite `2026-04-28 14:05:32 -04:00` |
| Low-level reader | working against current live PID `41220` |
| ReaderBridge snapshot/export | available; export matched Atank at Sanctum Watch during April 30 recovery |
| Player current read | working for read-only context; current `SelectionSource=heuristic` remains exploration-only, not movement proof |
| Proof coord anchor cache | refreshed and validated on current live PID via `coord-triplet-access` |
| Proof coord source | canonical current coord region `0x216F2F26068`; source object `0x216F2F26020`; source coord offset `+0x48` |
| Proof polling watchset | rebuilt after April 30 yaw promotion and again after active smoke; required `coord-trace-coords` region is present at `0x216F2F26068` length `12` |
| Source-chain/accessor-family coord recovery | working again after current-session capture; source-chain pattern found at `rift_x64.exe+0x931133`, accessor at `rift_x64.exe+0x685C30` |
| CE Lua server/bootstrap | available during this pass; `cheatengine-exec.ps1 -Code 'return 123'` returned `123` |
| Telemetry preflight | green: memory coords available/valid, memory facing available/valid, effective position source `memory`, effective facing source `memory-facing` |
| Actor yaw / pitch truth | working on current live session via source `0x216F2F26020`; primary forward basis `+0x60/+0x64/+0x68`, duplicate basis `+0x94/+0x98/+0x9C` |
| `--read-player-orientation` reader mode | live mode works when called with explicit `--pid 41220`; artifact-only/no-PID mode remains historical-only |
| Actor-facing provenance | April 30 exact PID/HWND D/A validation confirmed behavior-backed yaw on `0x216F2F26020 @ +0x60/+0x94`; durable owner/source recovery remains unresolved |
| Navigation preflight (`--read-navigation-current`) | green after April 30 lead promotion using `AnchorSource=coord-trace-anchor`, current address `0x216F2F26068`, facing source `0x216F2F26020 @ +0x60` |
| Auto-turn preflight | green after April 30 lead promotion: `-PreflightOnly -AutoTurnBeforeMove` aligned from `42.135°` to `4.702°` with three `d` pulses and no forward movement |
| Active movement (`--navigate-waypoints`) | April 30 smallest active forward smoke passed with current yaw/coord truth: `success`, `StopReason=arrived`, `2` `w` pulses, distance `2.600 -> 1.890` |
| Navigation v3 active route gate | implementation exists, but April 23 active movement proofs are historical after this update; live route-chain promotion remains pending |
| ReaderBridge orientation probe | still not treated as a usable direct yaw/pitch source |
| Camera yaw / pitch / distance on `main` | stale / unverified after the update |
| Authoritative camera controller | not yet isolated |

## April 30 actor-yaw recovery truth

April 30, 2026 live recovery supersedes conflicting April 28 session-bound
addresses below. The older April 28 sections are retained as historical proof
context.

Compact machine-readable truth packet:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-actor-truth.json`
- validation guard:
  - `C:\RIFT MODDING\RiftReader\scripts\validate-current-actor-truth.ps1`

Current live target:

- process: `rift_x64`
- PID: `41220`
- HWND: `0xBD0D94`
- character/location: `Atank` / `Sanctum Watch`

Current proof-grade coord source:

- source object: `0x216F2F26020`
- canonical coord triplet: `0x216F2F26068`
- source coord offset: `+0x48`
- proof-anchor refresh artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-coord-anchor-refresh.json`
- post-active proof-anchor refresh artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-coord-anchor-after-active-forward-smoke.json`
- proof polling watchset artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-polling-watchset-after-yaw-promotion.json`
- post-active proof polling watchset artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\proof-polling-watchset-after-active-forward-smoke.json`
- current default watchset:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\proof-polling-watchset.json`
- required watchset region:
  - `coord-trace-coords` at `0x216F2F26068`, length `12`
- match: `CoordMatchesWithinTolerance=true`
- deltas vs ReaderBridge at refresh:
  - `DeltaX = -0.0043945312`
  - `DeltaY = -0.0009765625`
  - `DeltaZ = 0.0014648438`

Current behavior-backed actor-facing/yaw source:

- source object: `0x216F2F26020`
- primary forward basis: `+0x60/+0x64/+0x68`
- duplicate forward basis: `+0x94/+0x98/+0x9C`
- primary/duplicate agreement after promotion:
  - duplicate delta magnitude: `0.000003339988166361308`
  - duplicate agreement: `true`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

Live exact-window D/A validation:

- validation artifact:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\actor-yaw-candidate-test-da-ahk-700ms.json`
- candidate screen:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\actor-yaw-validation-candidate-screen.json`
- input: exact target AutoHotkey `d` then `a`, `700 ms` holds
- foreground guard: target remained `0xBD0D94` / PID `41220`
- primary basis response:
  - forward yaw delta: about `-129.553°`
  - reverse yaw delta: about `+129.603°`
  - player coord drift: `0.0`
- duplicate basis response:
  - forward yaw delta: about `-129.554°`
  - reverse yaw delta: about `+129.604°`
  - player coord drift: `0.0`
- top pointer-hop candidates were nonresponsive except weak rank 9
  `0x216A250A590 @ +0xD4`, which moved only about `+3.650°/-2.916°`;
  it is not preferred over the owner/source coord object.

Promotion and validation after updating
`C:\RIFT MODDING\RiftReader\scripts\actor-facing-behavior-backed-lead.json`:

- `--read-player-orientation --pid 41220` resolved
  `0x216F2F26020 @ +0x60/+0x94`
- telemetry preflight is green:
  - memory coords valid: `true`
  - facing valid: `true`
  - effective position source: `memory`
  - effective facing source: `memory-facing`
- `--read-navigation-current` is green:
  - current address: `0x216F2F26068`
  - facing status: `available`
  - facing source: `behavior-backed-memory-facing`
  - facing source address: `0x216F2F26020`
  - facing forward basis offset: `0x60`
- turn-only auto-turn preflight is green:
  - script:
    - `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1`
  - mode:
    - `-PreflightOnly -AutoTurnBeforeMove`
  - custom current-session waypoint file:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\autoturn-current-session-waypoints.json`
  - log:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\autoturn-preflight-only.ndjson`
  - start yaw/delta:
    - `1.450°` yaw, `42.135°` absolute delta, turn `right`
  - final yaw/delta:
    - `48.287°` yaw, `4.702°` absolute delta, turn hint `left`
  - pulses:
    - three exact-target `d` pulses at `75 ms`
  - movement:
    - no forward movement was sent; this was preflight-only
- smallest active forward smoke is green:
  - route file:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\active-forward-smoke-waypoints.json`
  - log:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\active-forward-smoke.ndjson`
  - stdout:
    - `C:\RIFT MODDING\RiftReader\scripts\captures\actor-facing-recovery-20260430-110229\active-forward-smoke.stdout.txt`
  - compact summary:
    - `C:\RIFT MODDING\RiftReader\scripts\navigation\summarize-a-to-b-log.ps1 -LogFile <active-forward-smoke.ndjson>`
    - emits `lastNavigationSummary` with status, stop reason, pulse count,
      distances, positions, and computed planar movement
  - command mode:
    - `--navigate-waypoints`
  - status:
    - `success`
  - stop reason:
    - `arrived`
  - anchor source:
    - `coord-trace-anchor`
  - preflight:
    - yaw `48.287°`, bearing `48.287°`, heading delta `0.000°`
  - movement input:
    - two `w` pulses
  - initial/final planar distance:
    - `2.600 -> 1.890`
  - initial position:
    - `X = 7260.58544921875`
    - `Y = 875.6790161132812`
    - `Z = 3052.92138671875`
  - final position:
    - `X = 7261.05712890625`
    - `Y = 875.696533203125`
    - `Z = 3053.451904296875`
  - planar movement:
    - about `0.710`
  - post-active telemetry after proof refresh:
    - memory coords valid: `true`
    - facing valid: `true`
    - effective position source: `memory`
    - effective facing source: `memory-facing`
  - post-active navigation read:
    - current address: `0x216F2F26068`
    - within arrival radius: `true`
    - facing source: `0x216F2F26020 @ +0x60`
    - yaw/bearing delta: about `0.027°`

Operational interpretation:

- `0x216F2F26020 @ +0x60/+0x94` is the current live behavior-backed
  actor-facing/yaw truth for this PID/HWND.
- The old behavior-backed lead `0x216FE3C6280 @ +0xD4` is stale/unreadable in
  this live session and must not be used unless separately re-proven.
- These addresses are still session-bound; after restart/client update,
  refresh proof coord readiness and rerun short exact-target yaw validation
  before treating them as current.
- Durable owner/source recovery is still unresolved.

## Historical April 28 proof coord anchor truth

_Historical: this section is retained as proof context only. April 30, 2026
re-promoted current coord truth to `0x216F2F26068` on source object
`0x216F2F26020`; use the April 30 section above for current live-session
addresses._

April 28 live validation established the then-current proof-grade movement
coord source:

- live process: `rift_x64` PID `41220`
- target window: `0xBD0D94`
- canonical live coord region: `0x216F87CDE18`
- canonical live coord-trace object base: `0x216F87CDE18`
- current trace-linked source object: `0x216F87CDDD0`
- source-object coord offset: `+0x48`
- verification method: `coord-triplet-access`
- match source: `readerbridge-live`
- sample memory coords after final active-proof ReaderBridge refresh:
  - `X = 7449.1753`
  - `Y = 863.58527`
  - `Z = 2973.069`
- ReaderBridge deltas at validation:
  - `DeltaX = -0.0043945312`
  - `DeltaY = -0.004699707`
  - `DeltaZ = -0.00073242193`
- current proof cache file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`

Operational interpretation:

- this validated coord-trace anchor remains the **only** proof-grade movement
  source
- `read-player-current.ps1`, heuristic current-player anchors, and cached
  current-player snapshots remain read-only/exploration aids only
- if a proof watchset does not include this validated coord-trace coord region,
  treat it as a blocker instead of silently accepting a stale/candidate source
- current proof watchset file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\proof-polling-watchset.json`
- the current proof watchset contains required region `coord-trace-coords` at
  `0x216F87CDE18`, length `12`
- active route movement was **not** rerun in this April 28 pass; use the fresh
  proof anchor again immediately before any movement-polling proof

## Historical April 28 source-chain / accessor-family coord evidence

_Historical: retained for recovery pattern/provenance context. Do not treat the
April 28 object addresses below as current unless separately re-proven._

The April 28 current-session source-chain capture rebuilt the coord
source-chain on PID `41220`:

- selected/source object: `0x216F87CDDD0`
- cluster trace instruction: `0x7FF7879B117E`
- cluster pattern offset: `rift_x64.exe+0x931169`
- source container load: `0x7FF7879B1133` / `mov rcx,[rax+78]`
- source object load: `0x7FF7879B1137` / `mov rdi,[rcx+rdx*8]`
- source resolve target: `0x7FF787705C30`
- accessor return offset: `72` (`+0x48`)
- suggested source-chain scan: `rift_x64.exe+0x931133`
- suggested accessor scan: `rift_x64.exe+0x685C30`

Script fix validated in this pass:

- `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1` now uses
  named hashtable splatting when invoking `trace-player-coord-write.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1` now
  uses named hashtable splatting, a 12-byte access watch window, and
  `MaxCandidates=4`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-discovery-chain.ps1` now accepts
  and propagates exact `-ProcessId` / `-TargetWindowHandle` through the
  provenance chain instead of relying on process-name-only defaults
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-accessor-family.ps1`
  and `C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1`
  now support exact target args for reader calls and record the target in their
  output artifacts
- `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1` now
  passes the exact live target into `refresh-discovery-chain.ps1` during
  `-RunProvenance`
- both patched paths were exercised live and then covered by the source-chain
  regression tests listed below

## Historical April 28 actor yaw / pitch truth

_Historical: April 30 re-promoted actor yaw/facing to
`0x216F2F26020 @ +0x60/+0x94`; the April 28 `+0xD4` lead below is stale in the
current April 30 proof packet unless separately re-proven._

April 28 live agentic discovery promoted a then-current session-bound lead:

- canonical live source address: `0x216FE3C6280`
- canonical forward basis row:
  - `X = +0xD4`
  - `Y = +0xD8`
  - `Z = +0xDC`
- canonical formulas:
  - yaw = `atan2(forwardZ, forwardX)`
  - pitch = `atan2(forwardY, sqrt(forwardX^2 + forwardZ^2))`

April 28 live checks on the promoted lead:

- `refresh-actor-facing-discovery.ps1 -RestartSession -StimulusMode AutoHotkey`
  promoted `0x216FE3C6280 @ +0xD4`
- reversible validation observed yaw peaks of about `59.055°` and `74.600°`
  with `0.0` coord drift across one D/A cycle
- `dotnet ... -- --pid 41220 --read-player-orientation --json` resolved the
  same behavior-backed lead
- telemetry preflight used memory-facing from `0x216FE3C6280 @ +0xD4`
- `refresh-actor-facing-discovery.ps1 -RunProvenance -ProcessId 41220
  -TargetWindowHandle 0xBD0D94` completed successfully after exact-target
  plumbing was added
- provenance summary: `SuccessfulSteps=1`, `FailedSteps=0`,
  `ProvenanceStatus=confirmed`

Operational interpretation:

- the April 28 live actor-facing truth was the validated `0xD4` forward row on
  `0x216FE3C6280`
- this is facing-only truth; it is not the movement coord source
- the April 23 actor-facing address `0x12CC0FA0F70 @ +0xD4` and earlier April
  source-chain/accessor-family addresses are historical after the April 28
  client update unless separately re-proven
- the exact-target post-update provenance chain was green for that live
  PID/HWND, but it remains session-bound evidence; rerun it after a client
  restart/update before treating addresses as current again

## Historical April 28 telemetry and navigation validation

_Historical: retained as the earlier post-update movement proof. The April 30
section above is the current actor-yaw/coord truth after the later live
recovery._

April 28 telemetry preflight after final active-proof ReaderBridge refresh on
**April 28, 2026**:

- memory coords available: `true`
- memory coords valid: `true`
- memory facing available: `true`
- facing valid: `true`
- effective position source: `memory`
- effective facing source: `memory-facing`
- position source address: `0x216F87CDE18`
- facing source address: `0x216FE3C6280`
- facing forward basis offset: `0xD4`

Read-only navigation preflight was also validated with the active-proof
current-session smoke waypoint file:

- waypoint file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625\current-session-smoke-waypoints-active-proof.json`
- command mode: `--read-navigation-current`
- anchor source: `coord-trace-anchor`
- current address: `0x216F87CDE18`
- planar distance to smoke destination after active proof: about `1.784`
- arrival radius: `2.1`
- within arrival radius: `true`
- facing source: `0x216FE3C6280 @ +0xD4`
- signed bearing delta before the active proof: about `0.065°`
- suggested turn direction: `right`

Smallest active `--navigate-waypoints` smoke proof also passed:

- runner:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1`
- log:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625\a-to-b-prototype-active-proof.ndjson`
- route file:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625\current-session-smoke-waypoints-active-proof.json`
- status: `success`
- stop reason: `arrived`
- anchor source: `coord-trace-anchor`
- pulse count: `1`
- input: one `w` pulse for `250 ms`
- initial planar distance: `2.5991395661`
- final planar distance: `1.7840590320`
- elapsed: `2406 ms`
- initial position:
  - `X = 7448.36083984375`
  - `Y = 863.5816650390625`
  - `Z = 2973.037109375`
- final position:
  - `X = 7449.17529296875`
  - `Y = 863.5852661132812`
  - `Z = 2973.069091796875`

No active multi-segment route-chain proof was run during this post-update
validation slice.

## Validation commands from this pass

These checks passed after the April 28 update and the small script fixes:

- PowerShell parser checks for:
  - `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1`
  - `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1`
- whitespace check:
  - `git diff --check -- scripts/resolve-proof-coord-anchor.ps1 scripts/capture-player-trace-cluster.ps1`
- source-chain recovery regression:
  - `C:\RIFT MODDING\RiftReader\scripts\test-player-source-chain-recovery.ps1`
- source-chain fresh rebuild regression:
  - `C:\RIFT MODDING\RiftReader\scripts\test-player-source-chain-fresh-rebuild.ps1`
- actor-facing proof suite:
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-proof-suite.ps1`
- navigation proof suite, non-live/default mode:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`
- live exact-target provenance chain:
  - `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1 -RunProvenance -ProcessId 41220 -TargetWindowHandle 0xBD0D94`
- final post-provenance ReaderBridge refresh, proof anchor, telemetry preflight,
  and read-only navigation-current sanity checks
- exact-target proof polling watchset export:
  - `C:\RIFT MODDING\RiftReader\scripts\export-proof-polling-watchset.ps1 -ProcessId 41220 -TargetWindowHandle 0xBD0D94 -Json`
- proof watchset reader smoke:
  - `dotnet ... -- --pid 41220 --record-session --session-watchset-file scripts\captures\proof-polling-watchset.json --session-sample-count 2 --session-interval-ms 100 --json`
- active movement smoke proof:
  - `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1 -ProcessId 41220 -TargetWindowHandle 0xBD0D94 -WaypointFile <active-proof-route> -UseExistingWaypoints -AutoConfirm -SkipRefresh -ArrivalRadius 2.1 -MaxTravelSeconds 5`
- final post-active ReaderBridge refresh, proof anchor, telemetry preflight, and
  read-only navigation-current sanity checks

## Broken, stale, or pending right now

- April 23 live addresses are historical after the April 28 client update:
  - old coord anchor: `0x12C9B02B888`
  - old actor-facing lead: `0x12CC0FA0F70 @ +0xD4`
- active single-segment smoke movement has been re-promoted after the update;
  multi-segment route-chain movement is still pending
- actor-facing selector/source-chain provenance is green only for the current
  live PID/HWND; it is not durable across restarts or future client updates
- proof polling watchset is current for PID `41220` / HWND `0xBD0D94`, but it
  must be rebuilt after client restart/update before movement proof
- camera yaw/pitch/distance on `main` remains stale/unverified after the update
- `--read-player-orientation` without explicit `--pid` / `--process-name`
  remains the historical artifact-only path until the owner/source artifact path
  is rebuilt

## Canonical scripts on `main`

- `C:\RIFT MODDING\RiftReader\scripts\resolve-proof-coord-anchor.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-trace-cluster.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\test-actor-orientation-stimulus.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\profile-actor-orientation-keys.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\post-rift-key.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\refresh-readerbridge-export.ps1`
- `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`

## Evidence folder

Post-update recovery evidence for this pass is under:

- `C:\RIFT MODDING\RiftReader\scripts\captures\post-update-inworld-20260428-141625`

Key files:

- `process-info.json`
- `smart-capture-player-family.stdout.txt`
- `capture-player-source-chain-refreshcluster-size12-max4.stdout.txt`
- `resolve-proof-coord-anchor-after-sourcechain.stdout.txt`
- `resolve-proof-coord-anchor-final-refresh.stdout.txt`
- `read-player-orientation-after-facing-promotion.stdout.txt`
- `telemetry-preflight-after-facing-promotion.stdout.txt`
- `current-session-smoke-waypoints.json`
- `read-navigation-current-current-smoke.stdout.txt`
- `refresh-actor-facing-discovery-runprovenance-exact-target.stdout.txt`
- `refresh-readerbridge-export-post-provenance.stdout.txt`
- `resolve-proof-coord-anchor-post-provenance-after-readerbridge-refresh.stdout.txt`
- `telemetry-preflight-post-provenance-after-readerbridge-refresh.stdout.txt`
- `current-session-smoke-waypoints-post-provenance.json`
- `read-navigation-current-post-provenance-after-readerbridge-refresh.stdout.txt`
- `export-proof-polling-watchset-exact-target.stdout.txt`
- `record-session-proof-watchset-smoke.stdout.txt`
- `watchset-record-session-smoke`
- `current-session-smoke-waypoints-active-proof.json`
- `run-a-to-b-prototype-active-proof.stdout.txt`
- `a-to-b-prototype-active-proof.ndjson`
- `resolve-proof-coord-anchor-after-active-proof.stdout.txt`
- `telemetry-preflight-after-active-proof.stdout.txt`
- `read-navigation-current-after-active-proof.stdout.txt`

## Camera script location note

The currently documented live camera helpers are **not present** on the `main`
worktree during this pass.

The active camera workflow currently lives on:

- branch: `feature/camera-orientation-discovery`
- worktree: `C:\RIFT MODDING\RiftReader_camera_feature`

Relevant scripts there:

- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\find-live-camera-angle-candidates.ps1`
- `C:\RIFT MODDING\RiftReader_camera_feature\scripts\test-camera-stimulus.ps1`

Do not treat camera outputs as current truth on `main` until the camera path is
revalidated on the updated client.
