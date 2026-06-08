# 2026-06-08 — MCP dashboard Desktop Queue Contract card

## Current truth

| Item | Status |
|---|---|
| Dashboard JSON | `scripts\riftreader-mcp-dashboard.cmd --once-json --no-public-smoke` now includes `desktopControlQueue`. |
| Dashboard UI | The localhost-only dashboard now renders a `Desktop Queue Contract` card next to Browser/Computer readiness. |
| Execution state | The card surfaces `execution.status=disabled`, required future executor gates, and forbidden action families. |
| Current external blocker | Computer Use still fails at setup with `Computer Use native pipe path is unavailable`; latest ignored observation: `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\20260608-113208Z\observation.json`. |
| Safety | Visibility only: no queue writer, executor, MCP tool, Browser/Computer automation, desktop input, RIFT input, tunnel start, package apply, Git mutation, CE, or x64dbg endpoint. |

## Validation

Passed locally before commit:

- `python -m py_compile tools\riftreader_workflow\mcp_dashboard.py tools\riftreader_workflow\desktop_control_queue_contract.py tools\riftreader_workflow\desktop_control_readiness.py`
- `python -m unittest scripts.test_mcp_dashboard scripts.test_desktop_control_queue_contract scripts.test_operator_lite scripts.test_desktop_control_readiness`
- `scripts\riftreader-mcp-dashboard.cmd --self-test --json`
- `scripts\riftreader-mcp-dashboard.cmd --once-json --no-public-smoke` produced expected blocked status while the dashboard patch was still uncommitted; payload included `desktopControlQueue.execution.status=disabled`.
- Browser Use localhost smoke against `http://127.0.0.1:8788/` verified the visible `Desktop Queue Contract` card, `execution.status=disabled`, and forbidden `rift-movement` family. Direct Browser Use navigation to `/status.json` remained blocked by the browser client, so verification used the dashboard's embedded/live rendered status.
- `git --no-pager diff --check`
- `pre-commit run --files docs/HANDOFF.md docs/handoffs/2026-06-08-mcp-dashboard-desktop-queue-contract-card-handoff.md docs/workflow/riftreader-chatgpt-mcp.md scripts/test_mcp_dashboard.py tools/riftreader_workflow/mcp_dashboard.py --show-diff-on-failure`

## Next action

Repair/reconnect the Codex Computer Use plugin/runtime outside the repo, prove only bootstrap/list-apps, and record a success observation before any future queue-draft or executor design.
