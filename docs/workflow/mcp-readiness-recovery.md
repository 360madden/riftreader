# MCP Readiness Recovery Plan

`riftreader-mcp-recovery-plan` is the Stage 52 guided recovery checklist for
the non-Codex ChatGPT Web/Desktop MCP lane. It consumes the unified operator
status packet and turns runtime, proof, freshness, CI, and deferred
proof-recovery signals into ordered next steps.

## Command

```cmd
scripts\riftreader-mcp-recovery-plan.cmd --json
```

The launcher is intentionally thin:

```cmd
python -m tools.riftreader_workflow.mcp_recovery_plan --json
```

Use `--write` to save ignored local evidence under
`.riftreader-local\riftreader-chatgpt-mcp\recovery-plan\`.

## What it plans

| Signal | Planned recovery |
|---|---|
| `git:dirty-worktree` | Review explicit safe commit plan. |
| `phase2:not-ready` or `ci:not-completed:*` | Wait for current-head CI, then rerun final readiness. |
| `artifact:trial-readiness-stale` | Run local MCP trial readiness. |
| `artifact:proposal-smoke-stale` | Refresh proposal/package smoke via trial readiness. |
| no HTTP listener / no full runtime | Start the full HTTP runtime manually, then verify server status. |
| tool surface mismatch | Verify the MCP server status/tool surface. |
| `proof:stale` | Write/check/fill/record a fresh actual-client proof packet. |
| no RIFT target / proof-recovery blocker | Mark as deferred proof-recovery lane, not a release-local code blocker. |

## Safety contract

The plan helper is read-only. It does not start the MCP runtime, start a public
tunnel, register ChatGPT, send RIFT input, attach x64dbg/Cheat Engine, promote
proof/current truth, write provider repos, or mutate Git.

Steps that would start runtime or require actual ChatGPT observations are
marked as operator steps. They are recommendations only until invoked
explicitly by the operator.

## Validation

```cmd
python -m py_compile tools\riftreader_workflow\mcp_recovery_plan.py
python -m unittest scripts.test_mcp_recovery_plan
scripts\riftreader-mcp-recovery-plan.cmd --json
```

# END_OF_SCRIPT_MARKER
