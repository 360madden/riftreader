# Rift Game MCP

Local MCP server for Codex to interact with a **bound Rift game window** on Windows.

## What it exposes

- `find_game_window`
- `focus_game_window`
- `capture_game_window`
- `wait_for_frame_change`
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
- Every other tool uses that bound window.
- Input tools reject execution if:
  - no window is bound,
  - the current foreground window is not the bound window,
  - the bound handle no longer matches the same process identity.
- Clicks are **client-area relative**, not desktop-relative.
- `wait_for_frame_change` can watch the full client area or a narrowed region.
- Semantic tools read `config/bindings.json` unless you override `keyChord` in the tool call.
- `toggle_inventory` verifies that something changed after sending the bags key.
- `ensure_inventory_open` / `ensure_inventory_closed` only act when inventory state can be verified safely from reference screenshots.

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
2. Capture one screenshot with bags closed.
3. Capture one screenshot with bags open.
4. Save those PNGs somewhere stable.
5. Set `inventoryVerification.openReferencePath` and `inventoryVerification.closedReferencePath`.
6. Optionally set `inventoryVerification.region` to the exact bags panel area for more reliable matching.

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
