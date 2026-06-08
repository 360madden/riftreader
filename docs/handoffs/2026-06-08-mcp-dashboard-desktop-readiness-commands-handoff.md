# 2026-06-08 — MCP dashboard Desktop Readiness Commands card

## Current truth

| Item | Status |
|---|---|
| Dashboard JSON | `scripts\riftreader-mcp-dashboard.cmd --once-json --no-public-smoke` now includes `desktopControlCommands`. |
| Dashboard UI | The localhost-only dashboard renders a `Desktop Readiness Commands` card with copy-ready blocked/success observation commands from the Computer Use repair guide. |
| Command scope | Operator-copy-only: the dashboard displays commands but does not execute them. |
| Queue safety | The dashboard self-test now fails closed if the Desktop Queue Contract grows an enabled executor, exposed MCP tool, execution endpoint, or queue-write endpoint. |
| Server polish | Dashboard writes tolerate client disconnects and Ctrl+C prints a clean stopped message instead of a Python traceback. |
| Current external blocker | Computer Use still fails at setup with `Computer Use native pipe path is unavailable`; latest ignored observation: `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\20260608-114715Z\observation.json`. |
| Safety | Visibility only: no queue writer, executor, MCP tool, Browser/Computer automation, desktop click, typing, window activation, RIFT input, tunnel start, package apply, Git mutation, CE, or x64dbg endpoint. |

## Validation

Passed locally before commit:

- `python -m py_compile tools\riftreader_workflow\mcp_dashboard.py tools\riftreader_workflow\desktop_control_queue_contract.py tools\riftreader_workflow\desktop_control_readiness.py`
- `python -m unittest scripts.test_mcp_dashboard scripts.test_desktop_control_queue_contract scripts.test_operator_lite scripts.test_desktop_control_readiness`
- `scripts\riftreader-mcp-dashboard.cmd --self-test --json` wrote `.riftreader-local\mcp-dashboard.self-test.readiness-commands.json` and passed.
- `scripts\riftreader-mcp-dashboard.cmd --once-json --no-public-smoke` wrote `.riftreader-local\mcp-dashboard.once.readiness-commands.json`; expected exit `2` because the current dashboard status is still blocked, but payload showed `desktopControlCommands.status=ready`, record-success command contains `--computer-use-native-pipe-ok`, record-blocked command contains `Computer Use native pipe path is unavailable`, `copyOnly=true`, `executionEndpoint=false`, and `desktopControlQueue.execution.status=disabled`.
- Browser Use localhost smoke against `http://127.0.0.1:8788/` verified the visible `Desktop Readiness Commands` card, success/native-pipe argument, blocked-error text, copy-only warning, and disabled queue execution.
- Manual Ctrl+C server stop printed `RiftReader MCP dashboard stopped.` without a Python traceback.
- `git --no-pager diff --check`
- `pre-commit run --files docs/HANDOFF.md docs/handoffs/2026-06-08-mcp-dashboard-desktop-readiness-commands-handoff.md docs/workflow/riftreader-chatgpt-mcp.md scripts/test_mcp_dashboard.py tools/riftreader_workflow/mcp_dashboard.py --show-diff-on-failure`

## Next action

Repair/reconnect the Codex Computer Use plugin/runtime outside the repo, prove only bootstrap/list-apps, and record the success observation with the displayed command before any future queue-draft or executor design.
