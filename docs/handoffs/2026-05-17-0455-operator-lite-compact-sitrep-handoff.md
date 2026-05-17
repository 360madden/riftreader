# Compact handoff — Operator Lite compact OpenCode SITREP

Generated UTC: `2026-05-17T08:55:00Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Operator Lite now exposes the compact OpenCode/non-Codex SITREP path directly.
This avoids making the user or local OpenCode remember `--compact --write` and
treats expected safe blocker exit code `2` as an acceptable status result for
workflow status and live triage commands.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/operator_lite.py` | Adds `compact-sitrep` command spec/button and expected-exit-code handling. |
| `scripts/test_operator_lite.py` | Verifies compact SITREP command presence and expected `0/2` exit handling. |
| `docs/workflow/operator-lite.md` | Documents the compact SITREP button and safe blocker exit semantics. |

## Safety

No live input, movement, `/reloadui`, screenshot key, CE/x64dbg attach,
provider write, stage, commit, or push is added. The new command only runs the
existing no-input status packet helper.

## Resume point

Next safe OpenCode slice: consider adding a tiny package-intake summary mode for
desktop ChatGPT packages, or stop workflow changes if no more practical friction
appears.
