# 2026-06-16 - MCP commit execution helper

## Current truth

| Item | Current state |
|---|---|
| Stage | Stage 25 `commit_reviewed_slice` approval-gated local commit helper is complete locally. |
| Helper | `tools\riftreader_workflow\commit_reviewed_slice.py --commit` reruns Stage 24 preflight before any mutation. |
| Approval | Commit execution requires the preflight `expectedApprovalToken`; missing or mismatched tokens block before staging. |
| Allowed mutation | `git add -- <explicit paths>`, `pre-commit run --files <explicit paths>`, then `git commit -m <message>`. |
| Output | Structured JSON with `preHead`, `postHead`, `commitHash`, staged paths, command envelopes, blockers, warnings, post-status, and safety truth. |
| Boundary | No MCP exposure yet, no push, no reset/clean/stash/restore, no branch rewrite, no package apply, no provider write, no live RIFT input/movement, no CE, and no x64dbg. |

## Validation

| Check | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\commit_reviewed_slice.py scripts\test_commit_reviewed_slice.py` | Passed |
| `python -m unittest scripts.test_commit_reviewed_slice` | Passed: 10 tests |
| `scripts\riftreader-commit-reviewed-slice.cmd --self-test --json` | Passed, including synthetic approved local commit in a temp repo |
| Targeted validation ledger | `.riftreader-local\validation-runs\20260616-133407-058742\summary.md`, duration `9.297s`, status `passed` |

## Next action

Stage 26 can expose `commit_reviewed_slice` through MCP only after preserving
the same preflight and approval-token contract in the tool schema. Stage 21
approved package-apply actual-client proof remains separate and gated.
