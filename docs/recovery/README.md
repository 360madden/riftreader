# Recovery

Start here if artifacts, notes, or workflow state drift or get corrupted.

Last reviewed: May 8, 2026.

## Current no-CE coord proof note

As of the May 8, 2026 current-PID lane, start coord-truth recovery with:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
- newest handoff:
  `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-08-063335-current-pid-33912-visible-hud-proof-passed-handoff.md`

The latest live target is `rift_x64` PID `33912` / HWND `0xE0DB2` while that
client remains alive. Current-session coordinate truth is movement-grade through
the previous `Forward250`, `ForwardSeries3x250`, fixed-bearing 1m waypoint
smoke, and fixed-bearing 2m waypoint smoke. The latest visible-HUD `ProofOnly`
run sent no movement and passed on the same target. Auto-turn remains blocked
because no turn backend is promoted.

Current RiftScan-backed candidate source:

- candidate: `rift-addon-coordinate-candidate-000001`
- current absolute address: `0x202FEA3E180`
- RiftScan match file:
  `C:\RIFT MODDING\Riftscan\reports\generated\currentpid-33912-reacquire-exact16m-20260508-042613-addon-coordinate-matches.json`
- tracked pointer:
  `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
- latest visible-HUD proof summary:
  `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260508-103043\run-summary.json`

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

Movement remains allowed only after rerunning the current proof-anchor readback
preflight for the exact live PID/HWND because the proof age gate is short-lived.
CE plus SavedVariables live-truth paths remain forbidden for this lane.

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
