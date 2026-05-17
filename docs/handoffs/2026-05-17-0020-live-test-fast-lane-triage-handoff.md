# Compact handoff — Live-Test Fast-Lane Triage

Generated UTC: `2026-05-17T04:20:00Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Added an offline-safe live-test triage helper that classifies the current failed
stage from status packets and existing artifacts. It is read-only except for
ignored `.riftreader-local` reports. It does not send input, run movement,
attach CE/x64dbg, stage, commit, push, or write provider repos.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/live_test_triage.py` | Builds a status packet, classifies the current blocker, and emits JSON/Markdown triage. |
| `scripts/riftreader-live-triage.cmd` | Thin launcher for the triage helper. |
| `scripts/test_live_test_triage.py` | Tests stage classification and ignored output paths. |
| `docs/workflow/live-test-fast-lane-triage.md` | Operator guide and classification order. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Updated with triage command. |
| `docs/workflow/opencode-non-codex-bridge.md` | Updated with OpenCode triage prompt. |
| `.opencode/opencode.example.jsonc` | Updated with allow-gated triage command entries. |

## Public command

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-live-triage.cmd --json --write
```

Expected while RIFT is offline:

| Field | Value |
|---|---|
| `status` | `blocked` |
| `failedStage` | `live-target` |
| `blockerCategory` | `no-live-process` |
| Safety | All movement/input/debugger/git/provider flags false |

## Validation target

Run:

```powershell
python -m unittest scripts.test_live_test_triage scripts.test_package_intake scripts.test_opencode_status_packet
python -m compileall tools\riftreader_workflow scripts\test_live_test_triage.py
.\scripts\riftreader-live-triage.cmd --json --write
git --no-pager diff --check
```

## Next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Validate and commit this triage milestone. | Preserves the next workflow-control-plane slice. |
| 2 | Later add Operator Lite buttons around status, package intake, and triage. | This is the next roadmap phase after stable CLI helpers. |
