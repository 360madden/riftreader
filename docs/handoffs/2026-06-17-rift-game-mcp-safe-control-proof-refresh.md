# 2026-06-18 - RIFT game MCP Phase 9 preflight handoff

## Current truth

| Item | Evidence |
|---|---|
| Scope | Durable handoff for the safe local `tools\rift-game-mcp` movement-control Phase 9 preflight slice. No live RIFT input, movement, focus, click, resize, CE, x64dbg, proof promotion, provider writes, branch rewrite, reset, or cleanup was performed. |
| Baseline head before this handoff commit | `4cfd39c011c18a5d2c5b61ed9da745310a93ad6a` (`Harden RIFT game MCP action fail-closed classification`) pushed to `origin/main`. This handoff update is part of the subsequent Phase 9 preflight slice. |
| Tool count - RIFT game MCP | `npm run validate` in `tools\rift-game-mcp` passed with 25 expected tools after adding `get_movement_execution_preflight`. |
| Phase 9 tool | `get_movement_execution_preflight` is read-only, annotated `readOnlyHint=true` / `destructiveHint=false`, and reports standard control output fields plus exact target facts, current-truth freshness, verification requirements, required approval scope, and Phase 9/10 readiness flags. |
| Current-window smoke artifact | `.riftreader-local\rift-game-mcp\current-window-smoke\current-window-safe-smoke-20260618T051530Z.json` was written by `npm run smoke:current-window:auto`. The smoke remained safe/pass because no input was sent, while the new movement preflight correctly reported Phase 10 blocked. |
| Current RIFT target discovery | Read-only discovery found one target: PID `130540`, HWND `0x9310EA`, title `RIFT`, foreground `false`, minimized `true`, client rect `0x0`, process start `2026-06-17T21:57:01.8571209-04:00`. |
| Phase 10 blocker facts | Preflight blockers: `bound-window-minimized`, `bound-window-client-area-empty`, `bound-window-not-foreground`, `current-truth-too-old`, `current-truth-target-process-id-mismatch:12664!=130540`, and `current-truth-target-window-handle-mismatch:0x205146c!=0x9310ea`. |
| Current-truth status | `docs\recovery\current-truth.json` still points at historical PID `12664` / HWND `0x205146C`, updated `2026-06-02T04:13:42Z`; it must not be treated as current live movement truth for PID `130540`. |
| Stage 38 boundary gate | Approval packet/token path was tested earlier in this lane; `stage38Started=false`, `stage38Active=false`, `movementSent=false`, `inputSent=false`. |
| Final readiness before this slice | `scripts\riftreader-mcp-final.cmd --status --compact-json` previously passed at `2026-06-18T05:05:09Z` for head `4cfd39c`; rerun after the Phase 9 commit before claiming final route readiness. |
| Decision packet | `scripts\riftreader-decision-packet.cmd --compact-json --write` remained blocked-safe for proof recovery on `latest-static-owner-readback-root-pointer-null`; safe target discovery was run. |

## Implemented safe game-control tools

| Tool | Safety boundary |
|---|---|
| `get_game_control_readiness` | Read-only; aggregates bound window, current truth gates/blockers, config summary, and recommended next safe action. |
| `classify_game_action` | Read-only; classifies movement-risk keys/actions as gated and blocked by default; unknown actions fail closed. |
| `plan_movement_step` | Writes only ignored movement-plan artifacts unless `dryRun=true`; never executes input or emits reusable approval tokens. |
| `get_movement_execution_preflight` | Read-only Phase 9 gate for one future bounded movement step; blocks on no bound window, minimized/zero-client window, not foreground, stale or mismatched current truth, overlong holds, non-movement actions, and missing live verification requirements. |
| `get_latest_control_artifact` | Read-only lookup under `.riftreader-local\rift-game-mcp`. |
| `release_all_movement_keys` | Dry-run by default; live path sends only key-up messages for fixed movement-risk keys to exact bound foreground HWND. Dry-run validation only was performed. |

## Validation and error checks

| Command | Result |
|---|---|
| `node --check .\tools\rift-game-mcp\index.mjs; node --check .\tools\rift-game-mcp\validate.mjs; node --check .\tools\rift-game-mcp\test-control-tools.mjs; node --check .\tools\rift-game-mcp\safe-current-window-smoke.mjs` | Passed. |
| `npm run validate` in `tools\rift-game-mcp` | Passed; 25 expected tools, control output/safety schema checks, and no-input smoke self-test. |
| `npm run test:control` in `tools\rift-game-mcp` | Passed; classifier matrix, read-only movement preflight no-bound/non-movement blocks, dry-run release, movement-plan artifact writing, and latest artifact lookup. |
| `npm run test:smoke` in `tools\rift-game-mcp` | Passed; synthetic target-discovery lane selection and multi-target guard. |
| `npm run smoke:current-window:auto` in `tools\rift-game-mcp` | Passed as a no-input safety smoke; it also reported Phase 10 preflight blocked for minimized/stale-target conditions. |
| `git diff --check` | Pending after this handoff edit. |
| `pre-commit` | Pending after this handoff edit. |
| GitHub Actions | Pending after the Phase 9 commit/push. |
| Final readiness | Pending after the Phase 9 commit/push. |

## Operational notes

- `get_movement_execution_preflight` is not a live executor. It performs no focus, capture, release, key send, click, resize, CE/x64dbg, provider write, proof promotion, or SavedVariables live-truth use.
- The current-window smoke can pass while Phase 10 is blocked; smoke pass means the dry-run path remained safe, not that live movement is ready.
- Do not send live movement/input until the window is restored/non-minimized, foregrounding is performed by the live sequence, current-truth is refreshed for the exact PID/HWND/process start, and Phase 9 preflight passes.
- Keep using `START_RIFTREADER_CHATGPT_MCP.cmd` for the non-Codex ChatGPT/Desktop HTTP MCP lane on `127.0.0.1:8770`; do not assume saved connector config starts the local runtime.
- The public ChatGPT/Desktop MCP surface remains the narrow repo adapter. Do not add public ChatGPT live movement tools.
- SavedVariables remain forbidden as live movement truth.

## Recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit/push the Phase 9 preflight slice after `git diff --check` and pre-commit pass. | Makes the local MCP safety gate durable. |
| 2 | Rerun GitHub Actions and `scripts\riftreader-mcp-final.cmd --status --compact-json` after push. | Restores final-readiness evidence for the new head. |
| 3 | Add a small explicit `get_movement_execution_preflight` sample to operator docs if needed. | Reduces confusion between dry-run smoke pass and Phase 10 readiness. |
| 4 | Restore/unminimize the RIFT window only as an explicit live-window operator action. | Current target has a zero client area, so visual verification is impossible. |
| 5 | Refresh current-target readback/current-truth for PID `130540` / HWND `0x9310EA` before any movement. | Current-truth still points at PID `12664` / HWND `0x205146C`. |
| 6 | Rerun `npm run smoke:current-window:auto` after restore/current-truth refresh. | Confirms Phase 9 blockers are resolved without sending input. |
| 7 | Generate a one-shot `plan_movement_step` artifact for the exact target before Phase 10. | Records exact action, hold, target facts, approval scope, and verification requirements. |
| 8 | For Phase 10, execute only one bounded semantic movement step, then release and verify. | Prevents broad route-control or reusable movement approval drift. |
| 9 | Keep CE/x64dbg/provider/proof-promotion work out of this MCP movement slice. | Maintains the safe local automation boundary. |
| 10 | If Phase 10 remains blocked, keep working safe-local on better preflight diagnostics rather than forcing live input. | Preserves progress without crossing unsafe gates. |
