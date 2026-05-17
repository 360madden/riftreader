# Compact handoff — optional OpenCode bridge for non-Codex workflow

Generated UTC: `2026-05-16T18:55:00Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Implemented an opt-in, offline-safe OpenCode bridge so local OpenCode can serve
desktop ChatGPT when Codex is unavailable. The bridge is documentation-first and
status-helper-first: OpenCode can collect local truth, run validation, and
summarize/apply approved packages, while desktop ChatGPT remains the
planner/reviewer. No live RIFT input, movement, CE, x64dbg attach, provider
writes, staging, commit, or push were performed.

## Current live/proof status

| Field | Value |
|---|---|
| Current proof | `blocked-target-drift` |
| Live RIFT process | Not running / `live-target-not-running:rift_x64` |
| Movement allowed | `false` |
| Historical stale target | PID `27552` / HWND `0x3411E2` |
| Historical stale address | `0x27B1ED850C0` |
| Reuse policy | Historical reacquisition/static-chain hint only; never current movement truth |

## Implemented files

| Path | Purpose |
|---|---|
| `.opencode/opencode.example.jsonc` | Secret-free optional OpenCode project config template with bounded agents. |
| `docs/workflow/opencode-non-codex-bridge.md` | Operator guide, safety defaults, role split, and reusable OpenCode prompts. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Updated with the optional OpenCode bridge sequence. |
| `tools/riftreader_workflow/status_packet.py` | Deterministic status packet helper; no OpenCode required. |
| `tools/riftreader_workflow/__init__.py` | Workflow helper package marker. |
| `scripts/riftreader-workflow-status.cmd` | Thin launcher for the deterministic status helper. |
| `scripts/riftreader-opencode-sitrep.cmd` | Thin optional OpenCode one-shot SITREP launcher. |
| `scripts/test_opencode_status_packet.py` | Targeted tests for handoff selection, stale proof parsing, blockers, command envelopes, and ignored output paths. |
| `.gitignore` | Ignores local OpenCode overrides/secrets/sessions. |

## Public commands

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-workflow-status.cmd
.\scripts\riftreader-workflow-status.cmd --json
.\scripts\riftreader-workflow-status.cmd --write
.\scripts\riftreader-opencode-sitrep.cmd
```

Expected offline status while RIFT is not running: exit code `2` with status
`blocked`, blocker `coordinate-status:live-target-not-running:rift_x64`, and all
safety mutation/input/debugger flags `false`.

## Validation performed

| Check | Result |
|---|---|
| `python -m compileall tools\riftreader_workflow scripts` | Passed; traversed existing ignored captures/sessions too. |
| `python -m unittest scripts.test_opencode_status_packet` | Passed, 5 tests. |
| `PYTHONPATH=...\scripts;...\reader python -m unittest scripts.test_opencode_status_packet scripts.test_coordinate_recovery_status scripts.test_current_proof_pointer scripts.test_validate_current_truth` | Passed, 13 tests. |
| `python .\tools\riftreader_workflow\status_packet.py --json --skip-opencode-check --commits 3 --refs 3` | Expected blocked exit `2`; parsed `blocked` and `no-live-process`. |
| `.\scripts\riftreader-workflow-status.cmd --json --skip-opencode-check --commits 3 --refs 3` | Expected blocked exit `2`; produced compact JSON. |
| `python .\tools\riftreader_workflow\status_packet.py --write --skip-opencode-check --commits 3 --refs 3` | Expected blocked exit `2`; wrote ignored `.riftreader-local\opencode-status\...` artifacts. |
| `python .\scripts\validate_current_truth.py --json` | Passed, `artifactCount=51`. |
| `python .\scripts\coordinate_recovery_status.py --json` | Expected blocked exit `2`, `live-target-not-running:rift_x64`. |
| `opencode --version` | Passed, `1.4.3`. |
| Secret/config smoke for new OpenCode template | No credential value detected; JSONC stripped-comment parse passed. |
| `git --no-pager diff --check` | Passed; line-ending warnings only. |

## Notes for resume

- The OpenCode bridge is optional and offline-safe.
- The deterministic status helper should be the default first local command for
  desktop ChatGPT fallback sessions.
- `opencode mcp list` was intentionally not made part of validation because MCP
  startup can hang or depend on external tools.
- The existing current-proof blocker remains correct; this work did not attempt
  current-PID recovery because RIFT is offline.

## Next recommended actions

| # | Action | Why |
|---:|---|---|
| 1 | Review the OpenCode example config before copying it to a live local config. | Keeps provider credentials and permissions explicit. |
| 2 | Run `scripts\riftreader-workflow-status.cmd --write` when desktop ChatGPT needs local truth. | Produces compact pasteable state. |
| 3 | When RIFT is back in-world, use only the no-input live observer prompt first. | Preserves movement/proof safety gates. |
| 4 | Keep commits/pushes explicit-path and user-approved. | Maintains the non-Codex workflow invariant. |
