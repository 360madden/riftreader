# 2026-06-09 — Decision packet target-drift loop guard and no-live-target gate

## Current truth

| Item | Status |
|---|---|
| Generated at | `2026-06-09T10:18:00Z` |
| Branch | `main`, clean worktree before this handoff; local branch is ahead of `origin/main` by 7 commits before this handoff commit. |
| Latest local commits | `53e34e4` guards post-update rediscovery target drift; `afab4e6` covers MCP package validation gates; `cb0e45b` records CI-parity handoff blocker; `ea3c0e6`, `1cd41e2`, `6884787`, and `f89aea5` are the earlier MCP validation-gate hardening commits. |
| Decision packet | `scripts\riftreader-decision-packet.cmd --compact-json --write` remains `blocked` / `blocked-safe` for proof recovery. |
| New safe next action | `scripts\get-rift-window-targets.cmd -Json`; this replaced repeated owner-root rediscovery when latest post-update evidence reports `pid-hwnd-mismatch` / `process-start-mismatch`. |
| RIFT target discovery | `scripts\get-rift-window-targets.cmd -Json` at `2026-06-09T10:17:53Z` found `count=0` for `rift_x64`; no current PID/HWND is available for owner-root rediscovery. |
| Proof recovery blocker | Static owner readback still reports `root-pointer-null`; packet blocker remains `latest-static-owner-readback-root-pointer-null`. |
| Post-update recovery state | Candidate-only yaw/facing inventory exists, but it is not route-actionable and includes target identity blockers. |
| Safety state | No movement, game input, reload, screenshot hotkey, target selection, debugger/CE attach, provider write, truth apply, proof promotion, branch rewrite, or Git push was performed. |

## What changed since the prior handoff

| Area | Change |
|---|---|
| Decision packet loop guard | `tools\riftreader_workflow\decision_packet.py` now detects post-update target identity blockers and routes to read-only window target discovery before repeating current-PID rediscovery. |
| CMD-first target discovery | `scripts\get-rift-window-targets.cmd` wraps the existing read-only PowerShell leaf script so future agents can use a CMD-first resume command. |
| Regression coverage | `scripts\test_decision_packet.py` proves `pid-hwnd-mismatch` / `process-start-mismatch` route to `refresh-rift-window-target-discovery`. |
| Workflow docs | `docs\workflow\local-decision-control-plane-plan.md` records the post-update target-drift loop guard. |
| MCP package gate coverage | `scripts\test_riftreader_chatgpt_mcp.py` now verifies dry-run check counts and apply preflight blockers surface through the MCP wrapper. |

## Validation evidence

| Validation | Result |
|---|---|
| Decision packet + tool catalog focused tests | `python -m unittest scripts.test_decision_packet scripts.test_tool_catalog` passed: 83 tests. |
| Latest targeted ledger | Passed: `.riftreader-local\validation-runs\20260609-101455-631243\summary.md`; duration `22.044s`. |
| Previous targeted ledger for same slice | Passed: `.riftreader-local\validation-runs\20260609-101218-444627\summary.md`; duration `24.051s`. |
| MCP wrapper/package gate ledger | Passed: `.riftreader-local\validation-runs\20260609-100252-554742\summary.md`; duration `7.525s`. |
| Target discovery wrapper smoke | `cmd /c "scripts\get-rift-window-targets.cmd -Json"` passed read-only and reported `count=0`. |
| Diff/pre-commit | `git --no-pager diff --check` and `pre-commit run --files ...` passed for the changed files before local commits. |
| CI parity | Still blocked-safe for local-only commits; prior ledger `.riftreader-local\validation-runs\20260609-093529-591706\summary.md` timed out because GitHub had no run for unpushed local `HEAD`. |

## Gate

| Gate | Required behavior |
|---|---|
| Git push | Requires explicit user approval; local branch is ahead and remote CI cannot run for local-only commits until pushed. |
| Launch/relaunch RIFT | Requires explicit approval before starting or interacting with the game/launcher. |
| Target discovery | Read-only `scripts\get-rift-window-targets.cmd -Json` is safe and is the current packet next action. |
| Owner-root rediscovery | Safe only after a current `rift_x64` PID/HWND exists; no-input readback remains allowed. |
| ProofOnly / promotion / current-truth apply | Still blocked without fresh same-target proof gates and explicit approval. |
| Movement/navigation/live target-control | Still blocked until proof recovery succeeds and movement/input is separately approved. |

## Safe resume commands

Run these for read-only status refresh before any live action:

```cmd
git status --short --branch
scripts\riftreader-decision-packet.cmd --compact-json --write
scripts\get-rift-window-targets.cmd -Json
```

If RIFT is running and exactly one valid target is found, continue no-input proof recovery with:

```cmd
python .\scripts\postupdate_owner_root_rediscovery.py --json
```

## Next action

If the goal is proof recovery, start RIFT manually or explicitly approve launch/relaunch, then rerun `scripts\get-rift-window-targets.cmd -Json`. If the goal is publication, explicitly approve pushing the local ahead commits.
