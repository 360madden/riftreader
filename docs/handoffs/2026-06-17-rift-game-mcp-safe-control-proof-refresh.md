# 2026-06-18 - RIFT game MCP Phase 10 dry-run wrapper handoff

## Current truth

| Item | Evidence |
|---|---|
| Scope | Durable handoff for the safe local `tools\rift-game-mcp` Phase 10 wrapper slice. Implementation and validation stayed no-input: no live RIFT movement, focus, click, resize, CE, x64dbg, proof promotion, provider writes, branch rewrite, reset, or cleanup was performed. |
| Baseline head before this wrapper slice | `968c3a1db81e5d536c6c05325807bedcf5bbd0d2` (`Update RIFT game MCP Phase 9 handoff`) pushed to `origin/main`. |
| Tool count - RIFT game MCP | `npm run validate` in `tools\rift-game-mcp` passed with 26 expected tools after adding `execute_movement_step`. |
| Phase 10 wrapper | `execute_movement_step` defaults to `dryRun: true`, internally calls `get_movement_execution_preflight`, emits an exact one-shot approval phrase, and refuses live execution before input if preflight, approval, or verification requirements are not satisfied. It is annotated non-read-only/destructive because the gated live path can focus/capture/send/release/wait when all gates pass. |
| No-input current-window smoke artifact | `.riftreader-local\rift-game-mcp\current-window-smoke\current-window-safe-smoke-20260618T053555Z.json` was written by `npm run smoke:current-window:auto`. The smoke stayed safe/pass because no input was sent while `movementPreflight` and `executeDryRun` correctly reported Phase 10 blocked. |
| Current RIFT target discovery | Read-only discovery found one target: PID `130540`, HWND `0x9310EA`, title `RIFT`, foreground `false`, minimized `true`, client rect `0x0`, process start `2026-06-17T21:57:01.8571209-04:00`. |
| Phase 10 blocker facts from preflight | `bound-window-minimized`, `bound-window-client-area-empty`, `bound-window-not-foreground`, `current-truth-too-old`, `current-truth-target-process-id-mismatch:12664!=130540`, and `current-truth-target-window-handle-mismatch:0x205146c!=0x9310ea`. |
| Phase 10 blocker facts from executor dry-run | `execute_movement_step` with `dryRun:true` returned `dry-run-blocked`, `executionAttempted=false`, `movementSent=false`, `inputSent=false`; blockers were minimized/zero-client/stale-current-truth/PID-HWND mismatch. |
| Current-truth status | `docs\recovery\current-truth.json` still points at historical PID `12664` / HWND `0x205146C`, updated `2026-06-02T04:13:42Z`; it must not be treated as current live movement truth for PID `130540`. |
| Latest final readiness before this slice | `scripts\riftreader-mcp-final.cmd --status --compact-json` passed at `2026-06-18T05:28:08Z` for head `968c3a1db81e5d536c6c05325807bedcf5bbd0d2`; rerun after this wrapper slice commit/push. |

## Implemented safe game-control tools

| Tool | Safety boundary |
|---|---|
| `get_game_control_readiness` | Read-only; aggregates bound window, current truth gates/blockers, config summary, and recommended next safe action. |
| `classify_game_action` | Read-only; classifies movement-risk keys/actions as gated and blocked by default; unknown actions fail closed. |
| `plan_movement_step` | Writes only ignored movement-plan artifacts unless `dryRun=true`; never executes input or emits reusable approval tokens. |
| `get_movement_execution_preflight` | Read-only Phase 9 gate for one future bounded movement step; blocks on no bound window, minimized/zero-client window, not foreground, stale or mismatched current truth, overlong holds, non-movement actions, and missing live verification requirements. |
| `execute_movement_step` | Phase 10 wrapper; dry-run by default and no-input during validation. Live path requires passing preflight, exact one-shot approval phrase, focus/capture/send/release/wait sequencing, and still records that fresh live coordinate-delta verification is required before proof completion. |
| `get_latest_control_artifact` | Read-only lookup under `.riftreader-local\rift-game-mcp`. |
| `release_all_movement_keys` | Dry-run by default; live path sends only key-up messages for fixed movement-risk keys to exact bound foreground HWND. Dry-run validation only was performed. |

## Validation and error checks

| Command | Result |
|---|---|
| `node --check .\tools\rift-game-mcp\index.mjs; node --check .\tools\rift-game-mcp\validate.mjs; node --check .\tools\rift-game-mcp\test-control-tools.mjs; node --check .\tools\rift-game-mcp\safe-current-window-smoke.mjs` | Passed. |
| `npm run validate` in `tools\rift-game-mcp` | Passed; 26 expected tools, control output/safety schema checks, and no-input smoke self-test. |
| `npm run test:control` in `tools\rift-game-mcp` | Passed; classifier matrix, read-only preflight blocks, dry-run Phase 10 wrapper no-bound/non-movement blocks, dry-run release, movement-plan artifact writing, and latest artifact lookup. |
| `npm run test:smoke` in `tools\rift-game-mcp` | Passed; synthetic target-discovery lane selection and multi-target guard. |
| `npm run smoke:current-window:auto` in `tools\rift-game-mcp` | Passed as a no-input safety smoke; it also reported Phase 10 preflight and executor dry-run blocked for minimized/stale-target conditions. |
| `git diff --check` | Pending after this handoff edit. |
| `pre-commit` | Pending after this handoff edit. |
| GitHub Actions | Pending after this wrapper slice commit/push. |
| Final readiness | Pending after this wrapper slice commit/push. |

## Operational notes

- `execute_movement_step` is the Phase 10 wrapper but not proof completion by itself. It intentionally records `fresh-live-coordinate-delta-verification-still-required` after a live send until a true live coordinate surface verifies movement.
- Dry-run smoke pass means the wrapper stayed safe and reported blockers; it does not mean live movement is ready.
- Do not send live movement/input until the window is restored/non-minimized, current-truth is refreshed for exact PID/HWND/process start, and Phase 9 preflight plus the wrapper dry-run are ready for the same one-shot target/action/hold.
- The public ChatGPT/Desktop MCP surface remains the narrow repo adapter. Do not add public ChatGPT live movement tools.
- SavedVariables remain forbidden as live movement truth.

## Recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit/push the Phase 10 dry-run wrapper slice after `git diff --check` and pre-commit pass. | Makes the executor gate durable. |
| 2 | Rerun GitHub Actions and `scripts\riftreader-mcp-final.cmd --status --compact-json` after push. | Restores final-readiness evidence for the new head. |
| 3 | Add a fresh exact-target current-truth/readback refresh lane for PID `130540` / HWND `0x9310EA`. | Current truth still points at PID `12664` / HWND `0x205146C`. |
| 4 | Restore/unminimize the RIFT window only as an explicit live-window action. | Current target has a zero client area, so visual verification is impossible. |
| 5 | Rerun `npm run smoke:current-window:auto` after restore/current-truth refresh. | Confirms Phase 10 blockers are resolved without sending input. |
| 6 | Generate a one-shot `plan_movement_step` artifact for the exact target/action/hold. | Records approval scope and target facts. |
| 7 | Run `execute_movement_step` first with `dryRun:true` and copy only its exact approval phrase if all gates pass. | Prevents broad/reusable movement approval. |
| 8 | Execute one bounded Phase 10 movement step only after the exact approval phrase and fresh proof gates pass. | Keeps live action narrow and reversible. |
| 9 | Add/attach a true live coordinate delta verifier before marking Phase 10 proof complete. | Visual frame change alone is not movement proof. |
| 10 | Update this handoff after the first actual live proof or if blockers persist. | Keeps the current state durable. |
