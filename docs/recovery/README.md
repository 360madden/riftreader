# Recovery

Start here if artifacts, notes, or workflow state drift or get corrupted.

Last reviewed: May 8, 2026.

## Coordinate freshness rule

Do not treat a stored coordinate from
`C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`,
`run-summary.json`, or another artifact as current just because PID/HWND still
match. PID/HWND/process-start match is only a targeting preflight.

The required quick stale/non-stale check is **API-now vs memory-now**:

1. Sample a fresh live API/runtime coordinate now.
2. Immediately read memory from the current proof candidate/anchor.
3. Compare X/Y/Z deltas.
4. Pass only when the API source is freshness-proven and all deltas are within
   tolerance.
5. Otherwise fail closed, block movement, and treat the artifact coordinate as a
   timestamped snapshot/reacquisition seed.

Fresh API/runtime sources include a freshness-proven ChromaLink
`/api/v1/riftreader/world-state` response, an explicitly live ReaderBridge or
in-game runtime surface, or another current telemetry stream. They do **not**
include SavedVariables, `ReaderBridgeExport.lua`, `rift.cfg`, screenshots, or an
old run summary.

Every freshness result should record API coordinate/timestamp/source, memory
coordinate/timestamp/address/candidate, PID/HWND/process identity, per-axis
deltas, tolerance, and verdict.

## Current no-CE coord proof note

As of the May 8, 2026 current-PID lane, start coord-truth recovery with:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
- newest handoff:
  `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-08-232000-final-push-handoff.md`

The latest live target captured in this lane is `rift_x64` PID `49504` / HWND
`0x5121A` while that client remains alive. Current-session forward movement is
validated through `Forward250`, refreshed `ForwardSeries3x250`, and a 2m
observed-forward `--navigate-waypoints` smoke. The waypoint smoke used a route
built from current-session observed W-key displacement, not actor-facing truth,
and arrived within the `0.75m` radius after 4 pulses. A later durable-summary
waypoint run also passed with `5` pulses, stop reason `arrived`, final planar
distance `0.3942869934100385m`, and wrote
`C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\navigate-waypoints-run-summary.json`.
Auto-turn remains blocked because the behavior-backed actor-facing lead is stale
for PID `49504` and no turn backend is promoted.

Current proof-pointer candidate source:

- candidate: `api-coord-hit-000005`
- current absolute address: `0x24A01358880`
- candidate file:
  `C:\RIFT MODDING\RiftReader\scripts\captures\reacquire-currentpid-49504-20260508-211304\api-bootstrap-vec3-candidates.json`
- tracked pointer:
  `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
- latest no-input proof summary:
  `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-031334\run-summary.json`
- latest movement proof summaries:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260509-020624\run-summary.json`
  - `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\navigate-waypoints-result-transcript.json`
  - `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\navigate-waypoints-run-summary.json`
- latest waypoint route/readback:
  - route: `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\smoke-test-waypoints-2m-observed-forward.json`
  - post-run read: `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\post-navigation-read-current.json`
- latest visual-baseline gate:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260508-231046\visual-gate-status.json`
  - rerun with `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full`

Navigation-specific stale snapshot rule: `ReaderBridgeExport.lua` is a post-save
SavedVariables snapshot, not live IPC. Navigation read/move modes now ignore the
default ReaderBridge SavedVariables snapshot unless a snapshot path is explicitly
provided; proof-grade currentness should come from the current proof coord anchor
or another freshness-proven live surface.

RiftScan is a read-only provider for RiftReader unless the user explicitly
authorizes a RiftScan edit/capture/write pass. Use
`C:\RIFT MODDING\RiftReader\scripts\riftscan_coordination.py` for a read-only
coordination checkpoint, `C:\RIFT MODDING\RiftReader\scripts\riftscan_feedback.py`
for a RiftReader-owned provider feedback packet, and
`C:\RIFT MODDING\RiftReader\scripts\riftscan_milestone_review.py` after each
major milestone before expanding discovery scope. Before committing a
coordination milestone, run
`C:\RIFT MODDING\RiftReader\scripts\validate_riftscan_coordination.py` with
`--write-summary --write-markdown --update-latest-pointer` to rerun and
persist the no-CE/read-only validation suite plus
`scripts\captures\latest-riftscan-validation.json`. Do not run wrappers in a mode that
creates new RiftScan sessions/reports when the boundary is read-only; pass an
existing `-CandidateFile`.

Movement remains allowed only after the visual-baseline gate passes and then the
current proof-anchor readback preflight is rerun for the exact live PID/HWND
because the proof age gate is short-lived. CE plus SavedVariables live-truth
paths remain forbidden for this lane.

For player actor-yaw discovery, use
`C:\RIFT MODDING\RiftReader\docs\player-actor-yaw-candidate-ledger.md` as the
ledger evidence contract. The ledger can downrank candidate yaw sources before
behavior validation, but it cannot promote actor-facing truth; promotion still
requires behavior-backed yaw proof plus
`C:\RIFT MODDING\RiftReader\scripts\test-actor-facing-proof-suite.ps1`.
The current promoted actor-yaw disambiguation packet is
`C:\RIFT MODDING\RiftReader\docs\recovery\current-actor-yaw-disambiguation.json`;
validate it against the behavior-backed lead with
`python C:\RIFT MODDING\RiftReader\scripts\validate_current_actor_yaw_disambiguation.py`
before treating `scripts\actor-facing-behavior-backed-lead.json` as current
actor-facing truth. For a compact operator view, run
`python C:\RIFT MODDING\RiftReader\scripts\actor_yaw_current_truth_status.py --json`.
For a no-input live readback smoke against an exact target, run
`python C:\RIFT MODDING\RiftReader\scripts\actor_yaw_readback_smoke.py --pid <PID> --hwnd <HWND> --process-name rift_x64 --json`.
The smoke refuses output paths inside RiftScan and updates
`C:\RIFT MODDING\RiftReader\scripts\captures\latest-actor-yaw-readback-smoke.json`
when it runs with default pointer behavior.

## Historical May 6/7 no-CE proof note

Historical only: the May 6/7 resumed no-CE forward-proof lane used
`rift_x64` PID `47560` / HWND `0x2122E`. It refreshed proof through the
user-corrected RiftScan-first candidate workflow without Cheat Engine and
without SavedVariables live truth. That lane promoted RiftScan candidate
`rift-addon-coordinate-candidate-000001` at `0x2400EA32120` from:

- RiftScan session: `C:\RIFT MODDING\Riftscan\sessions\codex-current-coord-region-passive-20260506-230940`
- RiftScan match file: `C:\RIFT MODDING\Riftscan\reports\generated\codex-current-coord-region-passive-20260506-230940-addon-coordinate-matches.json`
- proof anchor: `C:\RIFT MODDING\RiftReader\scripts\captures\telemetry-proof-coord-anchor.json`
- latest readback: `C:\RIFT MODDING\RiftReader\scripts\captures\proof-anchor-currentpid-47560-readback-summary-20260506-232245.json`
- tracked pointer: `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`

The May 6/7 proof-gated `1000 ms W` pulse passed and moved the validated proof
coordinate by planar distance `1.2391483387792066`, but those PID/address values
are not current-session truth after the May 8 PID `33912` reacquisition.

## Current post-update note

After the April 14, 2026 game update:

- `player-current` and the coord-anchor module pattern still survived
- the source-chain / selector-owner / owner-components refresh path drifted
- the April 22, 2026 recovery passes rebuilt the source-chain/accessor-family
  lane strongly enough to restore actor-facing truth
- the April 23, 2026 agentic actor-facing refresh pass promoted the current
  live lead again and refreshed the selector-owner / owner-components /
  owner-graph / stat-hub provenance lane on the same session
- navigation preflight now reuses that live actor-facing truth for a read-only
  turn hint, and `--navigate-waypoints` can now opt into pre-movement
  auto-turn; the first deliberately misaligned live correction proof plus
  forward-travel handoff passed in `navigation-prototype-20260423-195303-923`
- camera notes below the recovery layer should still be treated as historical
  until rebuilt

Start with:

- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-post-update-anchor-drift-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-14-camera-workflow-branch-audit.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-22-actor-facing-source-chain-behavior-backed-lead.md`

## Native screenshot recovery note

For screenshot or visual-capture blockers, use
`C:\RIFT MODDING\RiftReader\docs\recovery\native-rift-screenshot-backend.md`.
The current RIFT native screenshot key is `NUM PAD *`; `Ctrl+P`, `PrtSc`, and
Snipping Tool automation are forbidden for RiftReader screenshot workflows.

## Use these files only

1. `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
2. `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
3. `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md`
4. `C:\RIFT MODDING\RiftReader\docs\recovery\artifact-tiers.md`
5. `C:\RIFT MODDING\RiftReader\docs\navigation-waypoint-v1.md` when the task
   touches movement, preflight, smoke routes, or auto-turn behavior
6. `C:\RIFT MODDING\RiftReader\docs\player-actor-yaw-candidate-ledger.md`
   when the task touches player actor-yaw discovery candidate evidence,
   ledger penalties, or pre-promotion yaw ranking
7. `C:\RIFT MODDING\RiftReader\docs\recovery\current-actor-yaw-disambiguation.json`
   when the task touches promoted current-session actor-yaw truth

## Rules

- `current-truth.md` = what is true right now
- `current-proof-anchor-readback.json` = tracked pointer to the latest validated
  current-readback coordinate proof
- `rebuild-runbook.md` = what order to rebuild in
- `artifact-tiers.md` = what to preserve vs regenerate vs ignore
- `C:\RIFT MODDING\RiftReader\docs\analysis\README.md` = how to record dated
  update/drift investigations without overwriting current truth
- historical handoff docs are background only unless one of the files above sends you there

## Camera branch note

The current live camera workflow is branch-specific:

- living recovery truth stays on `main`
- the active camera discovery scripts currently live on
  `feature/camera-orientation-discovery`
- inspected worktree path:
  `C:\RIFT MODDING\RiftReader_camera_feature`
