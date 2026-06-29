# Unified Operator Status

`riftreader-status` is the Stage 51 read-only operator status surface for the
RiftReader monorepo/workflow repo. It aggregates the facts normally needed at
resume time into one JSON packet without starting servers, tunnels, live RIFT
input, debugger sessions, proof promotion, provider writes, or Git mutation.

## Command

```cmd
scripts\riftreader-status.cmd --json
```

The launcher is intentionally thin and delegates to Python:

```cmd
python -m tools.riftreader_workflow.operator_status --json
```

Use `--write` only when you want ignored local evidence under
`.riftreader-local\operator-status\`:

```cmd
scripts\riftreader-status.cmd --json --write
```

## Included status areas

| Area | Source |
|---|---|
| Git branch/upstream/ahead-behind/dirty/HEAD | Read-only `git` inspection |
| Handoff pointer and newest tracked handoff | `docs\HANDOFF.md` and `docs\handoffs\*.md` |
| MCP HTTP runtime and stdio counterparts | Existing `mcp_server_status` Python helper |
| Final readiness | Existing final-readiness compact gate |
| Trial readiness/proposal smoke/proof freshness | Existing MCP workflow artifact discovery |
| RIFT target count | Python-native `psutil` + `win32gui` read-only enumeration |
| Decision packet lane/safe next action | Existing decision packet builder |
| Next actions | Ordered summary from final readiness, runtime, decision packet, and target state |

## Safety contract

The status command is read-only. It does not:

- start the MCP server or Cloudflare tunnel,
- register or mutate ChatGPT connector state,
- send RIFT input, movement, focus, clicks, or key presses,
- attach x64dbg or Cheat Engine,
- promote proof/current-truth/actor chains,
- write provider repositories,
- stage, commit, push, reset, or rewrite Git history.

`--write` writes only ignored local summaries under `.riftreader-local`.

## Interpreting output

`status` describes whether the status packet was collected. `overallState`
describes whether the repo/runtime/release path is ready. A blocked final gate
or missing runtime should therefore still produce `status=passed` with
`overallState=blocked` and an ordered `recommendedActions` list.

## Validation

Focused validation for this surface:

```cmd
python -m py_compile tools\riftreader_workflow\operator_status.py
python -m unittest scripts.test_operator_status
scripts\riftreader-status.cmd --json
```

# END_OF_SCRIPT_MARKER
