# Compact handoff — OpenCode / non-Codex bridge milestone

Generated UTC: `2026-05-17T09:04:21Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

The optional OpenCode bridge now has compact status, package-review, live
observer, Operator Lite, and config-template support for the non-Codex desktop
ChatGPT workflow. Desktop ChatGPT can ask the user/OpenCode for small pasteback
packets instead of broad manual terminal dumps, while edits, live input,
movement, debugger attach, commit, push, credentials, and provider writes remain
explicit approval boundaries.

## Command quick reference

| Need | Command | Safety |
|---|---|---|
| Deterministic compact local truth | `scripts\riftreader-workflow-status.cmd --compact-json --write` | No input/movement/debugger/Git mutation. |
| OpenCode one-shot SITREP | `scripts\riftreader-opencode-sitrep.cmd` | OpenCode wrapper around compact status. |
| Package dry-run pasteback | `scripts\riftreader-package-intake.cmd --package "C:\path\to\package" --compact-json` | No repo target writes; writes ignored diff/artifacts. |
| OpenCode package review | `scripts\riftreader-opencode-package-review.cmd "C:\path\to\package-or.zip"` | OpenCode wrapper around package dry-run; no apply. |
| No-input live blocker triage | `scripts\riftreader-live-triage.cmd --json --write` | No live input/movement; reports safe blocker exit `2`. |
| OpenCode live observer | `scripts\riftreader-opencode-live-observer.cmd` | OpenCode wrapper around no-input triage/status. |
| Operator Lite surface | `scripts\riftreader-operator-lite.cmd` | Buttons for compact SITREP, live triage, package dry-run, git status. |
| Template config | `.opencode\opencode.example.jsonc` | Secret-free optional template; local overrides ignored. |

## Current live/stale-proof state

Last no-input checks during this milestone reported:

| Field | Value |
|---|---|
| Live RIFT process | `rift_x64` PID `22304` |
| Current proof artifact | historical PID `27552` / HWND `0x3411E2` |
| Live target verdict | `artifact-pid-stale` |
| Current proof status | `blocked-target-drift` |
| Movement | blocked |
| Stale proof policy | do not reuse as current proof or movement truth |

This is a safe status blocker, not a movement/proof promotion.

## Commits in this OpenCode bridge pass

| Commit | Purpose |
|---|---|
| `f66c71e` | Make OpenCode status live-target aware. |
| `d1569eb` | Add compact OpenCode SITREP status output. |
| `3959014` | Surface compact OpenCode SITREP in Operator Lite. |
| `38bffcd` | Clarify OpenCode live triage stale target guidance. |
| `24834d2` | Add compact OpenCode package intake summaries. |
| `08851ad` | Add OpenCode package review launcher. |
| `da2b83a` | Add OpenCode live observer launcher. |
| `c7fafef` | Refine OpenCode bridge agent prompts. |

## Validation performed

- `python -m compileall tools\riftreader_workflow scripts\test_*.py`
- targeted/broader `python -m unittest ...` with 31 workflow tests passing
- `scripts\riftreader-operator-lite.cmd --self-test --json`
- `scripts\riftreader-workflow-status.cmd --compact-json`
- `scripts\riftreader-live-triage.cmd --json`
- `python .\scripts\coordinate_recovery_status.py --json`
- `python .\scripts\validate_current_truth.py --json`
- `opencode --version` => `1.4.3`
- `git --no-pager diff --check`

Expected safe blocker: status/triage helpers may return blocked/exit `2` while
the live PID and historical proof artifact disagree.

## Boundaries preserved

No command added in this pass stages, commits, pushes, sends live input, moves
the character, runs `/reloadui`, sends screenshot hotkeys, attaches CE/x64dbg,
promotes stale proof, writes provider repos, or stores secrets.

## Resume prompt

> Resume RiftReader OpenCode/non-Codex bridge work from `docs/handoffs/2026-05-17-0504-opencode-bridge-milestone-handoff.md`. Start with `scripts\riftreader-workflow-status.cmd --compact-json --write`, keep movement/input/debugger/provider writes blocked, and only expand the OpenCode bridge if a concrete desktop ChatGPT workflow gap remains.
