# Compact handoff — OpenCode package-review launcher

Generated UTC: `2026-05-17T08:59:21Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

There is now a thin optional OpenCode package-review launcher:
`scripts\riftreader-opencode-package-review.cmd`. It runs OpenCode with a
bounded prompt that performs package inspection only through Package Intake Lite
`--compact-json`, summarizes the compact result for desktop ChatGPT, and does
not apply edits.

## Implemented files

| Path | Purpose |
|---|---|
| `scripts/riftreader-opencode-package-review.cmd` | Thin OpenCode wrapper for package dry-run review. |
| `docs/workflow/opencode-non-codex-bridge.md` | Documents the one-shot OpenCode package review wrapper. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Adds the optional wrapper to the package inspection path. |
| `docs/workflow/package-intake-lite.md` | Lists the wrapper alongside compact package-intake commands. |

## Safety

The launcher prompt denies edits, apply, staging, commits, pushes, live input,
movement, `/reloadui`, screenshot hotkeys, CE/x64dbg attach, and provider repo
writes. It is optional and falls back to direct Package Intake Lite if OpenCode
is not available.

## Resume point

Next safe OpenCode slice: add a no-input live observer one-shot launcher if
useful, or stop if launcher/docs/test coverage are enough for the current
OpenCode bridge pass.
