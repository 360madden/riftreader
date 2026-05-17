# Compact handoff — Operator Lite package-intake self-test button

Generated UTC: `2026-05-17T09:16:08Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Operator Lite now exposes Package Intake Self-Test as a safe button/command-plan
entry. This lets the user or OpenCode smoke-test the package-review lane from
the local GUI without selecting a real desktop ChatGPT package and without
applying edits.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/operator_lite.py` | Adds `package-selftest` command spec/button and includes self-test reports in latest-report lookup. |
| `scripts/test_operator_lite.py` | Verifies the command-plan entry and latest-report lookup for self-test outputs. |
| `docs/workflow/operator-lite.md` | Documents the new self-test button and ignored output path. |

## Safety

The button runs `scripts\riftreader-package-intake-selftest.cmd`, which is
dry-run only and writes under `.riftreader-local\package-intake-selftest\...`.
It does not stage, commit, push, apply package files, send live input, move,
attach CE/x64dbg, or write provider repos.

## Resume point

Next safe OpenCode slice: run the Operator Lite self-test command plan and then
decide whether any non-Codex bridge friction remains.
