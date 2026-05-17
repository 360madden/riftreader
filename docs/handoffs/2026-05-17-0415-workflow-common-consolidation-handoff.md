# Compact handoff — Workflow common consolidation

Generated UTC: `2026-05-17T08:15:00Z`
Workspace: `C:\RIFT MODDING\RiftReader`
Branch: `main`

## TL;DR

Started Phase E consolidation with a small shared common module for local
workflow helpers. This removes duplicated timestamp/path/safety utility logic
without changing the safe workflow boundaries or introducing a larger operator
application.

## Implemented files

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/common.py` | Shared offline-safe primitives: UTC stamps, repo-relative paths, unique filtering, previews, repo-root discovery, output dirs, safety flags. |
| `tools/riftreader_workflow/status_packet.py` | Uses shared common primitives while preserving existing public functions. |
| `tools/riftreader_workflow/apply_package.py` | Uses shared timestamps/output dirs/path rendering/safety flags. |
| `tools/riftreader_workflow/live_test_triage.py` | Uses shared timestamps/output dirs/path rendering/safety flags. |
| `tools/riftreader_workflow/operator_lite.py` | Uses shared repo-root/timestamp/safety primitives. |
| `scripts/test_workflow_common.py` | Covers common timestamp, path, uniqueness, output-dir, and safety behavior. |
| `docs/workflow/workflow-helper-common.md` | Documents the common module contract and extension rule. |
| `docs/workflow/RIFTREADER_WORKFLOW_CONTROL_PLANE_PLAN.md` | Marks Phase E common utility slice in progress. |

## Safety

This slice is offline-only. It does not send input, move, attach CE/x64dbg,
write provider repos, stage, commit, push, or run live proof/movement helpers.

## Validation

Expected checks:

```powershell
python -m compileall tools\riftreader_workflow scripts\test_workflow_common.py scripts\test_operator_lite.py scripts\test_live_test_triage.py scripts\test_package_intake.py scripts\test_opencode_status_packet.py
python -m unittest scripts.test_workflow_common scripts.test_operator_lite scripts.test_live_test_triage scripts.test_package_intake scripts.test_opencode_status_packet
.\scripts\riftreader-operator-lite.cmd --self-test --json
.\scripts\riftreader-live-triage.cmd --json
python .\scripts\validate_current_truth.py --json
python .\scripts\riftscan_milestone_review.py --compact-json
git --no-pager diff --check
```

Expected RIFT-offline result: live triage remains blocked safely at
`live-target` / `no-live-process`; coordinate recovery exits `2` for
`live-target-not-running:rift_x64`; RiftScan milestone review may also exit `2`
while the current proof pointer has no current selected candidate. These are
safe blockers, not validation failures.

## Resume point

Next safe continuation is another small Phase E slice, such as extracting a
shared command-envelope helper or artifact writer only if it reduces duplication
without changing behavior.
