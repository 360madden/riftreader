# Rift Game MCP handoff — 2026-04-24

## Verdict

| Area | Status | Notes |
|---|---:|---|
| Rift MCP server validation | ✅ Passing | `npm run validate` succeeds. |
| Keyboard input to Rift | ✅ Fixed | Current helper uses targeted window-message key events; `send_key b` was verified opening/closing bags earlier. |
| Basic window control | ✅ Working | `find_game_window`, `focus_game_window`, `capture_game_window`, `click_client`, and `wait_for_frame_change` are available. |
| Inventory toggle | ✅ Ready | `inventory` binding is configured as `b`; `toggle_inventory` can use the fixed keyboard path. |
| Inventory state ensure | ⚠️ Not calibrated | `ensure_inventory_open` / `ensure_inventory_closed` still require clean open/closed reference screenshots and a region. |
| New MCP functionality | ✅ Implemented, reload needed | Fresh validation sees new tools; the active Codex MCP session may need reload/restart before they appear as callable tools. |

## Context

| Item | Value |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch observed | `navigation` |
| MCP package | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp` |
| Config file | `C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\config\bindings.json` |
| Reference artifact dir | `C:\RIFT MODDING\RiftReader\artifacts\rift-game-mcp\references` |

## Root cause already identified

Manual `b` opened Rift bags, but MCP `send_key b` originally reported success without affecting Rift.

| Cause | Resolution |
|---|---|
| PowerShell collapsed one-key chords like `b` into a scalar, causing `.Count` errors. | `Resolve-KeyPlan` now wraps key tokens in an array. |
| Rift ignored `SendInput` keyboard events even when Windows reported them sent. | `send-key` now posts targeted `WM_KEYDOWN` / `WM_KEYUP` messages to the bound Rift window. |

The keyboard fix is in:

```text
C:\RIFT MODDING\RiftReader\tools\rift-game-mcp\helpers\window-tools.ps1
```

Key result field from the helper:

```json
"keyboardInputMethod": "window-message"
```

## Work completed in latest pass

| File | Change |
|---|---|
| `tools/rift-game-mcp/index.mjs` | Added `validate_config` MCP tool. |
| `tools/rift-game-mcp/index.mjs` | Added `capture_inventory_reference` MCP tool. |
| `tools/rift-game-mcp/index.mjs` | Propagates `keyboardInputMethod` from key actions. |
| `tools/rift-game-mcp/README.md` | Updated tool list and inventory calibration workflow. |
| `.codex/skills/rift-window-control/SKILL.md` | Updated skill guidance to use `validate_config` and `capture_inventory_reference`. |

## New tools

| Tool | Purpose | Live input? |
|---|---|---:|
| `validate_config` | Checks `bindings.json`, inventory reference paths, hotbar bindings, and capability readiness. | No |
| `capture_inventory_reference` | Captures the current bound game window as an `open` or `closed` inventory reference and can update `bindings.json`. | No key/click input, but requires a bound/focused capture state |

## Expected fresh tool list

After restarting/reloading the MCP server, `npm run validate` should list:

```text
capture_game_window
capture_inventory_reference
click_client
ensure_inventory_closed
ensure_inventory_open
find_game_window
focus_game_window
open_bags
open_inventory
press_hotbar_slot
send_key
suggest_inventory_region
toggle_inventory
validate_config
wait_for_frame_change
```

## Validation performed

Command:

```powershell
cd "C:\RIFT MODDING\RiftReader\tools\rift-game-mcp"
npm run validate
```

Result: ✅ passed.

`validate_config` was also invoked through a fresh MCP client and returned:

| Capability | Result |
|---|---:|
| `canUseInventoryBinding` | ✅ `true` |
| `canUseInventoryToggle` | ✅ `true` |
| `canUseInventoryEnsure` | ❌ `false` |
| `canSuggestInventoryRegion` | ❌ `false` |
| `keyboardInputMethod` | ✅ `window-message` |

## Current config state

`bindings.json` still has inventory verification unset:

```json
{
  "inventory": "b",
  "inventoryVerification": {
    "openReferencePath": null,
    "closedReferencePath": null,
    "region": null
  }
}
```

This is intentional. Bad references were not saved because the live scene changed during capture/combat, which would make state detection noisy.

## Resume plan

| # | Step | Details |
|---:|---|---|
| 1 | Reload Rift MCP/Codex session | Needed so active tool metadata includes `validate_config` and `capture_inventory_reference`. |
| 2 | Run `validate_config` | Confirm `canUseInventoryToggle: true` and see missing reference warnings. |
| 3 | Move character to a quiet/stable scene | Avoid combat, map changes, tooltips, camera motion, or NPC clutter during calibration. |
| 4 | Bind/focus/capture baseline | Use `find_game_window`, `focus_game_window`, `capture_game_window`. |
| 5 | Capture closed reference | Ensure bags are closed, then call `capture_inventory_reference` with `referenceState: "closed"`. |
| 6 | Open bags with `send_key b` or manual `b` | Confirm bags are visibly open and cursor is not hovering items. |
| 7 | Capture open reference | Call `capture_inventory_reference` with `referenceState: "open"`. |
| 8 | Derive region | Run `suggest_inventory_region` with `saveToBindings: true`. |
| 9 | Validate readiness | Run `validate_config`; target `canUseInventoryEnsure: true`. |
| 10 | Test ensure tools | Test `ensure_inventory_open` and `ensure_inventory_closed` only after validation is clean. |

## Safety notes

| Topic | Guidance |
|---|---|
| Live input | Always `find_game_window` → `focus_game_window` → `capture_game_window` before actions. |
| Clicks | Only use `click_client` after inspecting a current screenshot and using client-area coordinates. |
| Inventory refs | Do not capture while in combat, while tooltips are visible, or while the camera/world is moving. |
| Config | Do not set `openReferencePath`, `closedReferencePath`, or `region` from noisy screenshots. |
| MCP reload | If the new tools are not callable in Codex, restart/reload the MCP session even though `npm run validate` passes. |

## Current working tree after this handoff

Expected modified files include:

```text
.codex/skills/rift-window-control/SKILL.md
tools/rift-game-mcp/README.md
tools/rift-game-mcp/index.mjs
docs/analysis/2026-04-24-rift-game-mcp-handoff.md
```
