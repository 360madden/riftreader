# Compact handoff — Compact SITREP bridge command capabilities

Generated UTC: `2026-05-17T09:18:22Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

The compact OpenCode SITREP now reports a `bridgeCommands` capability list so
desktop ChatGPT can see which local OpenCode/non-Codex wrappers exist without
asking for broad terminal output or re-reading docs. This includes deterministic
status, OpenCode SITREP, package self-test, package dry-run, package review,
live triage, live observer, and Operator Lite.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/status_packet.py` | Adds bridge command specs and compact `bridgeCommands` capability output. |
| `scripts/test_opencode_status_packet.py` | Verifies capability existence reporting, including package self-test. |
| `docs/workflow/opencode-non-codex-bridge.md` | Documents the compact SITREP `bridgeCommands` field. |

## Safety

This is read-only status metadata. It does not run the commands, send live
input, move, attach CE/x64dbg, apply packages, stage, commit, push, or write
provider repos.

## Resume point

Next safe OpenCode slice: refresh the milestone handoff/index after the
self-test and capability-list additions, then stop unless a new concrete
OpenCode/non-Codex workflow gap appears.
