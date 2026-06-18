# ChatGPT MCP Stage 49 dashboard/recovery complete-local

Date: 2026-06-18

## Verdict

Stage 49 is complete-local. The existing localhost-only MCP dashboard now
surfaces the Stage 48 eval-suite checklist as operator recovery context without
adding MCP tools or control endpoints.

## Current truth

| Item | Current truth |
|---|---|
| Stage | Stage 49: operational dashboard and recovery. |
| Tool surface | Full non-Codex ChatGPT MCP profile remains 40 tools; no new MCP tool was added. |
| Dashboard JSON | `scripts\riftreader-mcp-dashboard.cmd --once-json --no-public-smoke` now includes `evalSuite`. |
| Dashboard UI | The HTML dashboard renders an `Eval Suite` card with copy-ready eval-suite commands, latest ignored artifact path/status, proof requirements, and safety flags. |
| Readiness badge | `eval-suite` appears beside local MCP server, repo final gate, Browser Use, Computer Use, and queue execution. |
| Control plan | `get_workflow_control_plan` reports `currentStage=49`, `nextStage=50`, and `futureCapabilityPolicy.status=stage49-dashboard-recovery-complete-release-next`. |
| Safety | Status/recovery only: no server start, tunnel start, ChatGPT registration, Git mutation, remote mutation, RIFT input, movement, CE/x64dbg attach, provider write, proof promotion, auth enforcement change, or secrets. |
| Next stage | Stage 50: finished product release. |

## Files changed

| Path | Purpose |
|---|---|
| `tools/riftreader_workflow/mcp_dashboard.py` | Adds read-only `evalSuite` status and HTML `Eval Suite` card. |
| `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` | Advances product plan metadata to Stage 49 and keeps compact workflow-control payload under budget. |
| `scripts/test_mcp_dashboard.py` | Covers dashboard JSON/UI eval-suite fields and safety flags. |
| `scripts/test_riftreader_chatgpt_mcp.py` | Covers Stage49 roadmap/control-plan status. |
| `scripts/test_chatgpt_mcp_workflow_docs.py` | Locks Stage49 documentation strings. |
| `docs/workflow/riftreader-chatgpt-mcp-50-stage-plan.md` | Marks Stage49 complete-local and narrows immediate work to Stage50. |
| `docs/workflow/riftreader-chatgpt-mcp.md` | Documents the Stage49 dashboard/recovery surface. |
| `docs/workflow/riftreader-chatgpt-mcp-final-readiness.md` | Clarifies Stage49 dashboard context is not actual-client proof. |

## Validation

| Check | Result |
|---|---|
| Python syntax | `python -m py_compile ...` passed for touched Python files. |
| Targeted unit tests | `python -m unittest scripts.test_mcp_dashboard scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs` -> 107 OK. |
| Dashboard JSON eval-suite probe | Dashboard exited `2` because overall final readiness/runtime proof is still blocked, but `evalSuite` parsed and validated with stage `48`, required tools `40`, schemas `40`, and read-only safety. |
| SDK validation | `--tool-profile full` passed with 40 tools; `--tool-profile public-read-only` passed with 16 tools. |
| Broad MCP regression | 190 OK across eval suite, dashboard, live-control, debugger/CE, workflow docs, final readiness, phase/status, mission control, and Stage38 consideration tests. |
| Whitespace | `git --no-pager diff --check` passed; only CRLF normalization warnings were emitted. |

## Remaining blockers before final release

| Blocker | Why |
|---|---|
| Fresh actual ChatGPT Web/Desktop proof | Final readiness still requires current 40-tool observed proof, 40 output schemas, `clientTransportStatus=tool-call-succeeded`, and `healthCallSucceeded=true`. |
| Non-Codex runtime/client proof lane | The saved ChatGPT connector entry does not start the local MCP server; runtime must be current before actual-client proof. |
| Remote publication | Git push is a separate remote-mutation gate and was not performed in this local Stage49 slice. |
| Live/proof/debugger/provider gates | Stage49 did not open live input, proof promotion, CE/x64dbg, or provider-write gates. |

## Recommended next action

Run Stage50 readiness assessment from current local truth. If the operator wants
actual-client proof, first refresh the non-Codex MCP runtime for
`http://127.0.0.1:8770/mcp`, then record a fresh ChatGPT Web/Desktop proof
against `https://mcp.360madden.com/mcp` with No Authentication.
