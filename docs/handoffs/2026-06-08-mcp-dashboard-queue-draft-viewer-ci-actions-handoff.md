# 2026-06-08 — MCP dashboard readiness summary, queue draft viewer, and CI action refresh

## Current truth

| Item | Status |
|---|---|
| Computer Use | Still blocked at setup with `Computer Use native pipe path is unavailable`; fresh ignored observation: `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\20260608-152808Z\observation.json`. |
| Dashboard summary | The localhost-only MCP dashboard now exposes a `Readiness Summary` card that separates repo final gate, Browser Use, Computer Use, and queue-execution state. |
| Queue draft viewer | The inert Desktop Queue Contract now includes `queueDraftViewer`, a read-only JSON draft viewer under `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-queue-drafts`. |
| Queue draft schema | Draft validation requires `dryRunOnly=true`, `requiresHumanApproval=true`, allowed pre-readiness action keys only, and rejects forbidden action families such as desktop clicks, typing, window activation, RIFT input, package apply, Git mutation, provider writes, CE, and x64dbg. |
| ChatGPT window discovery | The contract now includes `chatGptWindowDiscovery` as a future no-input, evidence-only action blocked until Computer Use bootstrap/list-apps readiness passes. |
| Status JSON fallback | Dashboard UI includes a read-only `Status JSON` card linking `/status.json` while preserving the embedded-status fallback for Browser Use clients that cannot navigate directly to JSON. |
| CI action versions | GitHub Actions were updated to Node 24-compatible major versions: `actions/checkout@v6`, `actions/setup-dotnet@v5`, and `actions/setup-python@v6`. |
| Safety | Still no queue writer, executor, MCP tool expansion, Browser/Computer automation, command execution, desktop input, RIFT input, tunnel start, package apply, Git endpoint, provider write, CE, or x64dbg endpoint. |

## Validation

Passed locally before commit:

- `python -m py_compile tools\riftreader_workflow\desktop_control_queue_contract.py tools\riftreader_workflow\mcp_dashboard.py tools\riftreader_workflow\desktop_control_readiness.py`
- `python -m unittest scripts.test_desktop_control_queue_contract scripts.test_mcp_dashboard scripts.test_operator_lite scripts.test_desktop_control_readiness` passed 71 tests.
- `scripts\riftreader-desktop-control-queue-contract.cmd --self-test --json` wrote `.riftreader-local\desktop-control-queue-contract.self-test.viewer.json` and passed.
- `scripts\riftreader-mcp-dashboard.cmd --self-test --json` wrote `.riftreader-local\mcp-dashboard.self-test.queue-viewer.json` and passed.
- `scripts\riftreader-mcp-dashboard.cmd --once-json --no-public-smoke` wrote `.riftreader-local\mcp-dashboard.once.queue-viewer.json`; expected exit `2` because final readiness is currently blocked by upstream/current-head CI state and stale local trial/proposal smoke artifacts, but payload showed four readiness badges, `queueDraftViewer.status=ready`, `draftWriteEndpoint=false`, `chatGptWindowDiscovery.status=blocked`, and `safety.statusJsonEndpoint=/status.json`.
- Browser Use localhost smoke against `http://127.0.0.1:8788/` verified visible `Readiness Summary`, `Desktop Queue Draft Viewer`, `Status JSON`, `chatgpt-window-discovery-no-input`, `computer-use-native-pipe-not-confirmed`, four readiness badges, disabled queue execution, and no draft write endpoint.
- `git --no-pager diff --check`
- `pre-commit run --files .github/workflows/dotnet.yml .github/workflows/riftreader-policy.yml docs/HANDOFF.md docs/handoffs/2026-06-08-mcp-dashboard-queue-draft-viewer-ci-actions-handoff.md docs/workflow/riftreader-chatgpt-mcp.md scripts/test_desktop_control_queue_contract.py scripts/test_mcp_dashboard.py tools/riftreader_workflow/desktop_control_queue_contract.py tools/riftreader_workflow/mcp_dashboard.py --show-diff-on-failure`

## Next action

Repair/reconnect the Codex Computer Use plugin/runtime outside the repo, then prove bootstrap/list-apps only and record a success observation. Do not design or enable any executor until readiness passes and a separate reviewed implementation plan is approved.
