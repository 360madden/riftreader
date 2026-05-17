# Compact handoff — OpenCode live-aware status packet

Generated UTC: `2026-05-17T08:45:00Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

RIFT is online again, but the current proof artifact still points at historical
PID `27552` / HWND `0x3411E2`. The observed live `rift_x64` PID was `22304`, so
OpenCode/non-Codex status must report `artifact-pid-stale` instead of repeating
the older offline-only "no live process" conclusion as if it were current.

This slice makes the status packet more useful for desktop ChatGPT by:

- detecting Windows OpenCode npm shims through a safe `cmd /d /c opencode --version` command;
- surfacing a top-level live-target summary;
- warning when current-truth docs are stale because a live process now exists;
- overriding the next action when the live target exists but the proof artifact
  points at an old PID/HWND.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/status_packet.py` | Adds Windows-safe OpenCode version command and top-level live-target summary/next-action handling. |
| `scripts/test_opencode_status_packet.py` | Covers OpenCode version command shape and live artifact-PID-stale status wording. |
| `.opencode/opencode.example.jsonc` | Allows the Windows shim-safe `cmd /d /c opencode --version` command. |
| `docs/workflow/opencode-non-codex-bridge.md` | Documents live-aware/no-input stale-artifact handling. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Documents online `artifact-pid-stale` blocker semantics for desktop ChatGPT. |

## Safety

No movement, live input, `/reloadui`, screenshot hotkey, CE/x64dbg attach,
provider write, stage, commit, or push is performed by the helpers. The status
packet remains read-only except optional ignored `.riftreader-local` artifacts.

## Resume point

Next safe OpenCode slice: improve the OpenCode SITREP wrapper/prompt so its
one-shot summary explicitly calls out live PID versus stale proof artifact when
RIFT is online.

## Follow-up completed in next slice

The status packet now also supports compact output:

```powershell
.\scripts\riftreader-workflow-status.cmd --compact
.\scripts\riftreader-workflow-status.cmd --compact-json
```

`--write` also emits `COMPACT_SITREP.md` and `compact-sitrep.json` under the
ignored `.riftreader-local/opencode-status/<timestamp>/` folder.
