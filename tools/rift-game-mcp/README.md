# Rift Game MCP

Local MCP server for Codex to interact with a **bound Rift game window** on Windows.

## What it exposes

- `find_game_window`
- `focus_game_window`
- `capture_game_window`
- `wait_for_frame_change`
- `click_client`
- `send_key`
- `open_inventory`
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

## Bindings config

Edit:

`C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\config\bindings.json`

- `inventory` is intentionally unset until you confirm the right key.
- `hotbarSlots` ships with editable placeholder defaults for slots 1-12.

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
