# Rift Game MCP

Local MCP server for Codex to interact with a **bound Rift game window** on Windows.

## What it exposes

- `find_game_window`
- `get_bound_window_state`
- `inspect_bound_window`
- `get_riftreader_current_truth`
- `get_game_control_readiness`
- `get_movement_execution_preflight`
- `classify_game_action`
- `plan_movement_step`
- `execute_movement_step`
- `get_latest_control_artifact`
- `focus_game_window`
- `capture_game_window`
- `resize_game_window`
- `capture_inventory_reference`
- `wait_for_frame_change`
- `suggest_inventory_region`
- `validate_config`
- `click_client`
- `send_key`
- `release_all_movement_keys`
- `toggle_inventory`
- `ensure_inventory_open`
- `ensure_inventory_closed`
- `open_inventory`
- `open_bags`
- `press_hotbar_slot`

## Safety model

- `find_game_window` binds the active target window for the session.
  When multiple Rift clients are running, pass `processId` or `windowHandle`
  instead of relying on the first `processName` match.
- `get_bound_window_state` reports the current MCP session binding without
  touching the game window.
- `inspect_bound_window` re-checks the bound HWND/process identity and returns
  current window/client rectangles without sending input.
- `get_riftreader_current_truth` reads `docs/recovery/current-truth.json` so an
  operator can see the current movement gate and proof/readback blockers before
  acting.
- `get_game_control_readiness` is a read-only preflight packet for live-control
  automation. It aggregates bound-window state, exact-window inspection when a
  window is bound, current-truth movement gates/blockers, config readiness, and
  the next safe action. It does not focus, resize, click, send keys, attach
  debuggers, write providers, or use SavedVariables as live truth.
- `get_movement_execution_preflight` is the read-only Phase 9 gate for one
  future bounded movement step. It classifies the requested movement action,
  inspects the bound window if available, blocks on stale/mismatched
  current-truth target identity, minimized or zero-client windows, missing
  foreground state, overlong holds, and missing live verification requirements.
  It does not capture, focus, release keys, or send input.
- `classify_game_action` is read-only and classifies semantic actions or raw
  key chords. Movement-risk keys/actions (`W/A/S/D/Q/E`, arrows, Space, and
  semantic movement aliases) are movement input, blocked by default, and require
  separate approval before execution.
- `plan_movement_step` creates only ignored local movement-plan artifacts under
  `.riftreader-local\rift-game-mcp\movement-plans\`. It never sends input and
  never creates a reusable approval token; its approval packet is for one
  bounded movement step only.
- `execute_movement_step` is the gated Phase 10 wrapper for one bounded
  movement step. It defaults to `dryRun: true`, internally calls
  `get_movement_execution_preflight`, and live execution requires the exact
  one-shot approval phrase returned for the same target/action/hold/current
  truth. Validation must keep `dryRun: true`; the live path is annotated
  non-read-only/destructive because it can focus/capture/send/release/wait when
  all gates pass.
- `get_latest_control_artifact` reads the latest readiness/plan/run/session/current-window-smoke
  artifact summaries under `.riftreader-local\rift-game-mcp\` without accepting
  arbitrary paths.
- Every other tool uses that bound window.
- Input tools reject execution if:
  - no window is bound,
  - the current foreground window is not the bound window,
  - the bound handle no longer matches the same process identity.
- `send_key` supports `dryRun: true` to classify a key without sending it.
  Movement-risk keys (`W/A/S/D/Q/E`, arrows, and Space) are blocked by default
  unless `allowMovementKeys: true` is explicitly passed after the movement gate
  is satisfied.
- `release_all_movement_keys` is a safety primitive, not a movement executor.
  It is `dryRun: true` by default and its live path sends only key-up messages
  for the fixed movement-risk key set (`W/A/S/D/Q/E`, arrows, Space) to the
  exact bound foreground window. It does not send key-down movement input and
  still requires fresh live-surface verification after use.
- `resize_game_window` defaults to `dryRun: true`. Pass `dryRun: false` only
  when you intentionally want to resize the exact bound HWND. It changes the
  window/client size only; it does not send game input. Native inspect/resize
  is implemented by the `.NET 10` helper at `tools/RiftReader.WindowTools`;
  mouse clicks now use that same `.NET 10` helper so the backend is explicit
  and testable. PowerShell remains a legacy leaf helper for older operations.
- Clicks are **client-area relative**, not desktop-relative.
- `click_client` reports mouse input delivery, not game-UI activation. Treat
  `inputSent=true` / legacy `clicked=true` as "Win32 input was sent"; require
  screenshot/classifier proof before claiming a button activated. The result
  includes `backend: "dotnet-win32-sendinput-mouse"`, `mouseInputMethod`,
  `activationVerified=false`, before/after window snapshots, and timing fields
  so failed UI activations can be diagnosed without implying success.
- `click_client` supports bounded timing knobs:
  `cursorSettleMilliseconds` and `clickDelayMilliseconds`, plus `dryRun` for
  exact-target/geometry preflight without sending mouse input. Do not use these
  knobs to retry blindly; each live click still needs an explicit approval gate.
- `wait_for_frame_change` can watch the full client area or a narrowed region.
- Semantic tools read `config/bindings.json` unless you override `keyChord` in the tool call.
- `validate_config` checks key bindings, inventory reference paths, and whether state-verifying inventory tools are ready.
- `capture_inventory_reference` saves a visually confirmed bags-open or bags-closed screenshot and can update `bindings.json`.
- `suggest_inventory_region` can derive the bags-panel region from open/closed reference screenshots and optionally save it back into `config/bindings.json`.
- `toggle_inventory` verifies that something changed after sending the bags key.
- `ensure_inventory_open` / `ensure_inventory_closed` only act when inventory state can be verified safely from reference screenshots.

## Fast state/resize tools

Read-only visibility:

```json
{ "tool": "get_bound_window_state" }
{ "tool": "inspect_bound_window" }
{ "tool": "get_riftreader_current_truth" }
```

Safe resize plan, then intentional resize:

```json
{ "tool": "resize_game_window", "arguments": { "clientWidth": 640, "clientHeight": 360, "dryRun": true } }
{ "tool": "resize_game_window", "arguments": { "clientWidth": 640, "clientHeight": 360, "dryRun": false } }
```

Safe key classification:

```json
{ "tool": "send_key", "arguments": { "keyChord": "w", "dryRun": true } }
```

Safe movement-control planning:

```json
{ "tool": "get_game_control_readiness" }
{ "tool": "classify_game_action", "arguments": { "actionName": "move_forward", "holdMilliseconds": 500 } }
{ "tool": "plan_movement_step", "arguments": { "semanticAction": "move_forward", "holdMilliseconds": 500 } }
{ "tool": "get_movement_execution_preflight", "arguments": { "semanticAction": "move_forward", "holdMilliseconds": 500 } }
{ "tool": "execute_movement_step", "arguments": { "semanticAction": "move_forward", "holdMilliseconds": 500, "dryRun": true } }
{ "tool": "release_all_movement_keys", "arguments": { "dryRun": true } }
{ "tool": "get_latest_control_artifact", "arguments": { "kind": "movement-plan" } }
{ "tool": "get_latest_control_artifact", "arguments": { "kind": "current-window-smoke" } }
```

These planning tools are not live execution tools. They do not focus the game
window, send keys, click, resize, attach x64dbg/CE, promote proof/truth, write
providers, or expose public-route live movement control.

Reusable exact-target dry-run smoke:

```powershell
cd "C:\RIFT MODDING\RiftReader\tools\rift-game-mcp"
npm run smoke:current-window -- --process-id 130540 --window-handle 0x9310EA --json
```

Reusable read-only discovery + dry-run smoke:

```powershell
cd "C:\RIFT MODDING\RiftReader\tools\rift-game-mcp"
npm run smoke:current-window:auto
```

No-input smoke helper self-test:

```powershell
cd "C:\RIFT MODDING\RiftReader\tools\rift-game-mcp"
npm run test:smoke
```

This smoke binds/inspects the exact target, checks readiness, classifies the
configured semantic movement action, calls `release_all_movement_keys` with
`dryRun: true`, calls `plan_movement_step` with `dryRun: true`, calls
`get_movement_execution_preflight` read-only to report Phase 10 blockers, and
calls `execute_movement_step` with `dryRun: true` to verify the wrapper does not
send input during smoke validation. It writes only ignored summaries under
`.riftreader-local\rift-game-mcp\current-window-smoke\` and fails if any tool
reports live input, movement, or key release. The auto
variant first runs the existing read-only
`scripts\get-rift-window-targets.cmd -Json` target discovery helper and selects
the `movement` lane target. It fails closed if more than one RIFT window is
discovered; pass exact `--process-id` / `--window-handle`, or add
`--allow-multiple-targets` only when selecting the sorted `movement` lane is
intentional. The self-test uses only synthetic discovery packets and does not
start the MCP server, discover live windows, bind a target, send input, or write
artifacts.

## Bindings config

Edit:

`C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\config\bindings.json`

- `inventory` is currently set to `"b"` for bags.
- `inventoryVerification` is optional for plain toggles, but required for `ensure_inventory_open` and `ensure_inventory_closed`.
- `inventoryVerification.openReferencePath` and `inventoryVerification.closedReferencePath` can be absolute paths or paths relative to `config/`.
- `inventoryVerification.region` is optional but strongly recommended; set it to the bags panel area so state matching ignores unrelated screen motion.
- `hotbarSlots` ships with editable placeholder defaults for slots 1-12.

## Inventory verification setup

To use `ensure_inventory_open` / `ensure_inventory_closed`:

1. Bind and focus the Rift window.
2. Make sure bags are closed, then run `capture_inventory_reference` with `referenceState: "closed"`.
3. Open bags, then run `capture_inventory_reference` with `referenceState: "open"`.
4. Run `suggest_inventory_region` with `saveToBindings: true` to derive the exact bags panel area, or set `inventoryVerification.region` manually.
5. Run `validate_config` and confirm `canUseInventoryEnsure` is `true`.

The reference screenshots must come from the same client size as the live game window. If the window size changes, capture new references.

## Codex wiring

This repo includes a project-scoped MCP config at:

`C:\RIFT MODDING\RiftReader\.codex\config.toml`

If Codex does not pick up the relative path in that config on your machine, add it explicitly:

```powershell
codex mcp add rift_game -- node "C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\index.mjs"
```

## Local validation

```powershell
cd "C:\RIFT MODDING\RiftReader\tools\rift-game-mcp"
npm run validate
npm run test:control
npm run test:smoke
node safe-current-window-smoke.mjs --help
```

That launches the MCP server over stdio, verifies the tool list and control
output/safety schemas, and runs the no-input current-window smoke self-test.
The control test exercises action classification and ignored movement-plan
artifact writing without touching the live game window. It also verifies the
read-only movement execution preflight and dry-run Phase 10 wrapper block safely
when no exact window is bound and when a non-movement semantic action is
supplied. Its classification
matrix covers the fixed movement-risk key set, modifier chords containing
movement keys, a non-movement chord, unknown-action fail-closed behavior, and
inventory semantic UI actions.
The smoke self-test covers target-discovery lane selection and multi-target
fail-closed behavior without touching the live game window.
The current-window smoke is an operator-run exact-target dry-run check; do not
add it to CI unless the target discovery step is also made deterministic.

## Repo-local Codex skill

This repo now includes a local skill at:

`C:\RIFT MODDING\RiftReader\.codex\skills\rift-window-control\SKILL.md`

It tells Codex to follow the safer loop:

bind → focus → capture → act → wait_for_frame_change
