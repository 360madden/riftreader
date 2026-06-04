<!--
Version: riftreader-operator-status-docs-v0.1.0
Purpose: Document the one-command operator status runner.
-->

# RiftReader Operator Status v0.1

## Purpose

One command to refresh compact workflow status, run recovery classifier, and write a project-manager board.

## Command

```powershell
python -m tools.riftreader_workflow.operator_status --write --json
```

Thin wrapper:

```powershell
.\scripts\riftreader-operator-status.cmd --write --json
```

## Output

```text
.riftreader-local/operator-status/<timestamp>/summary.json
.riftreader-local/operator-status/<timestamp>/summary.md
.riftreader-local/operator-status/latest/summary.json
.riftreader-local/operator-status/latest/summary.md
```

## Safety

Status/classification only. No movement, input, target memory read/write, CE, x64dbg, proof promotion, current-truth write, commit, or push.

## END_OF_SCRIPT_MARKER
