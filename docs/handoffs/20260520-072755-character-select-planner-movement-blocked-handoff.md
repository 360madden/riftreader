# RiftReader handoff — character-select planner + movement blocked

Created: 2026-05-20 07:27:55 -04:00
Repo: `C:\RIFT MODDING\RiftReader`
Branch/head: `main` at `c80cd92 Add MCP final maintenance handoff`

## TL;DR

- RIFT is currently detected at **character selection**, not in the in-game world.
- Current live target epoch:
  - PID: `60636`
  - HWND: `0xC51368`
  - title: `RIFT`
  - process start UTC: `2026-05-20T11:02:20.5639279Z`
  - client size: `640x360`
- `docs/recovery/current-proof-anchor-readback.json` is intentionally blocked with `status=blocked-target-not-in-world`.
- `docs/recovery/current-truth.json` is intentionally blocked with `status=target_present_character_select_movement_blocked_reacquisition_required`.
- Prior PID `1948` / HWND `0x3C0D58` proof is archived/historical only:
  `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-proof-anchor-readback-2026-05-20-pid1948-hwnd3C0D58-historical.json`
- Movement/navigation automation remains **paused**.
- Legacy `WindowMessage` movement is retired/fail-closed after the spin incident.
- C# `SendInput` `ScanCode` via `scripts/send-rift-key-csharp.ps1` is promoted only for bounded diagnostic movement-key tests after exact target/freshness gates.
- A new dry-run-only character-select automation planner was added. It does not click anything.

## Current screen/environment truth

Latest character-select environment artifact:

- JSON:
  `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-071701\character-select-automation-env-summary.json`
- Annotated screenshot:
  `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-071701\character-select-automation-targets-annotated-v2.png`
- Corrected Play crop:
  `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-071701\play-button-crop-corrected-6x.png`

Visible roster from the current capture:

| Slot | Character | Selected | Client click |
|---:|---|---:|---|
| 1 | `SYRACUSE` | false | `[75, 27]` |
| 2 | `CEBU` | false | `[75, 74]` |
| 3 | `ATANK` | true | `[75, 121]` |
| 4 | `SHADOWKORN` | false | `[75, 169]` |
| 5 | `ALBANIA` | false | `[75, 216]` |

Important measured target:

| Target | Client bbox | Client click | Rule |
|---|---|---|---|
| Large Play button | `[476, 329, 558, 357]` | `[517, 343]` | Use only after explicit approval to enter world. |

Coordinate conversion for this exact window instance:

```text
screenX = clientRect.left + clientX
screenY = clientRect.top  + clientY
clientRect = left 13, top 37, right 653, bottom 397
```

Prefer client-coordinate actions through the MCP/window layer, not raw screen clicks, after recapturing and revalidating geometry.

## New dry-run planner added

Files added:

| File | Purpose |
|---|---|
| `C:\RIFT MODDING\RiftReader\scripts\character_select_automation_plan.py` | CLI wrapper. |
| `C:\RIFT MODDING\RiftReader\scripts\rift_live_test\character_select_automation_plan.py` | Fail-closed dry-run planner implementation. |
| `C:\RIFT MODDING\RiftReader\scripts\test_character_select_automation_plan.py` | Targeted unit tests. |

Latest dry-run output:

| Artifact | Path |
|---|---|
| Plan JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-plan\run-20260520-112635-312184\character-select-automation-plan-summary.json` |
| Plan Markdown | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-plan\run-20260520-112635-312184\character-select-automation-plan.md` |

Dry-run verdict:

| Field | Value |
|---|---|
| `status` | `planned` |
| `targetCharacter` | `ATANK` |
| `selectedAlready` | `true` |
| `planOnly` | `true` |
| `willExecuteLiveActions` | `false` |
| `mouseClickSent` | `false` |
| `worldEntryClicked` | `false` |
| `movementAllowed` | `false` |

Planned future sequence from the dry-run artifact:

1. Bind/verify exact target window.
2. Verify character-select landmarks.
3. Keep `ATANK` selected because it is already selected.
4. Future approved action only: click Play at client `[517, 343]`.
5. Wait for world load.
6. Run current-PID ProofOnly before any movement.

## Movement/input truth

Current safe interpretation:

| Area | Truth |
|---|---|
| Route/navigation automation | Blocked/paused. |
| Movement gate | `allowed=false`. |
| Current proof pointer | Blocked because target is not in world. |
| SavedVariables | Not live truth. |
| CE/x64dbg | Not used; do not attach unless explicitly reauthorized. |
| Legacy `WindowMessage` movement | Retired/fail-closed after spin incident. |
| C# ScanCode backend | Allowed only for bounded diagnostics after fresh exact target/freshness gates. |

Important C# diagnostic evidence from earlier in the session:

| Key | Binding | Result | Artifact |
|---|---|---|---|
| `W` | Move Forward | Passed bounded diagnostic | `C:\RIFT MODDING\RiftReader\.riftreader-local\spin-diagnosis\csharp-w-test\csharp-w-test-summary.json` |
| `Q` | Strafe Left | Passed bounded diagnostic; spatial delta about `1.7443m` | `C:\RIFT MODDING\RiftReader\.riftreader-local\q-key-retest-csharp\clean-run-20260519-222554\q-retest-summary.json` |

Do **not** infer route/navigation safety from those tests. They only prove the C# ScanCode key path can send bounded diagnostic input under the tested conditions.

## Validation run after planner addition

| Command | Result |
|---|---|
| `python -m unittest .\scripts\test_character_select_automation_plan.py` | Passed, `5 tests OK`. |
| `python .\scripts\character_select_automation_plan.py --env-summary '.riftreader-local\character-select-automation-env\run-20260520-071701\character-select-automation-env-summary.json' --target-character ATANK --plan-enter-world --json` | Passed; wrote dry-run plan. |
| `git --no-pager diff --check -- scripts\character_select_automation_plan.py scripts\rift_live_test\character_select_automation_plan.py scripts\test_character_select_automation_plan.py` | Passed. |

Previously validated in this overall slice:

| Command | Result |
|---|---|
| `python -m unittest .\scripts\test_coordinate_recovery_status.py` | Passed, `6 tests OK`. |
| `python .\scripts\validate_current_truth.py --json` | Passed. |
| `python .\scripts\coordinate_recovery_status.py --json` | Blocked as expected while target is not in world. |

## Current git/worktree state

The worktree is dirty. This handoff does not stage or commit anything.

Known modified tracked files at handoff time include:

```text
configs/live-test-profiles.json
docs/recovery/csharp-sendinput-scancode-proof-2026-05-11.json
docs/recovery/csharp-sendinput-scancode-proof-2026-05-11.md
docs/recovery/current-proof-anchor-readback.json
docs/recovery/current-truth.json
docs/recovery/current-truth.md
scripts/coordinate_recovery_status.py
scripts/current_pid_family_snapshot_sequence.py
scripts/invoke-gated-forward-smoke.ps1
scripts/profile_turn_keys.py
scripts/rift_live_test/actor_yaw_current_truth_status.py
scripts/rift_live_test/actor_yaw_readback_smoke.py
scripts/rift_live_test/riftscan_coordination.py
scripts/rift_live_test/runner.py
scripts/rift_live_test/turn_keys.py
scripts/rift_live_test/x64dbg_static_chain_resolve.py
scripts/test-invoke-gated-forward-smoke.ps1
scripts/test_actor_yaw_current_truth_status.py
scripts/test_actor_yaw_readback_smoke.py
scripts/test_coordinate_recovery_status.py
scripts/test_current_pid_family_snapshot_sequence.py
scripts/test_live_test_orchestrator.py
scripts/test_opencode_status_packet.py
scripts/test_riftscan_coordination.py
scripts/test_turn_key_profile.py
scripts/test_x64dbg_static_chain_resolve.py
tools/riftreader_workflow/status_packet.py
```

Known untracked files at handoff time include:

```text
docs/handoffs/20260519-211920-current-proof-input-incident-recovery-handoff.md
docs/handoffs/20260519-212718-riftreader-current-proof-window-geometry-input-incident-handoff.md
docs/handoffs/20260520-072755-character-select-planner-movement-blocked-handoff.md
docs/recovery/historical/current-proof-anchor-readback-2026-05-20-pid1948-hwnd3C0D58-historical.json
docs/recovery/historical/current-proof-anchor-readback-2026-05-20-pid27552-hwnd3411E2-historical.json
scripts/__init__.py
scripts/character_select_automation_plan.py
scripts/current_pid_family_neighborhood_analysis.py
scripts/live_input_surface_audit.py
scripts/rift_emergency_key_release.py
scripts/rift_live_test/character_select_automation_plan.py
scripts/rift_live_test/emergency_key_release.py
scripts/riftreader-emergency-release.cmd
scripts/riftreader-family-neighborhood-analysis.cmd
scripts/riftreader-live-input-surface-audit.cmd
scripts/test_character_select_automation_plan.py
scripts/test_current_pid_family_neighborhood_analysis.py
scripts/test_emergency_key_release.py
scripts/test_live_input_surface_audit.py
```

Before committing, split into coherent commits if possible:

1. live input backend safety / C# ScanCode hardening,
2. current-truth/proof-pointer target-drift character-select blocker,
3. character-select dry-run planner,
4. handoff docs.

## Resume sequence

Use this exact order after resuming:

1. Read this handoff.
2. Run `git --no-pager status --short`.
3. If still at character selection, recapture/verify current target PID/HWND/client size before any click.
4. Re-run the dry-run planner:

   ```powershell
   python .\scripts\character_select_automation_plan.py --env-summary '.riftreader-local\character-select-automation-env\run-20260520-071701\character-select-automation-env-summary.json' --target-character ATANK --plan-enter-world --json
   ```

5. Do **not** click Play unless the user explicitly approves world entry.
6. If the user approves world entry:
   - bind exact PID/HWND,
   - verify character-select landmarks,
   - click Play only if geometry still matches,
   - wait for world load,
   - rediscover target state,
   - refresh current-truth/proof artifacts,
   - run same-target ProofOnly before any movement or diagnostic input.
7. Keep route/navigation movement automation paused until `movementGate.allowed=true` is explicitly restored by fresh same-target proof.

## Continuation update — 2026-05-20 07:32 EDT — planner hardening + workflow bridge

### What changed

- Recaptured the current bound RIFT client read-only through the Rift MCP:
  `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-072810-087.png`.
- Confirmed the current live target is still PID `60636`, HWND `0xC51368`, title `RIFT`, foreground/visible, client `640x360`.
- Hardened `scripts\rift_live_test\character_select_automation_plan.py` so dry-run plans now fail closed when:
  - any character-slot/play click point is missing,
  - a click point is outside the expected client bounds,
  - a click point is outside its recorded bbox,
  - multiple character slots are simultaneously marked selected.
- Added thin launcher `scripts\riftreader-character-select-plan.cmd`.
- Added status/workflow bridge command key `character-select-plan` in `tools\riftreader_workflow\status_packet.py`.
- Re-ran the dry-run resume plan for `ATANK`; it remains plan-only and wrote:
  `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-plan\run-20260520-113147-813453\character-select-automation-plan-summary.json`.

### Validation

- `python -m unittest scripts.test_character_select_automation_plan scripts.test_opencode_status_packet` -> 19 tests OK.
- `scripts\riftreader-character-select-plan.cmd --target-character ATANK --plan-enter-world --json` -> planned, no blockers, no live actions; warning remains `source-environment-says-world-entry-not-permitted-now`.
- `scripts\riftreader-workflow-status.cmd --compact-json` -> blocked as expected; `character-select-plan` bridge command exists and reports dry-run/no-click safety.
- `git --no-pager diff --check -- scripts/rift_live_test/character_select_automation_plan.py scripts/test_character_select_automation_plan.py tools/riftreader_workflow/status_packet.py scripts/test_opencode_status_packet.py scripts/riftreader-character-select-plan.cmd` -> passed; CRLF warnings only.

### Safety state

- movementSent: false.
- inputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-20 12:03 EDT — game relaunched, current target rebound

### What changed

- Operator reported the game shut down/exited and was relaunched.
- Rebound the live RIFT window read-only:
  - PID `77728`
  - HWND `0x8E13A6`
  - process start UTC `2026-05-20T15:54:23.2312272Z`
  - title `RIFT`
  - client `640x360`
- Captured a fresh visual baseline:
  `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-115825-793.png`.
- Confirmed the screen is still character selection, selected character `ATANK`, shard `Deepwood`.
- Recorded fresh character-select automation environment data:
  `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-115825\character-select-automation-env-summary.json`.
- Re-ran the dry-run planner:
  `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-plan\run-20260520-160048-254251\character-select-automation-plan-summary.json`.
- Archived the previous character-select target pointer:
  `C:\RIFT MODDING\RiftReader\docs\recovery\historical\current-proof-anchor-readback-2026-05-20-pid60636-hwndC51368-character-select-historical.json`.
- Updated:
  - `docs\recovery\current-proof-anchor-readback.json`
  - `docs\recovery\current-truth.json`
  - `docs\recovery\current-truth.md`

### Current blocked truth

| Field | Value |
|---|---|
| Current target | PID `77728` / HWND `0x8E13A6` |
| Previous character-select target | PID `60636` / HWND `0xC51368`, stale after relaunch |
| Prior in-world proof | PID `1948` / HWND `0x3C0D58`, historical only |
| Current proof status | `blocked-target-not-in-world` |
| Movement allowed | `false` |
| Play/slot click sent | `false` |

### Validation

- `python .\scripts\validate_current_truth.py --json` -> passed, artifactCount `86`.
- `python .\scripts\coordinate_recovery_status.py --json` -> blocked as expected with `current-proof-status:blocked-target-not-in-world`; live target PID `77728` detected.
- `scripts\riftreader-workflow-status.cmd --compact-json` -> blocked as expected; compact status reports PID `77728` / HWND `0x8E13A6`.
- `python -m unittest scripts.test_validate_current_truth scripts.test_current_truth_compact_summary scripts.test_coordinate_recovery_status scripts.test_character_select_automation_plan scripts.test_opencode_status_packet` -> 31 tests OK.

### Safety state

- movementSent: false.
- inputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-20 12:17 EDT — relogin resilience dry-run planner

### What changed

- Added a defensive, dry-run-only character login/relogin planning helper:
  - `scripts\character_login_resilience_plan.py`
  - `scripts\rift_live_test\character_login_resilience_plan.py`
  - `scripts\riftreader-character-login-resilience-plan.cmd`
  - `scripts\test_character_login_resilience_plan.py`
- Added workflow bridge command key `character-login-resilience-plan` in `tools\riftreader_workflow\status_packet.py`.
- The helper reads the latest character-select environment summary, current-truth JSON, and current-proof pointer; it blocks if target identity is stale or mismatched.
- It emits a crash/relogin state machine with explicit stop conditions:
  - no client / geometry mismatch,
  - not character select,
  - target character missing,
  - ambiguous selected slot,
  - Play target invalid,
  - world-load timeout,
  - post-world ProofOnly failed/stale.
- It writes a machine-readable state transition log:
  `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-resilience-plan\run-20260520-161628-200023\character-login-resilience-state-log.jsonl`.

### Latest dry-run relogin artifact

| Field | Value |
|---|---|
| Plan JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-resilience-plan\run-20260520-161628-200023\character-login-resilience-plan-summary.json` |
| Plan Markdown | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-resilience-plan\run-20260520-161628-200023\character-login-resilience-plan.md` |
| State log JSONL | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-resilience-plan\run-20260520-161628-200023\character-login-resilience-state-log.jsonl` |
| Status | `planned` |
| Can execute live actions now | `false` |
| Play action state | `approval-required` |
| Crash recovery loop | `armed-dry-run-policy` |

### Validation

- `python -m py_compile .\scripts\rift_live_test\character_login_resilience_plan.py`
- `python -m unittest scripts.test_character_login_resilience_plan` -> 3 tests OK.
- `scripts\riftreader-character-login-resilience-plan.cmd --target-character ATANK --json` -> planned, wrote JSON/Markdown/JSONL artifacts.
- `scripts\riftreader-workflow-status.cmd --compact-json` -> blocked as expected; bridge command `character-login-resilience-plan` exists.
- Full targeted suite including relogin planner -> 124 tests OK.

### Safety state

- movementSent: false.
- keyInputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-20 12:21 EDT — reusable character-select environment builder

### What changed

- Added a reusable read-only screenshot-to-environment builder:
  - `scripts\character_select_environment_capture.py`
  - `scripts\rift_live_test\character_select_environment_capture.py`
  - `scripts\riftreader-character-select-env-capture.cmd`
  - `scripts\test_character_select_environment_capture.py`
- Added workflow bridge command key `character-select-env-capture`.
- The helper converts a fresh `640x360` character-select screenshot plus explicit PID/HWND/process-start metadata into a durable environment JSON/Markdown packet.
- It blocks on wrong screenshot size, missing PID/HWND, missing screenshot, or unknown selected character layout.
- It writes annotated screenshot/crops and updates `.riftreader-local\character-select-automation-env\latest-run.txt`.

### Latest reusable environment artifact

| Field | Value |
|---|---|
| Source screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-120616-196.png` |
| Env JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-162004-986788\character-select-automation-env-summary.json` |
| Env Markdown | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-162004-986788\character-select-automation-env-summary.md` |
| Annotated screenshot | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-162004-986788\character-select-automation-targets-annotated.png` |
| Result | `captured-read-only-character-select` |
| Current target | PID `77728` / HWND `0x8E13A6` |

After generating this reusable env packet, the relogin resilience planner was re-run and now consumes the new env artifact:

`C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-resilience-plan\run-20260520-162015-078938\character-login-resilience-plan-summary.json`

### Validation

- `python -m py_compile .\scripts\rift_live_test\character_select_environment_capture.py .\scripts\character_select_environment_capture.py`
- `python -m unittest scripts.test_character_select_environment_capture scripts.test_opencode_status_packet` -> 14 tests OK.
- `scripts\riftreader-character-select-env-capture.cmd --screenshot ... --pid 77728 --hwnd 0x8E13A6 --process-start-utc 2026-05-20T15:54:23.2312272Z --module-base 0x7FF7B77A0000 --json` -> passed and wrote the env artifact above.
- `scripts\riftreader-character-login-resilience-plan.cmd --target-character ATANK --json` -> planned using the reusable env artifact.

### Safety state

- movementSent: false.
- keyInputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-20 12:26 EDT — future executor contract gate

### What changed

- Added a dry-run future-executor contract validator:
  - `scripts\character_login_executor_contract.py`
  - `scripts\rift_live_test\character_login_executor_contract.py`
  - `scripts\riftreader-character-login-executor-contract.cmd`
  - `scripts\test_character_login_executor_contract.py`
- Added workflow bridge command key `character-login-executor-contract`.
- Hardened new `.cmd` launchers to return child Python exit codes with `exit /b %ERRORLEVEL%`.
- The contract validator does **not** click. It only decides whether a future executor would be allowed to proceed after revalidating:
  - latest relogin plan is `planned`,
  - target identity matches current truth/proof,
  - target character is selected,
  - Play point/bbox match the measured client target,
  - source environment permits world entry,
  - exact approval token is provided.

### Latest executor-contract artifact

| Field | Value |
|---|---|
| Contract JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-executor-contract\run-20260520-162531-116685\character-login-executor-contract-summary.json` |
| Contract Markdown | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-executor-contract\run-20260520-162531-116685\character-login-executor-contract.md` |
| Status | `blocked` |
| Blockers | `world-entry-not-permitted-by-source-environment`; `explicit-world-entry-approval-token-missing-or-mismatched` |
| Expected approval token if explicitly approved later | `ENTER-WORLD:ATANK:77728:0x8E13A6` |
| May click Play | `false` |

### Validation

- `python -m unittest scripts.test_character_login_executor_contract scripts.test_character_login_resilience_plan scripts.test_character_select_environment_capture scripts.test_opencode_status_packet` -> 20 tests OK.
- `scripts\riftreader-character-login-executor-contract.cmd --json` -> blocked as expected, exit code `2`, no clicks/input.

### Safety state

- movementSent: false.
- keyInputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-20 12:36 EDT — consolidated login readiness packet

### What changed

- Added an input-free readiness aggregator for future character login/relogin automation:
  - `scripts\character_login_readiness_packet.py`
  - `scripts\rift_live_test\character_login_readiness_packet.py`
  - `scripts\riftreader-character-login-readiness-packet.cmd`
  - `scripts\test_character_login_readiness_packet.py`
- Added workflow bridge command key `character-login-readiness-packet`.
- Freshly rebound/captured the current character-select window with the RIFT MCP:
  - PID `77728`
  - HWND `0x8E13A6`
  - screenshot `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-122954-465.png`
- Refreshed the read-only environment, character-select plan, resilience plan, executor contract, and readiness packet from that capture.
- The readiness packet is designed as the single future-resume artifact for login automation: it consolidates target identity, selected character, Play coordinates, crash/relogin state machine, executor approval gate, stale-proof exclusions, and safety flags.

### Latest readiness artifacts

| Field | Value |
|---|---|
| Environment JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-163004-130462\character-select-automation-env-summary.json` |
| Resilience plan JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-resilience-plan\run-20260520-163014-082687\character-login-resilience-plan-summary.json` |
| Executor contract JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-executor-contract\run-20260520-163025-730666\character-login-executor-contract-summary.json` |
| Readiness packet JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-readiness-packet\run-20260520-163552-825917\character-login-readiness-packet-summary.json` |
| Readiness packet Markdown | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-readiness-packet\run-20260520-163552-825917\character-login-readiness-packet.md` |
| Status | `packet-ready` |
| Can plan login | `true` |
| Can execute live actions now | `false` |
| May click Play now | `false` |
| Expected future approval token | `ENTER-WORLD:ATANK:77728:0x8E13A6` |

### Current automation decision

| Decision | Value |
|---|---|
| Selected character | `ATANK` |
| Shard | `Deepwood` |
| Play client click point | `[517, 343]` |
| Play bbox | `[476, 329, 558, 357]` |
| Entry execution | Blocked until explicit current-run approval and revalidation |
| Movement | Blocked until post-world exact target rediscovery and same-target ProofOnly |

### Validation

- `python -m unittest scripts.test_character_login_readiness_packet scripts.test_opencode_status_packet scripts.test_character_login_resilience_plan scripts.test_character_login_executor_contract scripts.test_character_select_automation_plan scripts.test_character_select_environment_capture` -> 30 tests OK.
- Full targeted suite including readiness packet -> 132 tests OK.
- `git --no-pager diff --check` -> passed with CRLF warnings only.
- `scripts\riftreader-character-login-readiness-packet.cmd --target-character ATANK --json` -> `packet-ready`; no live actions.
- `scripts\riftreader-workflow-status.cmd --compact-json` -> blocked as expected because current target is character-select/not-in-world; new bridge command exists.

### Safety state

- movementSent: false.
- keyInputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-20 12:44 EDT — crash/relogin watch packet

### What changed

- Added an input-free crash/relogin watcher:
  - `scripts\character_login_crash_watch.py`
  - `scripts\rift_live_test\character_login_crash_watch.py`
  - `scripts\riftreader-character-login-crash-watch.cmd`
  - `scripts\test_character_login_crash_watch.py`
- Added workflow bridge command key `character-login-crash-watch`.
- The watcher samples visible RIFT windows and compares them to the current expected target epoch from current-truth/current-proof/readiness artifacts.
- It records:
  - exact PID/HWND match vs drift,
  - current client/window geometry,
  - offline/no-window state,
  - multiple-client ambiguity,
  - resume state for future login automation,
  - stale-epoch reuse policy.
- It never launches the game, focuses/clicks, sends keys, enters world, moves, reads live game memory, attaches a debugger, writes providers, or mutates Git.

### Latest crash/relogin watch artifact

| Field | Value |
|---|---|
| Watch JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-crash-watch\run-20260520-164322-952413\character-login-crash-watch-summary.json` |
| Watch Markdown | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-crash-watch\run-20260520-164322-952413\character-login-crash-watch.md` |
| Observation JSONL | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-crash-watch\run-20260520-164322-952413\character-login-crash-watch-observations.jsonl` |
| Status | `watch-ready` |
| Watch status | `target-present-same-epoch` |
| Samples | `3` |
| Observed window | PID `77728`, HWND `0x8E13A6`, client `640x360` |
| Resume decision | `refresh-character-select-readiness` |

### Watcher state log

| State | Status |
|---|---|
| `detect-client` | `passed` |
| `target-epoch-check` | `same-epoch` |
| `refresh-character-select-readiness` | `recommended` |
| `future-click-play` | `approval-required` |
| `post-world-proof` | `pending-after-world-load` |

### Validation

- `python -m unittest scripts.test_character_login_crash_watch scripts.test_opencode_status_packet` -> 16 tests OK.
- Full targeted suite including crash watch -> 136 tests OK.
- `git --no-pager diff --check` -> passed with CRLF warnings only.
- `scripts\riftreader-character-login-crash-watch.cmd --samples 3 --interval-seconds 1 --json` -> `watch-ready`, same PID/HWND epoch, no live actions.
- `scripts\riftreader-workflow-status.cmd --compact-json` -> blocked as expected; bridge command `character-login-crash-watch` exists.

### Safety state

- movementSent: false.
- keyInputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- clientLaunchAttempted: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-20 12:52 EDT — no-input character-login supervisor

### What changed

- Added a no-input login supervisor that orchestrates the current safe checks into one resumable packet:
  - `scripts\character_login_supervisor.py`
  - `scripts\rift_live_test\character_login_supervisor.py`
  - `scripts\riftreader-character-login-supervisor.cmd`
  - `scripts\test_character_login_supervisor.py`
- Added workflow bridge command key `character-login-supervisor`.
- The supervisor runs child checks with command envelopes:
  - crash/relogin watch,
  - readiness packet,
  - executor contract,
  - compact workflow status.
- It writes a single final decision packet plus durable child command envelopes.
- It never launches the game, focuses/clicks, sends keys, enters world, moves, reads live game memory, attaches a debugger, writes providers, or mutates Git.

### Latest supervisor artifact

| Field | Value |
|---|---|
| Supervisor JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-165126-279643\character-login-supervisor-summary.json` |
| Supervisor Markdown | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-165126-279643\character-login-supervisor.md` |
| Command envelopes | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-165126-279643\character-login-supervisor-command-envelopes.json` |
| Status | `blocked-approval-required` |
| Crash watch | `watch-ready` / `target-present-same-epoch` |
| Readiness packet | `packet-ready` |
| Executor contract | `blocked` |
| Workflow status | `blocked` |
| Can plan login | `true` |
| Can execute live actions now | `false` |
| Future executor may click Play | `false` |
| Expected future approval token | `ENTER-WORLD:ATANK:77728:0x8E13A6` |

### Supervisor decision

| Field | Value |
|---|---|
| Same target epoch observed | `true` |
| Selected character | `ATANK` |
| Play client click point | `[517, 343]` |
| Resume state | `refresh-character-select-readiness` |
| Current blocker | explicit approval/world-entry gate |
| Post-world requirement | rediscover PID/HWND, fresh API/runtime coordinate truth, same-target ProofOnly |

### Validation

- `python -m unittest scripts.test_character_login_supervisor scripts.test_opencode_status_packet` -> 16 tests OK.
- Full targeted suite including supervisor -> 140 tests OK.
- `git --no-pager diff --check` -> passed with CRLF warnings only.
- `scripts\riftreader-character-login-supervisor.cmd --target-character ATANK --samples 3 --interval-seconds 1 --json` -> `blocked-approval-required`, expected exit code `2`, no live actions.
- `scripts\riftreader-workflow-status.cmd --compact-json` -> blocked as expected; bridge command `character-login-supervisor` exists.

### Safety state

- movementSent: false.
- keyInputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- clientLaunchAttempted: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Ready-to-paste resume prompt

```text
Resume RiftReader from C:\RIFT MODDING\RiftReader\docs\handoffs\20260520-072755-character-select-planner-movement-blocked-handoff.md.
Start by reading the handoff and checking git status. Treat RIFT as character-select/not-in-world unless freshly verified otherwise. Do not click Play or send movement/input unless I explicitly approve. Movement automation remains paused; legacy WindowMessage movement is retired; C# ScanCode is only for bounded diagnostics after fresh target/freshness gates. Continue with the smallest safe next slice.
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Review the new character-select planner files | Confirm the dry-run contract is acceptable before any live click mode exists. |
| 2 | Re-run planner tests after any merge/conflict cleanup | Keeps the character-select safety contract locked. |
| 3 | Add a read-only recapture helper for character-select landmarks | Avoids relying on stale screenshots before future clicks. |
| 4 | Add executable mode only for character selection, not Play | Allows safer validation of roster-click behavior without entering world. |
| 5 | Require post-click visual recapture before Play can be considered | Prevents wrong-character entry. |
| 6 | Keep Play click behind explicit per-run approval | Preserves the user’s “do not enter world yet” boundary. |
| 7 | After world entry, immediately refresh PID/HWND/current-truth | Character-select target truth is not in-world coordinate truth. |
| 8 | Run ProofOnly before any movement/key diagnostics | Prevents stale proof from driving movement. |
| 9 | Split current dirty tree into coherent commits | Makes review and rollback practical. |
| 10 | Preserve old PID proof archives as historical-only | Avoids accidentally treating old absolute addresses as current truth. |

## Continuation update — 2026-05-20 13:11 EDT — PID80072 refreshed supervisor + future MCP manifest

### Current live target

| Field | Value |
|---|---|
| Current target | PID `80072`, HWND `0xD10C20` |
| Process start UTC | `2026-05-20T16:54:54.7174411Z` |
| Module base | `0x7FF7B77A0000` |
| Screen state | character selection; selected character `ATANK`; shard `Deepwood` |
| Client size | `640x360` |
| Latest screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-130819-184.png` |
| Movement gate | `blocked-target-not-in-world` |

### Fresh no-input artifacts

| Artifact | Path |
|---|---|
| Environment summary | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-env\run-20260520-170836-858950\character-select-automation-env-summary.json` |
| Selection plan | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-select-automation-plan\run-20260520-170837-458546\character-select-automation-plan-summary.json` |
| Resilience plan | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-resilience-plan\run-20260520-170837-770673\character-login-resilience-plan-summary.json` |
| Executor contract | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-170838-721852\executor-contract\character-login-executor-contract-summary.json` |
| Readiness packet | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-170838-721852\readiness-packet\character-login-readiness-packet-summary.json` |
| Supervisor summary | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-170838-721852\character-login-supervisor-summary.json` |
| Future MCP action manifest | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-170838-721852\future-mcp-action-manifest.json` |
| Current truth JSON | `docs\recovery\current-truth.json` updated `2026-05-20T17:11:10.254804Z` |
| Current proof blocker | `docs\recovery\current-proof-anchor-readback.json` updated `2026-05-20T17:11:10.254804Z` |

### Hardening added in this continuation

- Future MCP manifest now includes `mcp__rift_game__.wait_for_frame_change` after the one approved Play click and before post-transition capture.
- Future manifest is written as a standalone artifact: `future-mcp-action-manifest.json`.
- Character-select plan, login resilience plan, and executor contract now write `latest-run.txt` pointers for easier resume after crash/relaunch.
- Target identity matching now rejects process-epoch drift when `processStartUtc` / `moduleBase` are available, while tolerating harmless timestamp precision differences.
- `docs\recovery\current-truth.md`, `current-truth.json`, and `current-proof-anchor-readback.json` were refreshed to PID `80072` and the latest screenshot/artifact set.

### Latest supervisor decision

| Field | Value |
|---|---|
| Status | `blocked-approval-required` |
| Crash watch | `watch-ready` / `target-present-same-epoch` |
| Readiness packet | `packet-ready` |
| Executor contract | `blocked` |
| Workflow status | `blocked` |
| Future executor may click Play | `false` |
| Expected approval token | `ENTER-WORLD:ATANK:80072:0xD10C20` |
| Future MCP sequence | `find_game_window` -> `capture_game_window` -> `focus_game_window` -> `click_client` -> `wait_for_frame_change` -> `capture_game_window` -> post-world ProofOnly |

### Validation

- `python -m unittest scripts.test_character_select_automation_plan scripts.test_character_login_resilience_plan scripts.test_character_login_executor_contract scripts.test_character_login_readiness_packet scripts.test_character_login_crash_watch scripts.test_character_login_supervisor scripts.test_opencode_status_packet` -> 37 tests OK.
- `scripts\character_login_supervisor.py --target-character ATANK --samples 3 --interval-seconds 1 --json` -> expected exit `2`, status `blocked-approval-required`, no live actions.
- Read-only MCP target check/capture confirmed the same PID/HWND and `640x360` character-selection screen.

### Safety state

- No focus, click, key input, movement, CE, x64dbg attach, provider write, or Git mutation was performed.
- Character selection remains a blocker, not coordinate/movement truth.
- Old approval tokens are invalid after crash/relaunch or PID/HWND drift.
- Movement stays blocked until world load + fresh exact target + API/runtime coordinate + same-target ProofOnly.

### Updated resume note

Resume from this section first. The current same-epoch world-entry token is `ENTER-WORLD:ATANK:80072:0xD10C20`, but it is valid only for a future run that immediately revalidates PID/HWND/screenshot and receives explicit approval in that same run. Without that approval, continue only with read-only observation, artifact refresh, and defensive helper hardening.

## Continuation update — 2026-05-20 13:21 EDT — no-input screen-state classifier

### What changed

- Added a no-input screenshot classifier for character-login state:
  - `scripts\character_login_screen_state.py`
  - `scripts\rift_live_test\character_login_screen_state.py`
  - `scripts\riftreader-character-login-screen-state.cmd`
  - `scripts\test_character_login_screen_state.py`
- Wired the classifier into the character-login supervisor as a required child check before any future executor can be considered.
- Added workflow bridge command key `character-login-screen-state`.
- The classifier scores multiple visual landmarks instead of trusting one fixed click point only:
  - lower-right Play button region,
  - left roster panel,
  - shard label,
  - center character/model region,
  - expected client geometry.
- It never clicks, focuses, sends keys, enters world, reads memory, attaches a debugger, writes providers, or mutates Git.

### Latest classifier/supervisor evidence

| Field | Value |
|---|---|
| Screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-131947-896.png` |
| Screen-state summary | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-172009-127267\screen-state\character-login-screen-state-summary.json` |
| Screen classification | `character-selection-not-in-world` |
| Confidence | `0.9736` |
| Supervisor summary | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-172009-127267\character-login-supervisor-summary.json` |
| Supervisor status | `blocked-approval-required` |
| Expected approval token | `ENTER-WORLD:ATANK:80072:0xD10C20` |
| Current truth refresh | `docs\recovery\current-truth.json`, `docs\recovery\current-truth.md`, `docs\recovery\current-proof-anchor-readback.json` updated `2026-05-20T17:21:26.354850Z` |

### Why this matters for resilient login/relogin

- Crash/relaunch now requires both target epoch checks and a fresh screenshot classifier pass before any future login executor is eligible.
- The future executor can fail closed if the Play/roster landmarks are missing, stale, wrong-size, or ambiguous.
- Post-Play automation can use the same classifier to detect that character-select landmarks disappeared, but it still cannot claim in-world truth until fresh telemetry and same-target ProofOnly pass.

### Validation

- `python -m unittest scripts.test_character_login_screen_state scripts.test_character_login_supervisor scripts.test_opencode_status_packet` -> 19 tests OK.
- `scripts\character_login_screen_state.py --screenshot <latest> --expect-character-select --json` -> `classified-character-select`.
- `scripts\character_login_supervisor.py --target-character ATANK --samples 3 --interval-seconds 1 --json` -> expected exit `2`, status `blocked-approval-required`, screen child `classified-character-select`.

### Safety state

- movementSent: false.
- keyInputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- clientLaunchAttempted: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-20 13:29 EDT — Play executor gate validator

### What changed

- Added a future Play-click executor gate that consumes the supervisor's `future-mcp-action-manifest.json` without sending input:
  - `scripts\character_login_play_executor_gate.py`
  - `scripts\rift_live_test\character_login_play_executor_gate.py`
  - `scripts\riftreader-character-login-play-executor-gate.cmd`
  - `scripts\test_character_login_play_executor_gate.py`
- Added workflow bridge command key `character-login-play-executor-gate`.
- The gate validates:
  - current supervisor packet freshness,
  - screen-state classifier freshness/classification,
  - manifest step order and exact MCP tools,
  - `click_client` Play coordinate `[517,343]`,
  - `maxClicks == 1`, client coordinate space,
  - current-truth/current-proof target match,
  - explicit approval token match,
  - explicit `--allow-world-entry` flag.
- It writes an `mcpActionEnvelope` but never performs the MCP actions itself.

### Latest gate evidence

| Field | Value |
|---|---|
| Screenshot | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\.runtime\screenshots\capture-20260520-132806-184.png` |
| Supervisor | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-supervisor\run-20260520-172826-508165\character-login-supervisor-summary.json` |
| Play executor gate | `C:\RIFT MODDING\RiftReader\.riftreader-local\character-login-play-executor-gate\run-20260520-172832-522225\character-login-play-executor-gate-summary.json` |
| Gate status | `blocked-approval-required` |
| Data blockers | none |
| Execution blockers | `explicit-world-entry-approval-token-missing-or-mismatched`, `allow-world-entry-flag-missing` |
| Screen classification | `character-selection-not-in-world` |
| Screen confidence | `0.9178` |
| Expected approval token | `ENTER-WORLD:ATANK:80072:0xD10C20` |
| Current truth refresh | `docs\recovery\current-truth.json`, `docs\recovery\current-truth.md`, `docs\recovery\current-proof-anchor-readback.json` updated `2026-05-20T17:29:39.217389Z` |

### Validated future MCP sequence

| Step | Tool |
|---|---|
| `bind-exact-target` | `mcp__rift_game__.find_game_window` |
| `capture-before-focus` | `mcp__rift_game__.capture_game_window` |
| `focus-for-click` | `mcp__rift_game__.focus_game_window` |
| `click-play-once` | `mcp__rift_game__.click_client` |
| `wait-for-world-transition` | `mcp__rift_game__.wait_for_frame_change` |
| `capture-after-transition` | `mcp__rift_game__.capture_game_window` |
| `post-world-proof` | repo ProofOnly workflow |

### Validation

- `python -m unittest scripts.test_character_login_play_executor_gate` -> 4 tests OK.
- `python -m unittest scripts.test_character_login_play_executor_gate scripts.test_opencode_status_packet` -> 16 tests OK.
- `scripts\character_login_play_executor_gate.py --json` after fresh supervisor run -> expected exit `2`, status `blocked-approval-required`, no data blockers.

### Safety state

- movementSent: false.
- keyInputSent: false.
- mouseClickSent: false.
- worldEntryClicked: false.
- clientLaunchAttempted: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

## Continuation update — 2026-05-20 13:36 EDT — Glyph launcher read-only inspection

### Scope

User requested launcher examination only. No launcher/game focus, click, key input, launch attempt, or button press was performed.

### Observed launcher state

| Field | Value |
|---|---|
| Launcher process | `GlyphClientApp.exe` PID `31812` |
| Launcher path | `C:\Program Files (x86)\Glyph\GlyphClientApp.exe` |
| Launcher command | `GlyphClientApp.exe -hidden` |
| Main HWND | `0x27017C`, title `Glyph`, class `Qt5QWindowIcon` |
| Window state | minimized/offscreen at `-32000,-32000`, client `0x0` |
| Hidden form | HWND `0x10A86`, title `Form`, client `400x425`, not visible |
| Tray message window | HWND `0x10A8E`, class `QTrayIconMessageWindowClass`, not visible |
| UI Automation | root Qt pane only while hidden/minimized; no button tree captured |
| RIFT child process | `rift_x64.exe` PID `80072`, parent PID `31812` |
| Glyph library version | `stable-249-1-a-335557` |
| RIFT live manifest version | `STABLE-1-1149-a-1256380` |

### Artifacts

| Artifact | Path |
|---|---|
| Tracked launcher notes | `docs\handoffs\20260520-1336-glyph-launcher-readonly-automation-notes.md` |
| Redacted summary JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-launcher-inspection-summary.json` |
| Raw window enum JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-launcher-window-enum.json` |
| UI Automation JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-launcher-uia.json` |
| Process tree JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-133435-271272\glyph-process-tree.json` |

### Automation implications

- Detect launcher presence by process `GlyphClientApp.exe`, not visible client geometry.
- Associate RIFT to launcher via process tree; current `rift_x64.exe` parent is Glyph PID `31812`.
- Do not persist or reuse RIFT command-line auth/session arguments; tracked notes intentionally redact them.
- Hidden/minimized Glyph is not a safe button-click target; future launcher button automation needs explicit approval, restore/show, fresh screenshot classification, exact HWND/PID binding, and max-one action per approval.
- `Notification.log` is historical context only and did not provide reliable current launch proof for the 2026-05-20 session.

## Continuation update — 2026-05-20 13:49 EDT — tracked launcher inspection helper

### What changed

- Added a tracked, read-only launcher inspection workflow:
  - `scripts\launcher_inspection.py`
  - `scripts\rift_live_test\launcher_inspection.py`
  - `scripts\riftreader-launcher-inspection.cmd`
  - `scripts\test_launcher_inspection.py`
- Added workflow status bridge command key `launcher-inspection`.
- Added latest launcher-state summary into `scripts\riftreader-workflow-status.cmd --compact-json` under `launcher`.
- The helper writes redacted JSON/Markdown artifacts under `.riftreader-local\launcher-inspection\run-*` and updates `.riftreader-local\launcher-inspection\latest-run.txt`.

### Latest tracked-helper evidence

| Field | Value |
|---|---|
| Helper run | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-174905-389594` |
| Summary JSON | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-174905-389594\launcher-inspection-summary.json` |
| Summary Markdown | `C:\RIFT MODDING\RiftReader\.riftreader-local\launcher-inspection\run-20260520-174905-389594\LAUNCHER_INSPECTION.md` |
| Status | `passed` |
| Launcher state | `launcher-and-game-present` |
| Relogin state | `observe-current-game-child` |
| Launcher PID | `31812` |
| RIFT PID | `80072` |
| RIFT child of Glyph | `true` |
| Launcher window state | `minimized-or-offscreen` |
| Button automation policy | `blocked-hidden-or-minimized` |
| Raw command lines stored | `false` |
| Notification log tail stored | `false` |

### Validation

- `python -m py_compile scripts\rift_live_test\launcher_inspection.py scripts\launcher_inspection.py tools\riftreader_workflow\status_packet.py` -> passed.
- `python -m unittest scripts.test_launcher_inspection scripts.test_opencode_status_packet` -> 18 tests OK.
- `scripts\riftreader-launcher-inspection.cmd --json` -> passed; no launcher/game input sent.
- `scripts\riftreader-workflow-status.cmd --compact-json --skip-coordinate-status` -> expected blocked status because movement/world-entry remains blocked; compact SITREP now includes the latest `launcher` section.

### Safety state

- launcherButtonPressed: false.
- launchAttempted: false.
- mouseClickSent: false.
- keyPressSent: false.
- movementSent: false.
- rawCommandLinesStored: false.
- noCheatEngine: true.
- x64dbgAttach: false.
- providerWrites: false.
- gitMutation: false.

### Latest workflow-status artifact

- Compact SITREP with launcher section: `C:\RIFT MODDING\RiftReader\.riftreader-local\workflow-status\20260520-175126Z\compact-sitrep.json`.
- Expected status remains `blocked` because RIFT is at character selection and movement/world-entry remains approval-gated.
