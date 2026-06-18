# 2026-06-17 - RIFT game MCP safe control slice and proof refresh

## Current truth

| Item | Evidence |
|---|---|
| Scope | Durable handoff for the safe local `tools\rift-game-mcp` movement-control planning/release slice plus ChatGPT/Desktop MCP proof refresh. No live RIFT input, movement, focus, click, resize, CE, x64dbg, proof promotion, provider writes, branch rewrite, reset, or cleanup was performed. |
| Current head | `722d9a92b096633abd8883e8af32bec22bce18fd` (`Validate RIFT game MCP smoke guard`) pushed to `origin/main`. |
| Recent safe game-control commits | `8cf32f2` added readiness/classify/plan/latest-artifact tools; `ad93cb4` added dry-run-default movement-key release; `7415821`, `44e3c04`, `e795cc2`, `ff58b4e`, `01c003d`, and `722d9a9` added the tracked current-window dry-run smoke, read-only target discovery mode, artifact lookup, multi-target fail-closed guard, synthetic self-test, and `npm run validate` integration. |
| Tool count - RIFT game MCP | `npm run validate` in `tools\rift-game-mcp` passed with 24 expected tools, including `release_all_movement_keys`, and now runs the no-input current-window smoke self-test. |
| Tool count - ChatGPT/Desktop MCP | `get_tool_surface_diff` passed with 33 source/runtime/actual-client tools and 33 output schemas. |
| Actual-client proof | `get_actual_client_proof_status` replay passed; proof path `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260617-194828Z\proof.json`, 33 tools, `clientTransportStatus=tool-call-succeeded`, `healthCallSucceeded=true`, freshness `fresh`. |
| Local HTTP MCP runtime | `scripts\riftreader-mcp-server-status.cmd` reported `running-current` on `http://127.0.0.1:8770/mcp`, PID `134408`, full profile, source-fresh, 33/33 observed tools. |
| Codex stdio MCP handle | In-thread `mcp__riftreader.get_mcp_runtime_status` still returned `Transport closed`; direct repo adapter/status calls are the current proof path until the Codex connector is reloaded. |
| Final readiness | `scripts\riftreader-mcp-final.cmd --status --compact-json` passed at `2026-06-18T03:20:42Z`; blockers `[]`, proof freshness `fresh`, CI `passed`, current head `722d9a92b096633abd8883e8af32bec22bce18fd`. |
| RIFT target discovery | `scripts\get-rift-window-targets.cmd -Json` passed read-only and found one target: PID `130540`, HWND `0x9310EA`, title `RIFT`, foreground `false`, responding `true`. |
| RIFT game MCP safe smoke | Tracked script `tools\rift-game-mcp\safe-current-window-smoke.mjs` passed via `npm run smoke:current-window:auto` at `2026-06-18T03:14:54Z`. It used read-only target discovery, bound PID `130540` / HWND `0x9310EA` read-only, then ran readiness, movement classification, `release_all_movement_keys` dry-run, and `plan_movement_step` dry-run. Result: readiness `ready-for-planning`, release dry-run `inputSent=false`, `movementSent=false`, `keysReleased=false`; plan dry-run `planned`, no artifact written. |
| RIFT game MCP smoke self-test | `npm run test:smoke` passed with synthetic discovery packets only: single-target selection, multi-target fail-closed default, explicit multi-target override, missing lane block, and missing exact PID/HWND block. It does not start the MCP server, discover live windows, bind a target, send input, or write artifacts. |
| Decision packet | `scripts\riftreader-decision-packet.cmd --compact-json --write` remains blocked-safe for proof recovery on `latest-static-owner-readback-root-pointer-null`; its safe diagnostic target discovery was run. |

## Implemented safe game-control tools

| Tool | Safety boundary |
|---|---|
| `get_game_control_readiness` | Read-only; aggregates bound window, current truth gates/blockers, config summary, and recommended next safe action. |
| `classify_game_action` | Read-only; classifies movement-risk keys/actions as gated and blocked by default. |
| `plan_movement_step` | Writes only ignored movement-plan artifacts unless `dryRun=true`; never executes input or emits reusable approval tokens. |
| `get_latest_control_artifact` | Read-only lookup under `.riftreader-local\rift-game-mcp`. |
| `release_all_movement_keys` | Dry-run by default; live path sends only key-up messages for fixed movement-risk keys to exact bound foreground HWND. Dry-run validation only was performed. |

## Validation and error checks

| Command | Result |
|---|---|
| `node --check .\tools\rift-game-mcp\index.mjs; node --check .\tools\rift-game-mcp\validate.mjs; node --check .\tools\rift-game-mcp\test-control-tools.mjs; node --check .\tools\rift-game-mcp\safe-current-window-smoke.mjs` | Passed. |
| PowerShell parser check for `tools\rift-game-mcp\helpers\window-tools.ps1` | Passed. |
| `git --no-pager diff --check -- tools/rift-game-mcp/...` | Passed before commit. |
| `npm run validate` in `tools\rift-game-mcp` | Passed; 24 expected tools plus no-input smoke self-test. |
| `npm run test:control` in `tools\rift-game-mcp` | Passed; classification, dry-run release, movement-plan artifact writing, latest artifact lookup. |
| `npm run test:smoke` in `tools\rift-game-mcp` | Passed; synthetic target-discovery lane selection and multi-target guard. |
| `npm run smoke:current-window:auto` in `tools\rift-game-mcp` | Passed; no-input exact-target dry-run against the single discovered RIFT window. |
| Pre-commit on latest safe slices | Passed. |
| GitHub Actions for `722d9a9` | `.NET build and test` run `27734302551` passed; `RiftReader Policy` run `27734302490` passed. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_tool_surface_diff --json` | Passed; source/runtime/actual-client tool surface consistent. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_actual_client_proof_status --json` | Passed; actual-client proof replay fresh. |
| `scripts\riftreader-mcp-final.cmd --status --compact-json` | Passed. |
| `git status --short --branch` before this handoff | Clean at `main...origin/main`. |

## Operational notes

- Keep using `START_RIFTREADER_CHATGPT_MCP.cmd` for the non-Codex ChatGPT/Desktop HTTP MCP lane on `127.0.0.1:8770`; do not assume saved connector config starts the local runtime.
- The public ChatGPT/Desktop MCP surface remains the narrow 33-tool repo adapter. Do not add public ChatGPT live movement tools.
- `tools\rift-game-mcp` is the local game-window control MCP. Its new movement-control layer is currently planning/dry-run only unless an explicit live input gate is opened.
- `tools\rift-game-mcp\safe-current-window-smoke.mjs` is tracked and reusable. Its `--self-test` path is purely synthetic and is now part of `npm run validate`.
- `release_all_movement_keys` has a live key-up path, but it was not run with `dryRun=false`.
- Current exact RIFT target is not foreground; any live action would need explicit approval and exact-target focus/checks first.
- SavedVariables remain forbidden as live movement truth.

## Recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | In the actual ChatGPT/Desktop client, reconnect/reload the stale Codex stdio-style `mcp__riftreader` surface only if in-thread tools are needed. | The HTTP backend is healthy, but this Codex thread's MCP tool handle remains closed. |
| 2 | Rerun `scripts\riftreader-mcp-final.cmd --status --compact-json` before demos/releases. | Proof and artifacts are freshness-budgeted. |
| 3 | Keep the current HTTP MCP process alive unless source changes require an exact restart. | Runtime is source-fresh and full-profile 33/33. |
| 4 | Use `tools\rift-game-mcp` readiness/classify/plan dry-runs before any future live control. | They provide explicit movement gate and target facts without input. |
| 5 | If planning live movement, generate a one-shot `plan_movement_step` artifact first. | It records exact target facts, max hold duration, approval scope, and verification requirements. |
| 6 | Do not call `release_all_movement_keys` with `dryRun=false` unless a live safety-release action is explicitly approved. | It sends key-up input even though it does not send movement key-down input. |
| 7 | Keep `npm run validate`, `npm run test:control`, `npm run test:smoke`, and `npm run smoke:current-window:auto` together as the local RIFT game MCP safety gate. | This covers schemas, semantic classification, dry-run planning artifacts, synthetic multi-target fail-closed behavior, and exact-target no-input smoke. |
| 8 | If proof recovery resumes, start from the read-only target discovery result: PID `130540`, HWND `0x9310EA`, process start `2026-06-17T21:57:01.8571209-04:00`. | Avoids stale PID/HWND assumptions. |
| 9 | Keep the `latest-static-owner-readback-root-pointer-null` blocker separate from game-window MCP readiness. | Game-control planning can be ready while coordinate/proof recovery is blocked-safe. |
| 10 | Stop before live movement/input, focus/click/resize, CE/x64dbg, provider writes, or proof/truth promotion unless explicitly approved for that exact action. | Maintains the repo hard safety boundary. |
