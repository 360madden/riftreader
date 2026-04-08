---
name: rift-window-control
description: Use when interacting with the live Rift game window through the local rift_game MCP server. This skill is for safe bind/focus/capture/act workflows, semantic actions like inventory and hotbar presses, and visual verification with wait_for_frame_change.
---

# Rift window control

Use this skill when the task involves the live Rift client, not static code only.

## Required loop

1. `find_game_window` first.
2. Before any input, call `focus_game_window`.
3. Call `capture_game_window` to establish a visual baseline.
4. Prefer semantic tools before raw inputs:
   - `open_inventory`
   - `press_hotbar_slot`
   - `send_key` only when no semantic tool fits
   - `click_client` only when a screenshot shows the exact target
5. After input, call `wait_for_frame_change`.
6. Then call `capture_game_window` again if you need to inspect the final state.

## Safety rules

- Do not send input until a window is bound and focused.
- Treat semantic bindings as untrusted until confirmed. If `tools/rift-game-mcp/config/bindings.json` is incomplete or likely wrong, pass `keyChord` explicitly.
- Use client-area coordinates only.
- Prefer a narrow `wait_for_frame_change` region when the expected change is localized.
- If `wait_for_frame_change` returns `changed: false`, stop and inspect before sending more input.
- If the window title/process looks wrong, re-run `find_game_window` instead of forcing input.

## Practical guidance

- Use `capture_game_window` before `click_client` so coordinates are based on the latest screenshot.
- Use `open_inventory` for inventory toggling rather than guessing the key.
- Use `press_hotbar_slot` for hotbar actions rather than raw number keys when possible.
- If a step depends on a visible confirmation, do not chain more actions until the confirmation is observed.
