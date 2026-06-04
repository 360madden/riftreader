<!--
Version: riftreader-operator-status-publisher-docs-v0.1.0
Purpose: Publish operator status to a GitHub transport branch.
-->

# RiftReader Operator Status Publisher v0.1

## Purpose

Publish the latest operator status board to a dedicated GitHub transport branch so ChatGPT can inspect it without manual paste.

## Command

```powershell
python -m tools.riftreader_workflow.operator_status_publisher --run-status --push --json
```

## Branch

Default branch: `chatgpt/operator-status`

Files written there:

```text
handoffs/current/RIFTREADER_OPERATOR_STATUS.md
handoffs/current/RIFTREADER_OPERATOR_STATUS.json
```

## Safety

Does not mutate `main`. Uses a temporary worktree and force-with-lease pushes only the two allowlisted snapshot files to the transport branch.

No movement, input, target memory access, CE, x64dbg, proof promotion, or current-truth write.

## END_OF_SCRIPT_MARKER
