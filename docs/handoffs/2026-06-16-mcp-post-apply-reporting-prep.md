# 2026-06-16 - MCP post-apply validation reporting prepared locally

## Current lane

Safe MCP package-apply follow-up prep. This slice does not run an approved
package apply, does not mutate Git, and does not touch live RIFT, CE, x64dbg, or
provider repos.

## Result

| Item | Current truth |
|---|---|
| Problem | After a future approved `apply_latest_package_draft`, the bridge returned package-intake JSON but did not promote changed files, validation commands, rollback, and commit-gate guidance into a stable post-apply report. |
| Fix | `apply_latest_package_draft` now adds `postApplyValidationReport` when package intake returns JSON. |
| Report contents | `changedFiles`, `changedFileCount`, check counts, blockers/warnings/errors, rollback metadata, artifact paths, recommended validation command arrays, and `commitGate.allowedNow=false`. |
| Python validation hint | If changed files include `.py`, the report recommends `python -m py_compile <changed .py files>` before `git --no-pager diff --check`. |
| Git boundary | Commit and push remain separate explicit Git gates; the apply report never stages, commits, pushes, or rewrites refs. |
| Exposure truth | Package-draft preflight/apply helper safety now reports `mcpToolExposed=true` / `applyToolExposed=true`, matching the Stage 20 exposed MCP tool state. |

## Files changed

- `tools/riftreader_workflow/package_draft_review.py`
- `tools/riftreader_workflow/riftreader_chatgpt_mcp.py`
- `scripts/test_package_draft_review.py`
- `docs/HANDOFF.md`
- `docs/handoffs/2026-06-16-mcp-post-apply-reporting-prep.md`

## Validation evidence

| Check | Result |
|---|---|
| py_compile | Passed for `tools\riftreader_workflow\package_draft_review.py` and `scripts\test_package_draft_review.py`. |
| Focused tests | Passed for `scripts.test_package_draft_review` and `scripts.test_riftreader_chatgpt_mcp`. |

## Remaining gate

Stage 21 actual-client apply proof is still not performed. To use this report,
run the approved package-apply proof only after a deliberate package proposal,
review, dry-run hash binding, and approval-token step.
