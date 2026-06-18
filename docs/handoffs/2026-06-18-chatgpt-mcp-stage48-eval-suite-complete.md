# ChatGPT MCP Stage 48 eval-suite checklist complete

Date: 2026-06-18
Branch: `main`
Base before slice: `ab63940`

## Result

Stage 48 is complete-local. The ChatGPT MCP surface remains 40 tools; no MCP
tool was added. The new deliverable is a Python-first, non-executing eval-suite
checklist generator plus a thin `.cmd` launcher.

## What changed

- Added `tools/riftreader_workflow/chatgpt_mcp_eval_suite.py`.
- Added thin launcher `scripts/riftreader-chatgpt-mcp-eval-suite.cmd`.
- Added `scripts/test_chatgpt_mcp_eval_suite.py`.
- Advanced the 50-stage current truth to Stage 48 complete-local and Stage 49
  next.
- Updated workflow, final-readiness, live-control, debugger/CE docs, and root
  handoff pointer.

## Eval coverage

The helper emits:

- local commands for focused MCP tests, broader MCP regression, SDK validation
  for `full` and `public-read-only`, and `git diff --check`;
- denial-path expectations for apply, commit, push, live control, debugger/CE,
  provider writes, and stale/missing actual-client proof;
- actual-client proof requirements for `https://mcp.360madden.com/mcp`, including
  40 observed tools, 40 output schemas, `clientTransportStatus=tool-call-succeeded`,
  `healthCallSucceeded=true`, and Stage47 `authRolePolicy` observation.

## Safety boundary

Stage 48 is non-executing by default. Required safety truth remains:

```yaml
readOnlyEvalPlan: true
serverStarted: false
publicTunnelStarted: false
chatGptRegistrationPerformed: false
gitMutation: false
remoteMutation: false
providerWrites: false
movementSent: false
inputSent: false
x64dbgAttach: false
noCheatEngine: true
proofPromotionPerformed: false
authEnforcementChanged: false
secretMaterialIncluded: false
```

With `--write`, the helper writes ignored artifacts only under:

```text
.riftreader-local\riftreader-chatgpt-mcp\eval-suite\*
```

## Validation to run

```text
python -m py_compile tools\riftreader_workflow\chatgpt_mcp_eval_suite.py tools\riftreader_workflow\riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_eval_suite.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_mcp_workflow_docs.py
python -m unittest scripts.test_chatgpt_mcp_eval_suite scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_mcp_workflow_docs
scripts\riftreader-chatgpt-mcp-eval-suite.cmd --json
scripts\riftreader-chatgpt-mcp-eval-suite.cmd --write --summary-md
git --no-pager diff --check
```

## Post-commit refresh required

After committing/pushing this slice, restart or refresh the non-Codex local HTTP
MCP runtime before asking ChatGPT Web/Desktop to observe current payloads. Final
readiness still requires fresh actual ChatGPT Web/Desktop proof; local SDK,
runtime, and eval-suite evidence are not substitutes.

## Next stage

Stage 49 is next: operational dashboard and recovery. No live input, CE/x64dbg
attach, proof promotion, provider writes, or push is authorized by this handoff.
