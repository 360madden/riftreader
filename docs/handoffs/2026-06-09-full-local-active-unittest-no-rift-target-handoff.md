# 2026-06-09 — Full-local active unittest validation and no-RIFT-target gate

## Current truth

| Item | Status |
|---|---|
| Generated at | `2026-06-09T11:18:47Z` |
| Branch | `main`, clean worktree before this handoff; local branch is ahead of `origin/main` by 9 commits before this handoff commit. |
| Latest local commit | `70c8ce3 Keep full local validation on active tests`. |
| Local repo | Reachable at `C:\RIFT MODDING\RiftReader`. |
| Decision packet | `scripts\riftreader-decision-packet.cmd --compact-json --write` remains `blocked` / `blocked-safe` for proof recovery. |
| Safe next action | `scripts\get-rift-window-targets.cmd -Json`. |
| RIFT target discovery | `scripts\get-rift-window-targets.cmd -Json` at `2026-06-09T11:18:47Z` found `count=0` for `rift_x64`; no current PID/HWND is available for owner-root rediscovery. |
| Proof recovery blocker | Static owner readback still reports `root-pointer-null`; packet blocker remains `latest-static-owner-readback-root-pointer-null`. |
| Post-update recovery state | Candidate-only yaw/facing inventory exists, but it remains not route-actionable and includes target identity blockers. |
| Safety state | No movement, game input, reload, screenshot hotkey, target selection, debugger/CE attach, provider write, truth apply, proof promotion, branch rewrite, or Git push was performed. |

## What changed

| Area | Change |
|---|---|
| Full-local validation | `tools\riftreader_workflow\validation_ledger.py` now runs `unittest-discover-active` instead of raw global unittest discovery. |
| Active unittest helper | `tools\riftreader_workflow\unittest_discover_active.py` discovers tests under `scripts`, excludes retired OpenCode suites by default, and provides `--json`, `--self-test`, and controlled error reporting. |
| Retired OpenCode boundary | The retired OpenCode suites remain available by explicit opt-in with `--include-retired-opencode`; default `full-local` no longer blocks on that retired surface. |
| Test coverage | `scripts\test_unittest_discover_active.py` covers filtering and self-test behavior; `scripts\test_validation_ledger.py` verifies `full-local` uses active discovery. |

## Validation evidence

| Validation | Result |
|---|---|
| Post-commit full-local ledger | Passed: `.riftreader-local\validation-runs\20260609-111219-900949\summary.md`; duration `214.490s`. |
| Active unittest discovery inside ledger | Passed: `1925` active tests, `34` retired OpenCode tests skipped; duration `160.269s`. |
| Policy lint inside ledger | Passed with no blockers/warnings. |
| .NET restore/build/test inside ledger | Passed. |
| Git commit hook | Passed before commit `70c8ce3`. |
| Safe target discovery | Passed read-only and reported `count=0` for `rift_x64`. |

## Gate

| Gate | Required behavior |
|---|---|
| Git push | Requires explicit user approval; local branch is ahead and remote CI cannot run for local-only commits until pushed. |
| Launch/relaunch RIFT | Requires explicit approval before starting or interacting with the game/launcher. |
| Target discovery | Read-only `scripts\get-rift-window-targets.cmd -Json` is safe and is the current packet next action. |
| Owner-root rediscovery | Safe only after a current `rift_x64` PID/HWND exists; no-input readback remains allowed. |
| Retired OpenCode maintenance | Requires explicit reauthorization before changing or expanding retired OpenCode surfaces. |
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

Run current local validation with:

```cmd
python tools\riftreader_workflow\validation_ledger.py --tier full-local
```

## Next action

If the goal is proof recovery, start RIFT manually or explicitly approve launch/relaunch, then rerun `scripts\get-rift-window-targets.cmd -Json`. If the goal is publication, explicitly approve pushing the local ahead commits.
