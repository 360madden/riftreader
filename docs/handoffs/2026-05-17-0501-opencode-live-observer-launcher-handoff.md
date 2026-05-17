# Compact handoff — OpenCode no-input live observer launcher

Generated UTC: `2026-05-17T09:01:01Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

There is now a dedicated optional OpenCode live-observer launcher:
`scripts\riftreader-opencode-live-observer.cmd`. It asks local OpenCode to run
only existing no-input status helpers (`riftreader-live-triage` and compact
workflow status), then summarize live target identity, stale proof boundaries,
movement gate state, safety flags, and next safe action for desktop ChatGPT.

## Implemented files

| Path | Purpose |
|---|---|
| `scripts/riftreader-opencode-live-observer.cmd` | Thin OpenCode wrapper for no-input live observation. |
| `docs/workflow/opencode-non-codex-bridge.md` | Documents the wrapper in the live-triage section. |
| `docs/workflow/live-test-fast-lane-triage.md` | Lists the optional OpenCode observer command. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Adds the wrapper to the non-Codex live blocker path. |

## Safety

The launcher prompt denies edits, staging, commits, pushes, live input, clicks,
movement, `/reloadui`, screenshot hotkeys, CE/x64dbg attach, stale-proof
promotion, and provider repo writes. It does not itself send any game action.

## Resume point

Next safe OpenCode slice: refine `.opencode` template permissions/prompts for
the new compact package/live observer lanes, or stop if the bridge surface is
sufficient for this pass.
