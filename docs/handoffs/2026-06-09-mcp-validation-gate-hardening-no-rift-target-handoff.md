# 2026-06-09 — MCP validation gate hardening and no-live-target proof gate

## Current truth

| Item | Status |
|---|---|
| Generated at | `2026-06-09T09:28:37Z` |
| Branch | `main`, clean worktree before this handoff, `ahead 3` before this handoff commit. |
| Latest local commits | `f89aea5` documented the MCP validation gap; `6884787` runs package dry-run checks in an ignored workspace; `1cd41e2` gates package apply preflight on dry-run check results. |
| Decision packet | `scripts\riftreader-decision-packet.cmd --compact-json --write` remains `blocked` / `blocked-safe`; safe next action is `python .\scripts\postupdate_owner_root_rediscovery.py --json`. |
| RIFT target discovery | `scripts\get-rift-window-targets.ps1 -Json` at `2026-06-09T09:26:21Z` found `count=0` for `rift_x64`; no current PID/HWND is available for owner-root rediscovery. |
| Proof recovery blocker | Latest static owner readback still reports `root-pointer-null`; packet blocker is `latest-static-owner-readback-root-pointer-null`. |
| MCP package intake gate | Dry-run now executes manifest-declared checks in an ignored temporary workspace and reports `runCount`/`failedCount` from actual check execution. |
| MCP apply preflight gate | Apply preflight now rejects dry-run summaries where declared checks were skipped, count-mismatched, invalid, or failed. |
| Safety state | No movement, game input, reload, screenshot hotkey, target selection, debugger/CE attach, provider write, truth apply, proof promotion, branch rewrite, or Git push was performed. |

## Validation evidence

| Validation | Result |
|---|---|
| Package intake + draft review unit tests | `python -m unittest scripts.test_package_intake scripts.test_package_draft_review` passed: 29 tests. |
| Targeted ledger | Passed: `.riftreader-local\validation-runs\20260609-091950-823861\summary.md`; duration `2.819s`, command duration `2.515s`. |
| Smoke ledger | Passed: `.riftreader-local\validation-runs\20260609-092322-583432\summary.md`; duration `1.093s`. |
| Pre-commit gates | Passed for the changed package validation files and docs during local commits. |

## Gate

| Gate | Required behavior |
|---|---|
| Git push | Requires explicit user approval; branch is ahead locally. |
| Launch/relaunch RIFT | Requires explicit approval before starting or interacting with the game/launcher. |
| Owner-root rediscovery | Safe only after a current `rift_x64` PID/HWND exists; no-input readback remains allowed. |
| ProofOnly / promotion / current-truth apply | Still blocked without fresh same-target proof gates and explicit approval. |
| Movement/navigation/live target-control | Still blocked until proof recovery succeeds and movement/input is separately approved. |

## Safe resume commands

Run these only for read-only status refresh before any live action:

```cmd
git status --short --branch
scripts\riftreader-decision-packet.cmd --compact-json --write
scripts\get-rift-window-targets.ps1 -Json
```

If RIFT is running and exactly one valid target is found, the current packet's no-input next diagnostic is:

```cmd
python .\scripts\postupdate_owner_root_rediscovery.py --json
```

## Next action

If the goal is to continue proof recovery, launch RIFT manually or explicitly approve launch/relaunch, then rerun target discovery. If the goal is to publish the MCP validation hardening, explicitly approve pushing the local ahead commits.
