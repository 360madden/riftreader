# 2026-06-16 - MCP commit tool exposed locally

## Current truth

| Item | Current state |
|---|---|
| Stage | Stage 26 `commit_reviewed_slice` MCP wrapper is implemented locally. |
| Tool surface | Full ChatGPT MCP profile intentionally changes from 19 to 20 tools by adding `commit_reviewed_slice` after `apply_latest_package_draft`. |
| Tool contract | Requires `expectedHead`, explicit `paths`, `commitMessage`, `validationSummaryPath`, `validationDigest`, and a local preflight `approvalToken` before any commit mutation. |
| Mutation boundary | The only allowed Git mutation path is one local explicit-path commit via the Stage 25 helper; no push, branch rewrite, reset, clean, package apply, provider write, RIFT input/movement, CE, or x64dbg. |
| Safety truth | Health/final-readiness safety now reports no broad Git endpoint plus a `commit_reviewed_slice`-limited local commit endpoint, instead of claiming no Git mutation endpoint exists. |

## Validation

| Check | Result |
|---|---|
| `python -m py_compile ...` for MCP surface/final-readiness/recorder/test files | Passed |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_mcp_final_readiness scripts.test_chatgpt_trial_recorder scripts.test_commit_reviewed_slice` | Passed: 141 tests |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --validate-sdk --json` | Passed; registered 20 tools with output schemas and annotations. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --self-test --json` | Passed; ignored `.riftreader-local` artifacts only. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --trial-readiness --json` | Passed; local proposal transport smoke registered/called the 20-tool surface. Artifact: `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260616T135801Z-trial-readiness.json`. |
| Targeted validation ledger | `.riftreader-local\validation-runs\20260616-135442-071811\summary.md`, duration `9.519s`, status `passed`. |
| Fresh proof template | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260616-135424Z\proof-input.json` with `proofMode=final-20-tool` and `toolCount=20`. |
| Final gate | Expected blocked while worktree is dirty and latest actual-client proof is still the prior 19-tool proof; local `toolSurfaceStatus=passed`. |

## Current blocker / next action

Final readiness is expected to block until the new 20-tool surface is recorded
from actual ChatGPT Web/Desktop through `https://mcp.360madden.com/mcp` and
current-head CI is green after this commit. Stage 21 approved package-apply proof
and Stage 27 approved local-commit proof remain separate gated lanes; do not run
approved apply or approved commit proof without deliberate operator approval.
