# Compact handoff — Operator Lite v0

Generated UTC: `2026-05-17T04:35:00Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Added Operator Lite v0 as an offline-safe local launcher around the workflow
control-plane helpers. It exposes Workflow Status, Live-Test Triage, Package
Intake dry-run, Git Status, and Open Latest Report. It disables target-control,
visual gate, ProofOnly, movement, CE/x64dbg, staging, committing, and pushing.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/operator_lite.py` | Tkinter launcher plus headless command-plan/self-test. |
| `scripts/riftreader-operator-lite.cmd` | Thin launcher. |
| `scripts/test_operator_lite.py` | Tests command plan, denied fragments, package dry-run args, latest report discovery, and JSON serialization. |
| `docs/workflow/operator-lite.md` | Operator guide and safety contract. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Updated with Operator Lite usage. |
| `docs/workflow/opencode-non-codex-bridge.md` | Updated with Operator Lite references. |
| `.opencode/opencode.example.jsonc` | Updated with self-test permission entry. |

## Public commands

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-operator-lite.cmd
.\scripts\riftreader-operator-lite.cmd --self-test --json
```

## Expected validation

| Check | Expected |
|---|---|
| `python -m unittest scripts.test_operator_lite scripts.test_live_test_triage scripts.test_package_intake scripts.test_opencode_status_packet` | Pass |
| `python -m compileall tools\riftreader_workflow scripts\test_operator_lite.py` | Pass |
| `.\scripts\riftreader-operator-lite.cmd --self-test --json` | `status=passed` |
| `git --no-pager diff --check` | Pass |

## Safety

No live input, movement, CE/x64dbg attach, provider writes, staging, commit, or
push are part of Operator Lite v0.
