# Recovery

Start here if artifacts, notes, or workflow state drift or get corrupted.

Last reviewed: May 9, 2026 01:05 EDT / May 9, 2026 05:05 UTC.

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

<!-- RIFTREADER_CURRENT_PID_FAMILY_RECOVERY_POLICY_START -->
## Current-PID coordinate-family recovery rule

When `ProofOnly` blocks with target drift, PID mismatch, HWND mismatch, or a restarted RIFT client, the tracked proof pointer is stale for the new process epoch. Do **not** probe only the old absolute address or nearby offsets.

Use the broad current-PID coordinate-family recovery policy instead:

1. prove the new PID/HWND with target-control and visual gate;
2. capture a fresh live `RRAPICOORD` / API-runtime coordinate reference;
3. run `scripts/scan_current_pid_coordinate_family.py` against the current PID/HWND;
4. validate the resulting `api-family-vec3-candidates.jsonl` across poses;
5. promote the proof anchor only after multi-pose no-CE validation;
6. run same-target `ProofOnly` before updating current truth.

Durable policy: `docs/recovery/current-pid-coordinate-family-recovery-policy.md`.

A candidate family file is not movement permission. Movement remains blocked until target-control, visual gate, current proof preflight, and same-target `ProofOnly` pass.
<!-- RIFTREADER_CURRENT_PID_FAMILY_RECOVERY_POLICY_END -->

<!-- RIFTREADER_NON_CODEX_WORKFLOW_POLICY_START -->
## Non-Codex desktop ChatGPT workflow rule

When Codex is not being used, repo changes must follow the local package workflow:

1. ChatGPT inspects GitHub/read-only context and pasted local output;
2. ChatGPT provides a downloadable ZIP or local applier content;
3. the user applies it locally in `C:\RIFT MODDING\RiftReader`;
4. the user reviews `git status`, `git diff`, and `git diff --check`;
5. the user commits and pushes with explicit paths;
6. ChatGPT verifies the pushed commit through the GitHub connector read-only.

The GitHub connector is read-only in this lane unless the user explicitly authorizes a write in the current turn. Durable workflow doc: `docs/workflow/non-codex-desktop-chatgpt-workflow.md`.
<!-- RIFTREADER_NON_CODEX_WORKFLOW_POLICY_END -->

## Current no-CE coord proof note

As of the May 8, 2026 current-PID lane, start coord-truth recovery with:

- `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
- `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
- newest handoff:
  `C:\RIFT MODDING\RiftReader\docs\handoffs\2026-05-09-010500-visual-gate-focus-blocker-handoff.md`

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

The current C# waypoint movement path now selects a native exact-HWND
`WindowMessageMovementBackend` for targets with a resolved HWND. The old
`PowerShellMovementBackend` / `post-rift-key.ps1` path remains only as the
no-HWND fallback. This backend is now live-validated for no-turn observed-forward
waypoint movement via the native exact-HWND path; rerun the visual gate and
fresh `ProofOnly` before any further live input.
The latest visual gate retry is currently blocked, so live input remains
disabled until foreground focus plus desktop/window capture are restored and a
new full visual gate returns `readyForLiveInput=true`.

Current proof-pointer candidate source:

- candidate: `api-coord-hit-000005`
- current absolute address: `0x24A01358880`
- candidate file:
  `C:\RIFT MODDING\RiftReader\scripts\captures\reacquire-currentpid-49504-20260508-211304\api-bootstrap-vec3-candidates.json`
- tracked pointer:
  `C:\RIFT MODDING\RiftReader\docs\recovery\current-proof-anchor-readback.json`
- latest no-input proof summary:
  `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ProofOnly-20260509-042916\run-summary.json`
- latest movement proof summaries:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\live-test-ForwardSeries3x250-20260509-020624\run-summary.json`
  - `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-smoke-currentpid-49504-20260508-2218-2m\navigate-waypoints-result-transcript.json`
  - `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\navigate-waypoints-run-summary.json`
- latest waypoint route/readback:
  - route: `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\smoke-test-waypoints-2m-observed-forward.json`
  - post-run read: `C:\RIFT MODDING\RiftReader\scripts\captures\navigation-summary-currentpid-49504-20260508-2312\post-navigation-read-current.json`
- latest visual-baseline gate:
  - `C:\RIFT MODDING\RiftReader\scripts\captures\visual-gate-currentpid-49504-20260509-010348\visual-gate-status.json`
  - current status: `blocked-visual-baseline`; `focusConfirmedForeground=false`; blockers include `focus-window-not-foreground`, `desktop-capture-access-denied`, `desktop-copyfromscreen-invalid-handle`, `capture-methods-return-black-or-flat-content`; rerun with `python .\scripts\check_live_visual_gate.py --pid 49504 --hwnd 0x5121A --process-name rift_x64 --title-contains RIFT --full` after restoring foreground focus and capture access.

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

## x64dbg pointer-chain discovery note

x64dbg is available at `C:\RIFT MODDING\Tools\x64dbg` for bounded
debugger-assisted pointer-chain discovery. Treat it as a debugger-class live
tool: do not attach to `rift_x64.exe` unless the user explicitly approves a
live-debugger session in the current conversation, do not use it at the same
time as Cheat Engine debugger/watchpoints, and do not promote x64dbg evidence
without fresh API/runtime comparison plus multi-pose and restart validation.

Durable workflow doc:
`C:\RIFT MODDING\RiftReader\docs\recovery\x64dbg-pointer-chain-workflow.md`.

Claude/Codex adaptation and source-reference index:
`C:\RIFT MODDING\RiftReader\docs\recovery\x64dbg-mcp-claude-to-codex-adaptation.md`.

Current read-only x64dbg Automate helper status:
`C:\RIFT MODDING\RiftReader\docs\recovery\x64dbg-automate-readonly-helper-2026-05-12.md`.

Repo-owned x64dbg static-chain helpers:

- `C:\RIFT MODDING\RiftReader\scripts\x64dbg_coord_chain_plan.py` prepares an
  artifact-only plan from a current coordinate candidate.
- `C:\RIFT MODDING\RiftReader\scripts\x64dbg_access_event_ingest.py` ingests
  manually captured x64dbg access events into a candidate-only packet.
- `C:\RIFT MODDING\RiftReader\scripts\x64dbg_static_chain_resolve.py` is an
  offline resolver harness for real x64dbg-derived `derivedChain` packets. It
  blocks without module/RVA/static-owner evidence and currently performs
  offline memory-image readback only.

Current static-chain status:
`C:\RIFT MODDING\RiftReader\docs\recovery\x64dbg-static-coord-chain-discovery-status-2026-05-12.md`.
Planner, ingester, and resolver harness are schema-ready, but no stable static
coordinate chain has been discovered or promoted. Do not build or promote from a
candidate template, heap-only watch address, or guessed offsets.

None of these helpers attaches x64dbg, sends input, configures MCP, or promotes
movement truth.

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
8. `C:\RIFT MODDING\RiftReader\docs\recovery\x64dbg-pointer-chain-workflow.md`
   when the task touches debugger-assisted pointer-chain discovery
9. `C:\RIFT MODDING\RiftReader\docs\recovery\x64dbg-mcp-claude-to-codex-adaptation.md`
   when the task touches x64dbg Automate MCP, Claude-style x64dbg skills, or
   Codex/Desktop ChatGPT adaptation of those workflows
10. `C:\RIFT MODDING\RiftReader\docs\recovery\x64dbg-automate-readonly-helper-2026-05-12.md`
    when the task touches the read-only x64dbg Automate helper, local plugin
    setup, or the still-deferred active MCP configuration
11. `C:\RIFT MODDING\RiftReader\scripts\x64dbg_coord_chain_plan.py`
    when preparing an artifact-only x64dbg plan for static coordinate
    pointer-chain discovery from a current candidate address
12. `C:\RIFT MODDING\RiftReader\scripts\x64dbg_access_event_ingest.py`
    when normalizing manually captured x64dbg coordinate access events into a
    candidate-only packet
13. `C:\RIFT MODDING\RiftReader\scripts\x64dbg_static_chain_resolve.py`
    when resolving a real x64dbg-derived static coordinate chain packet through
    offline/repo-owned resolver gates without x64dbg or movement

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

<!-- RIFTREADER_CSHARP_SENDINPUT_SCANCODE_PROOF_20260511_START -->
## C# SendInput ScanCode proof — 2026-05-11

The repo now has proof-backed C# `SendInput` ScanCode movement evidence.

- Tool: `tools/RiftReader.SendInput`
- Wrapper: `scripts/send-rift-key-csharp.ps1`
- Commit: `06d82cd29bc173d4145829513b8eb521c0d9c6f5`
- Method: `--input-mode ScanCode --key w --hold-ms 750`
- Target: `rift_x64` PID `35728`, HWND `0x60E42`
- Result: `passed-csharp-sendinput-scancode-displacement`
- Measured planar displacement: `0.9469551256527897`
- Fresh API-coordinate before/after proof:
  - before: `7405.9297, 871.78, 3028.05`
  - after: `7405.0498, 871.78, 3027.7`
- Automatic `Esc`: not used.
- Cheat Engine: not used.
- SavedVariables live truth: not used.

See `docs/recovery/csharp-sendinput-scancode-proof-2026-05-11.md` and `.json`.

Policy: C# `RiftReader.SendInput` with ScanCode is the preferred SendInput diagnostic path. Legacy `scripts/send-rift-key.ps1` is superseded for serious SendInput testing. `post-rift-key.ps1 -SkipBackgroundFocus -UseWindowMessage` remains a working exact-HWND window-message backend.
<!-- RIFTREADER_CSHARP_SENDINPUT_SCANCODE_PROOF_20260511_END -->
