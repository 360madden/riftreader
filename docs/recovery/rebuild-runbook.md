# Rebuild Runbook

Use this order when you need to reconstruct the active state.

## 0. After a game update, triage the surviving baselines first

```powershell
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --readerbridge-snapshot --json
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-current --json
dotnet run --project C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\RiftReader.Reader.csproj -- --process-name rift_x64 --read-player-coord-anchor --json
```

Expected during the current post-update state:

- ReaderBridge snapshot should still load
- player-current should still match ReaderBridge
- coord-anchor should still find the module-local pattern, even if the absolute
  instruction address changed

For proof-grade movement / polling on the current process:

- the validated coord-trace anchor remains the required source of truth
- active movement (`--navigate-waypoints`) now fails closed unless that
  coord-trace anchor is available for the current process
- cached player-current / player-signature anchors are no longer accepted as
  live movement proof, even though read-only helpers may still surface them as
  fallback anchors

If these fail, stop and fix the reader baseline before trusting any
owner/source/camera artifact.

When a fresh coord trace is required on the current client, prefer:

```powershell
C:\RIFT MODDING\RiftReader\scripts\trace-player-coord-write.ps1 -Json -WatchMode access -StimulusMode AutoHotkey
```

That path is still **debugger-assisted breakpoint tracing**. It currently works
best with CE `debug-register` breakpoints. Treat VEH/page-exception as an
exploratory/manual path, not the canonical proof route, and avoid running other
debugger-class tools against `rift_x64` at the same time.

The default write/PostMessage path can still arm successfully without ever
producing a verified hit on the current build. If a `/reloadui` refresh just
ran, wait until `--read-player-current` succeeds again before refreshing the
coord trace or disassembly cluster.

If the current-process trace artifact still validates but the full
`resolve-proof-coord-anchor.ps1` refresh path cannot reacquire a fresh trace,
use `--read-player-coord-anchor` to confirm the live coord-trace anchor first,
then refresh the proof cache / watchset from that validated current-process
anchor before any movement-proof run.

## 1. Build the repo

```powershell
dotnet build C:\RIFT MODDING\RiftReader\RiftReader.slnx
```

## 2. Refresh actor-facing live truth and provenance

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-source-chain.ps1 -Json -RefreshCluster
C:\RIFT MODDING\RiftReader\scripts\capture-player-source-accessor-family.ps1 -Json
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-components.ps1 -Json -RefreshSelectorTrace
C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1 -RestartSession -StimulusMode AutoHotkey
C:\RIFT MODDING\RiftReader\scripts\refresh-actor-facing-discovery.ps1 -RunProvenance
C:\RIFT MODDING\RiftReader\scripts\assert-actor-facing-truth.ps1 -Json
```

Healthy result:

- `player-source-chain.json`
- `player-source-accessor-family.json`
- `player-selector-owner-trace.json`
- `player-owner-components.json`
- `scripts\captures\actor-facing-discovery\session.json`
- promoted/retained `scripts\actor-facing-behavior-backed-lead.json`

Current post-update warning:

- if `capture-player-source-chain.ps1` or
  `capture-player-source-accessor-family.ps1` cannot emit either a fresh
  same-session source chain or a same-session recovery-mode reuse, stop and mark
  provenance stale
- if `capture-player-source-chain.ps1` emits
  `Recovery.Mode = rebuild-from-suggested-source-chain-pattern`, treat that as
  a fresh same-session source-chain rebuild from the last-good suggested pattern
- if `capture-player-source-chain.ps1` emits
  `Recovery.Mode = reuse-previous-source-chain`, treat that as a same-session
  fallback only after the fresh pattern-scan rebuild path failed
- if `trace-player-selector-owner.ps1` remains `armed` without a hit, stop and
  mark the selector-owner / owner-components chain stale
- if `capture-player-trace-cluster.ps1 -RefreshTrace` fails immediately after a
  `/reloadui`, wait for current-player recovery and rerun it; the cluster
  refresh now retries briefly, but it still depends on a fully loaded character
  state

Preferred live-truth flow on the current client:

- `refresh-actor-facing-discovery.ps1 -RestartSession -StimulusMode AutoHotkey`
  is now the single operator-facing conductor for Discover -> Validate ->
  Promote -> Confirm
- `refresh-actor-facing-discovery.ps1 -RunProvenance` reuses the current lead,
  skips fresh stimulus, and refreshes the provenance lane without trying to
  replace live actor-facing truth
- `assert-actor-facing-truth.ps1 -Json` is the one-shot same-session proof check
  for the current live lead, capture parity, reader parity, and provenance
  posture
- `test-actor-facing-proof-suite.ps1` runs the actor-facing truth-proof
  regression checks plus the current source-chain recovery / fresh rebuild
  self-checks in one command
- once the current actor-facing lead is green, `--read-navigation-current` now
  returns a read-only facing-aware preflight summary with current yaw, heading
  delta, and suggested turn direction when the live behavior-backed lead is
  available; this is still read-only preflight data, but it now also powers
  opt-in reader-core auto-turn on `--navigate-waypoints`
- `--navigate-waypoints --auto-turn-before-move` is now the current v2-aligned
  reader-core path for pre-movement heading alignment; keep it opt-in, keep it
  strict on the validated coord-trace anchor, and expect it to fail closed if
  the heading gets worse across consecutive turn pulses
- the tuning switches (`--auto-turn-within-degrees`, `--turn-left-key`,
  `--turn-right-key`, `--turn-pulse-ms`, `--turn-post-sample-delay-ms`,
  `--turn-max-pulses`, `--turn-worsening-tolerance`,
  `--turn-max-worsening-pulses`) should be treated as refinement knobs, not as
  permission to weaken the fail-closed behavior
- the prototype wrapper `C:\RIFT MODDING\RiftReader\scripts\navigation\run-a-to-b-prototype.ps1`
  remains a higher-level helper around the same facing-aware preflight /
  auto-turn concept
- `C:\RIFT MODDING\RiftReader\scripts\navigation\test-navigation-proof-suite.ps1`
  is now the one-command navigation hardening pass for the smoke-route,
  facing-aware preflight, and current auto-turn-preflight path
- before calling navigation v3-ready, deliberately validate one live
  **misaligned** smoke route where reader-core auto-turn actually sends turn
  pulses, improves the heading delta, and still hands off cleanly to strict
  coord-trace-based forward movement
- Lane A (live truth) may stay green even when the raw source-chain step falls
  back to `rebuild-from-suggested-source-chain-pattern` or, only if that fails,
  same-session recovery-mode reuse; Lane B (provenance) is where that
  distinction matters
- do not promote stale selector-owner / owner-components artifacts as current
  actor-facing truth

## 3. Refresh the core graph artifacts

```powershell
C:\RIFT MODDING\RiftReader\scripts\capture-player-owner-graph.ps1 -Json -RefreshSelectorTrace
C:\RIFT MODDING\RiftReader\scripts\capture-player-stat-hub-graph.ps1 -Json -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader\scripts\inspect-capture-consistency.ps1 -Json
```

Run this step only after step 2 succeeds on the current game build.

## 4. Verify the live camera read path

```powershell
C:\RIFT MODDING\RiftReader_camera_feature\scripts\read-live-camera-yaw-pitch.ps1 -Json
```

Expected:
- yaw = direct
- pitch = derived
- distance = derived

Current post-update note:

- the active live camera scripts currently live on
  `feature/camera-orientation-discovery`, not on the `main` worktree
- do not treat older camera outputs as current until this step succeeds on the
  updated client

## 5. Rebuild controller-search helpers if needed

```powershell
C:\RIFT MODDING\RiftReader_camera_feature\scripts\search-camera-global.ps1 -Json -RefreshOwnerGraph -RefreshHubGraph -RefreshOwnerComponents
C:\RIFT MODDING\RiftReader_camera_feature\scripts\generate-camera-probe.ps1 -Json
C:\RIFT MODDING\RiftReader_camera_feature\scripts\capture-camera-memory-dump.ps1 -Json
```

## Missing-file shortcuts

- missing `player-owner-components.json` -> do step 2
- missing `player-owner-graph.json` or `player-stat-hub-graph.json` -> do step 3
- missing camera helper outputs -> do steps 4 and 5
- missing old notes -> rebuild the current state first, then compare history later

## Operator note

`refresh-readerbridge-export.ps1` may use UI-intrusive chat/reload helper
behavior. Prefer an already-fresh ReaderBridge export when possible, and do not
use chat/reload helpers for unattended live camera probing unless that
disruption is explicitly acceptable.
