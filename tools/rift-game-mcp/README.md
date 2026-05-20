# Rift Game MCP

Local MCP server for Codex to interact with a **bound Rift game window** on Windows.

## What it exposes

- `find_game_window`
- `get_bound_window_state`
- `inspect_bound_window`
- `get_riftreader_current_truth`
- `focus_game_window`
- `capture_game_window`
- `resize_game_window`
- `capture_inventory_reference`
- `wait_for_frame_change`
- `suggest_inventory_region`
- `validate_config`
- `click_client`
- `send_key`
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
- Every other tool uses that bound window.
- Input tools reject execution if:
  - no window is bound,
  - the current foreground window is not the bound window,
  - the bound handle no longer matches the same process identity.
- `send_key` supports `dryRun: true` to classify a key without sending it.
  Movement-risk keys (`W/A/S/D/Q/E`, arrows, and Space) are blocked by default
  unless `allowMovementKeys: true` is explicitly passed after the movement gate
  is satisfied.
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
```

That launches the MCP server over stdio and verifies the tool list.

## Repo-local Codex skill

This repo now includes a local skill at:

`C:\RIFT MODDING\RiftReader\.codex\skills\rift-window-control\SKILL.md`

It tells Codex to follow the safer loop:

bind → focus → capture → act → wait_for_frame_change
