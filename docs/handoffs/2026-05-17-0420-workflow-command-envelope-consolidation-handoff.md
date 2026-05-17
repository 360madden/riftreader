# Compact handoff — Workflow command-envelope consolidation

Generated UTC: `2026-05-17T08:20:00Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Continued Phase E consolidation after the first common-utility slice. The
generic command-envelope runner now lives in `tools/riftreader_workflow/common.py`.
`status_packet.run_command()` remains as the compatibility wrapper, and
`apply_package.py` no longer imports command execution/root discovery from
`status_packet.py`.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/common.py` | Added `run_command_envelope()` for bounded subprocess checks with expected exit codes and stdout/stderr previews. |
| `tools/riftreader_workflow/status_packet.py` | Keeps public `run_command()` wrapper while delegating to the common command-envelope runner. |
| `tools/riftreader_workflow/apply_package.py` | Imports `find_repo_root` and command envelope execution from common instead of `status_packet.py`. |
| `scripts/test_workflow_common.py` | Adds command-envelope coverage. |
| `docs/workflow/workflow-helper-common.md` | Documents the command-envelope primitive. |
| `docs/workflow/RIFTREADER_WORKFLOW_CONTROL_PLANE_PLAN.md` | Updates Phase E status wording. |

## Safety

Still offline-only. This does not add any new executable authority: no movement,
input, CE/x64dbg, provider writes, staging, committing, pushing, or live proof
work.

## Validation

Expected checks:

```powershell
python -m compileall tools\riftreader_workflow scripts\test_workflow_common.py scripts\test_operator_lite.py scripts\test_live_test_triage.py scripts\test_package_intake.py scripts\test_opencode_status_packet.py
python -m unittest scripts.test_workflow_common scripts.test_operator_lite scripts.test_live_test_triage scripts.test_package_intake scripts.test_opencode_status_packet
.\scripts\riftreader-operator-lite.cmd --self-test --json
.\scripts\riftreader-live-triage.cmd --json
python .\scripts\coordinate_recovery_status.py --json
python .\scripts\validate_current_truth.py --json
python .\scripts\riftscan_milestone_review.py --compact-json
git --no-pager diff --check
```

Expected RIFT-offline blocker exits remain safe: live triage and coordinate
status exit `2`; RiftScan milestone review may exit `2` until there is a current
selected candidate.

## Resume point

Next safe Phase E slice: extract artifact rendering/writing helpers only if it
removes duplication without changing output contracts.
