# Compact handoff — OpenCode bridge resume index after continued work

Generated UTC: `2026-05-17T09:19:19Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

After the original OpenCode bridge milestone, the resumed pass added a package
intake self-test, wired it into Operator Lite, and made compact SITREP report
the available bridge wrapper commands. Desktop ChatGPT can now ask for one
compact status packet and see both current local truth and the safe command
surface available on the PC.

## Current local truth

Last no-input compact status reported:

| Field | Value |
|---|---|
| HEAD before this handoff | `50607de` — `Report OpenCode bridge commands in compact status` |
| Worktree | clean before this handoff |
| Live target | `artifact-pid-stale` |
| Live PID | `22304` |
| Historical proof artifact | PID `27552` / HWND `0x3411E2` |
| Movement | blocked |
| OpenCode | available, version `1.4.3` |

## Safe command surface now reported by compact SITREP

| Key | Command |
|---|---|
| `compact-status` | `scripts\riftreader-workflow-status.cmd --compact-json --write` |
| `opencode-sitrep` | `scripts\riftreader-opencode-sitrep.cmd` |
| `package-intake-selftest` | `scripts\riftreader-package-intake-selftest.cmd` |
| `package-intake` | `scripts\riftreader-package-intake.cmd --package <path> --compact-json` |
| `opencode-package-review` | `scripts\riftreader-opencode-package-review.cmd <package>` |
| `live-triage` | `scripts\riftreader-live-triage.cmd --json --write` |
| `opencode-live-observer` | `scripts\riftreader-opencode-live-observer.cmd` |
| `operator-lite` | `scripts\riftreader-operator-lite.cmd` |

## New commits after the first milestone handoff

| Commit | Purpose |
|---|---|
| `6bbd165` | Add package intake self-test for OpenCode bridge. |
| `cd70429` | Add Operator Lite package intake self-test. |
| `50607de` | Report OpenCode bridge commands in compact status. |

## Validation performed during resumed pass

- `python -m compileall tools\riftreader_workflow scripts\test_*.py`
- `python -m unittest scripts.test_workflow_common scripts.test_operator_lite scripts.test_live_test_triage scripts.test_package_intake scripts.test_opencode_status_packet`
- `scripts\riftreader-package-intake-selftest.cmd`
- `scripts\riftreader-operator-lite.cmd --self-test --json`
- `scripts\riftreader-workflow-status.cmd --compact-json`
- `scripts\riftreader-live-triage.cmd --json`
- `python .\scripts\validate_current_truth.py --json`
- `opencode --version`
- `git --no-pager diff --check`

## Boundaries preserved

No resumed-slice command stages, commits, pushes except explicit repo commits,
sends live input, moves, runs `/reloadui`, sends screenshot hotkeys, attaches
CE/x64dbg, applies package files without `--apply`, writes provider repos, or
promotes stale proof.

## Resume prompt

> Resume RiftReader OpenCode/non-Codex bridge work from `docs/handoffs/2026-05-17-0519-opencode-bridge-resume-index.md`. Start with `scripts\riftreader-workflow-status.cmd --compact-json --write`. If `bridgeCommands` exists and all expected wrappers are present, only continue if a concrete desktop ChatGPT/OpenCode workflow friction remains; do not drift into live proof, movement, CE/x64dbg, or provider repos without explicit authorization.
