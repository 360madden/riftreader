# 2026-06-08 — Operator Lite Computer Use repair-guide action

## Current truth

| Item | Current truth |
|---|---|
| New Operator Lite command | `desktop-control-repair-guide` |
| New shortcut | `scripts\riftreader-operator-lite.cmd --desktop-control-repair-guide --json` |
| Backing helper | `scripts\riftreader-desktop-control-readiness.cmd --repair-guide --json` |
| GUI surface | MCP & Proof tab now includes a `Computer Use Repair Guide` button. |
| Computer Use status | Still blocked-safe at setup with `Computer Use native pipe path is unavailable`. |
| Fresh observation | `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\20260608-110501Z\observation.json` |
| MCP route | `cloudflare-named-tunnel`; Caddy/router remains deprecated and diagnostic-only. |

## Safety

This slice only exposes the existing guide-only repair payload through Operator Lite.
It does not automate Browser Use, Computer Use, desktop UI, RIFT input, movement,
tunnels, package apply, Git mutation, provider writes, CE, or x64dbg.

## Validation plan

- `python -m py_compile tools\riftreader_workflow\operator_lite.py tools\riftreader_workflow\desktop_control_readiness.py tools\riftreader_workflow\mcp_dashboard.py`
- `python -m unittest scripts.test_operator_lite scripts.test_desktop_control_readiness scripts.test_mcp_dashboard`
- `scripts\riftreader-operator-lite.cmd --self-test --json`
- `scripts\riftreader-operator-lite.cmd --desktop-control-repair-guide --json` expected exit `2`
- `git diff --check`
- pre-commit on explicit changed paths
