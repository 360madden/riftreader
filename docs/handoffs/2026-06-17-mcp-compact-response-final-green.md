# 2026-06-17 - MCP compact response final-green baseline

## Current truth

| Item | Evidence |
|---|---|
| Scope | Durable status handoff for the compact direct MCP response slice. No live RIFT input, movement, CE, x64dbg, proof promotion, provider writes, branch rewrite, reset, or cleanup was performed. |
| Baseline commit | `a5bff4d21437a85fb23f7ad4252cad11c47f96f2` (`Compact MCP direct status responses`) is pushed to `origin/main`. |
| CI | Current head passed `.NET build and test` run `27723546997` and `RiftReader Policy` run `27723547005`. |
| HTTP MCP runtime | `python tools\riftreader_workflow\mcp_server_status.py --json` reports `running-current`, PID `108940`, full profile, source-fresh, and 33/33 observed tools. |
| Stdio counterpart | The stale Codex stdio counterpart was exact-command-line matched and stopped; current local status reports `stdioCounterparts.status=not-running`. This Codex thread's `mcp__riftreader` transport remains closed and needs reconnect/reload before in-thread MCP tool calls work again. |
| Direct compact responses | Local current-source direct calls passed with no blockers: `get_final_readiness_status` minified size `5331` bytes and `get_tool_surface_diff` minified size `3854` bytes, both under the `8192` byte target. |
| Final readiness | `python tools\riftreader_workflow\bounded_repo_commands.py --run mcp_final_status --json` passed at `2026-06-17T22:37:40Z`; latest summary path: `.riftreader-local\riftreader-chatgpt-mcp\bounded-commands\20260617-223740Z-mcp_final_status\run-summary.json`. |
| Actual-client proof | `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_actual_client_proof_status --json` passed; proof path `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260617-194828Z\proof.json`, 33 tools, output schemas present, `clientTransportStatus=tool-call-succeeded`, `healthCallSucceeded=true`. |
| Public route | Active non-Codex route remains `https://mcp.360madden.com/mcp` through the Cloudflare named Tunnel to `http://127.0.0.1:8770/mcp`; saved ChatGPT connector config does not start the local runtime or Cloudflared. |
| Public-session warnings | Old Cloudflare/trial-session artifacts are expected-expired warnings only; they are not final-readiness blockers in this green baseline. |
| RIFT target discovery | `scripts\get-rift-window-targets.cmd -Json` is read-only and currently finds `rift_x64` count `0`; no focus, click, key, debugger, or target-control action was sent. |

## Validation and error checks

| Command | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_riftreader_chatgpt_mcp.py` | Passed. |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp` | Passed: 90 tests. |
| `git --no-pager diff --check` | Passed. |
| `python tools\riftreader_workflow\mcp_ci_status.py --status --json` | Passed for current head `a5bff4d21437a85fb23f7ad4252cad11c47f96f2`. |
| `python tools\riftreader_workflow\mcp_server_status.py --json` | Passed: HTTP MCP runtime current, 33/33, source-fresh. |
| `python tools\riftreader_workflow\bounded_repo_commands.py --run mcp_final_status --json` | Passed: final readiness green, no blockers. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_actual_client_proof_status --json` | Passed: actual-client proof replay fresh and consistent. |
| `scripts\get-rift-window-targets.cmd -Json` | Passed read-only; `count=0`. |
| `git status --short --ignored=matching .riftreader-local` | Confirmed ignored local evidence only (`!! .riftreader-local/`). |

## Operational notes

- Use `START_RIFTREADER_CHATGPT_MCP.cmd` for the operator-owned local HTTP MCP runtime; do not assume the saved ChatGPT connector starts it.
- Use `scripts\riftreader-mcp-final.cmd --status --compact-json` as the release/readiness gate before demos or releases.
- If in-thread `mcp__riftreader` tools are needed from Codex, reconnect/reload the stdio connector first; the HTTP MCP runtime itself is healthy.
- Do not promote proof/actor chains or start live Stage 38 work from this status handoff. Live target, movement, proof-promotion, CE/x64dbg, and provider-write gates remain separate.

## Recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Reconnect/reload Codex's stdio `mcp__riftreader` connector only if in-thread MCP tools are needed. | The stale counterpart was stopped and the current thread transport is closed. |
| 2 | Keep HTTP MCP PID `108940` running unless source changes require another exact-PID restart. | It is current-source, 33/33, and final-readiness compatible. |
| 3 | Rerun `scripts\riftreader-mcp-final.cmd --status --compact-json` before any release/demo. | Proof/artifact freshness is time-budgeted. |
| 4 | Treat old Cloudflare/trial-session artifacts as expected-expired unless public-session proof is explicitly required. | They are warnings only in the green final gate. |
| 5 | If direct MCP timeout recurs after connector reload, compare stdio vs HTTP response sizes before changing code. | Current local direct responses are compact and below target. |
| 6 | If returning to proof recovery, start with `scripts\get-rift-window-targets.cmd -Json`. | Current read-only target discovery finds no `rift_x64` windows. |
| 7 | Do not run movement/proof promotion until a live target exists and the relevant gate is explicit. | Prevents unsafe proof claims. |
| 8 | Leave `.riftreader-local` evidence ignored. | It is runtime/proof evidence, not source. |
| 9 | Preserve `a5bff4d` as the current compact-response baseline. | It is pushed, CI-green, and final-readiness-green. |
| 10 | Continue running validation immediately after any code change. | Maintains the current green baseline. |
