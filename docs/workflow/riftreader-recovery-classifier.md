<!--
Version: riftreader-recovery-classifier-docs-v0.1.0
Purpose: Operator documentation for the RiftReader recovery classifier.
-->

# RiftReader Recovery Classifier v0.1

## Purpose

Read existing workflow artifacts and output one project-manager style recovery board.

The classifier does not run movement, debugger attach, proof promotion, current-truth writes, or git mutation.

## Command

```powershell
.\scripts\riftreader-recovery-classifier.cmd --write --json
```

Python-direct equivalent:

```powershell
python -m tools.riftreader_workflow.recovery_classifier --write --json
```

## Output

The classifier writes:

```text
.riftreader-local/recovery-classifier/<timestamp>/summary.json
.riftreader-local/recovery-classifier/<timestamp>/summary.md
.riftreader-local/recovery-classifier/latest/summary.json
.riftreader-local/recovery-classifier/latest/summary.md
```

## Classifications

```text
status-refresh-needed
proof-reacquire-needed
static-chain-repair-needed
stale-dashboard-or-current-truth
ready-or-review-needed
manual-review-needed
```

## Safety

Read-only classification only.

## END_OF_SCRIPT_MARKER
