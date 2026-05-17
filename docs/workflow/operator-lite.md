# Operator Lite

Created: 2026-05-17
Scope: Offline-safe local launcher for the non-Codex/OpenCode RiftReader
workflow-control-plane helpers.

## Verdict

Operator Lite v0 is a small Python/Tkinter helper that launches only safe
workflow commands:

- Workflow Status;
- Compact OpenCode SITREP;
- Live-Test Fast-Lane Triage;
- Package Intake dry-run;
- Git Status;
- Open Latest Report.

It intentionally disables target-control, visual gate, ProofOnly, movement, CE,
x64dbg, staging, committing, and pushing.

## Commands

Launch GUI:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd
```

Headless command-plan/self-test:

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd --self-test --json
```

## Buttons

| Button | Action | Safety |
|---|---|---|
| Refresh Workflow Status | Runs `scripts\riftreader-workflow-status.cmd --write`. | No input/movement/debugger/Git mutation; exit `2` means a safe blocker. |
| Compact OpenCode SITREP | Runs `scripts\riftreader-workflow-status.cmd --compact --write`. | Paste-ready for desktop ChatGPT; exit `2` means a safe blocker. |
| Run Live-Test Triage | Runs `scripts\riftreader-live-triage.cmd --write`. | No input/movement/debugger/Git mutation. |
| Package Intake Dry-Run | Lets the operator choose a package and runs intake without `--apply`. | No repo target writes. |
| Git Status | Runs `git --no-pager status --short --branch`. | Read-only Git. |
| Open Latest Report | Opens latest ignored `.riftreader-local` report. | Local view only. |
| Target-Control / Visual Gate / ProofOnly / Movement | Disabled in v0. | Prevents live action drift. |

## Safety contract

Operator Lite v0 writes only through the underlying helpers:

- `.riftreader-local\opencode-status\...`
- `.riftreader-local\live-test-triage\...`
- `.riftreader-local\package-intake\...`

It does not stage, commit, push, reset, clean, send game input, run movement,
attach CE/x64dbg, or write provider repos. Current stale proof remains
historical-only until fresh current-PID recovery and same-target `ProofOnly`
pass.
