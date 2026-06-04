<!--
Version: riftreader-automation-roadmap-v0.1.0
Purpose: Project-manager roadmap for RiftReader automation and recovery workflow maturity.
-->

# RiftReader Automation Roadmap v0.1

## Operating model

```text
LLM reasons.
Local PC executes deterministic work.
Repo helpers validate.
MCP transports tool calls/status.
GitHub/snapshots preserve durable evidence.
Manual paste is last resort.
```

## Current stage

| Component | Status |
|---|---|
| MCP adapter | Done |
| MCP client smoke/config | Done |
| MCP tool caller | Done |
| Recovery classifier | v0.1 |
| Recovery playbook | v0.1 |
| Orchestrated lanes | Later |

## Standard board

Every major status should expose:

| Field | Meaning |
|---|---|
| Current lane | The active recovery/work lane |
| Now | What is being worked now |
| Next | Next concrete action |
| Later | Deferred roadmap |
| Blocked by | Active blocker if any |
| Do not do | Actions explicitly forbidden in current state |

## Automation maturity ladder

1. Classify blocker state.
2. Run deterministic safe actions automatically.
3. Publish compact evidence.
4. Let LLM reason over compact artifacts.
5. Add lane automation only after repeated friction.
6. Add approval-gated live actions only after read-only lanes are stable.

## Python-first enforcement

PowerShell is only a launcher.

Python owns:

```text
JSON
parsing
workflow branching
artifact writing
validation
commit/push runners
```

## END_OF_SCRIPT_MARKER
