# 2026-06-08 — MCP dashboard Browser Use hydration and route-context note

## Current truth

| Item | Current truth |
|---|---|
| Browser Use dashboard smoke | The Browser plugin can open `http://127.0.0.1:8788/` and now renders the dashboard cards from embedded initial status before live `/status.json` refresh. |
| Root cause fixed | The dashboard previously depended only on client-side `/status.json`; when that path was blocked or unavailable to Browser Use, the page stayed as a static shell. |
| Route context | Dashboard status now exposes `activeRoute.key=cloudflare-named-tunnel` and `legacyCaddyRouterDeprecated=true`. |
| Caddy output | `tcp443Owner` may still show `caddy.exe`, but it is now explicitly marked `tcp443OwnerDiagnosticOnly=true`; it is not the active MCP route. |
| Remaining blocker | Computer Use still fails before `list_apps` with `Computer Use native pipe path is unavailable`. |
| Fresh observation | `.riftreader-local\riftreader-chatgpt-mcp\desktop-control-readiness\20260608-105309Z\observation.json` records Browser OK and Computer Use blocked. |

## Safety

No shell endpoint, arbitrary filesystem endpoint, Git mutation endpoint, RIFT input,
movement, CE, x64dbg, public tunnel start, ChatGPT registration, package apply, or
provider write was added to the dashboard. The dashboard remains localhost-only and
status-only.

## Validation

| Check | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\mcp_dashboard.py tools\riftreader_workflow\desktop_control_readiness.py tools\riftreader_workflow\operator_lite.py` | Passed |
| `python -m unittest scripts.test_mcp_dashboard scripts.test_desktop_control_readiness scripts.test_operator_lite` | Passed, 65 tests |
| `scripts\riftreader-mcp-dashboard.cmd --self-test --json` | Passed |
| `scripts\riftreader-mcp-dashboard.cmd --once-json --no-public-smoke` | Expected exit `2` while the tracked dashboard patch is uncommitted; output includes the new route-context fields |
| Browser Use dashboard smoke | Passed for rendered dashboard cards; Computer Use card correctly remains blocked |

## Next actions

1. Commit and push the dashboard compatibility slice.
2. Re-run final readiness after the worktree is clean.
3. Repair/reconnect the Codex Desktop Computer Use runtime, then rerun only bootstrap + `list_apps`.
