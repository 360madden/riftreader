# 2026-06-14 - MCP proposal transport timeout fixed locally

## Current lane

MCP / local repo automation maintenance lane. This is not a live RIFT, desktop-input, CE, x64dbg, or provider-write lane.

## Local result

| Item | Current truth |
|---|---|
| Base HEAD | `698f819 Expose tracked repo context MCP tools`. |
| Problem | `--proposal-transport-smoke` and Operator Lite `--mcp-trial-readiness` could report `MCP_TRANSPORT_CLIENT_TIMEOUT` after the 19-tool surface landed. |
| Root cause | The transport client still used deprecated `streamablehttp_client(..., timeout=5, sse_read_timeout=10)` while the synthetic package dry-run can legitimately exceed 10 seconds. |
| Fix | The smoke client now uses the current MCP SDK `streamable_http_client` with an explicit `httpx.AsyncClient` and a read timeout aligned with the smoke timeout budget. |
| Diagnostics | Transport client responses now include `clientStepTimings`, `transportClientApi`, and `clientReadTimeoutSeconds`; timeout failures preserve `lastClientStage` and step timings. |
| Stale wording | Proposal-smoke full-profile error text no longer says `12-tool profile`. |
| Scope | Local loopback smoke/readiness only; no public tunnel, ChatGPT registration, Git push, live RIFT input, CE, x64dbg, or provider writes. |

## Files changed by this slice

- `tools/riftreader_workflow/riftreader_chatgpt_mcp.py`
- `scripts/test_riftreader_chatgpt_mcp.py`
- `docs/HANDOFF.md`
- `docs/handoffs/2026-06-14-mcp-transport-timeout-readiness-handoff.md`

## Validation evidence

| Check | Result |
|---|---|
| py_compile | Passed: `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_riftreader_chatgpt_mcp.py`. |
| Focused MCP unit tests | Passed: `python -m unittest scripts.test_riftreader_chatgpt_mcp` (`73 tests`, `4.369s`). |
| SDK registration | Passed: `scripts\riftreader-chatgpt-mcp.cmd --validate-sdk --json`; registered 19 tools. |
| Basic transport smoke | Passed: `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260614T094934Z-transport-smoke.json`. |
| Proposal transport smoke | Passed: `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260614T094942Z-proposal-transport-smoke.json`. |
| Operator Lite trial readiness | Passed: `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260614T095002Z-trial-readiness.json`. |
| Final readiness compact status | Still blocked as expected due dirty worktree, branch ahead 1, missing current-head CI, and stale 14-tool actual-client proof. |

## Remaining blockers / gates

| Gate | State |
|---|---|
| Worktree | Dirty. This MCP slice owns only the files listed above. Current unrelated dirty C# reader/scan-region files must be reviewed separately before any broad commit. |
| Actual ChatGPT proof | Stale 14-tool proof still fails against the 19-tool surface; refresh actual-client proof before claiming final readiness. |
| CI | Missing for local `HEAD` because branch is ahead of origin and not pushed. |
| Git push | Not authorized by this handoff. |
| Live RIFT / movement / desktop input | Not authorized by this handoff. |
| CE / x64dbg | Not authorized by this handoff. |
| Provider writes | Not authorized by this handoff. |

## Exact next action

Commit the MCP transport-timeout slice with explicit paths only after final targeted validation/pre-commit. Do not include unrelated reader C# changes in this commit unless separately reviewed and approved.

```cmd
python -m unittest scripts.test_riftreader_chatgpt_mcp
scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
git add -- tools/riftreader_workflow/riftreader_chatgpt_mcp.py scripts/test_riftreader_chatgpt_mcp.py docs/HANDOFF.md docs/handoffs/2026-06-14-mcp-transport-timeout-readiness-handoff.md
git commit -m "Fix MCP proposal transport timeout"
```
