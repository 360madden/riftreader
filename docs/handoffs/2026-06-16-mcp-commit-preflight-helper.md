# 2026-06-16 - MCP commit preflight helper

## Current truth

| Item | Current state |
|---|---|
| Stage | Stage 24 `commit_reviewed_slice` read-only preflight is complete locally. |
| Helper | `tools\riftreader_workflow\commit_reviewed_slice.py` validates a requested local commit slice without staging or committing. |
| Wrapper | `scripts\riftreader-commit-reviewed-slice.cmd` is a thin launcher for `--preflight` and `--self-test`. |
| Gates | Exact `HEAD`, explicit safe paths, no unrelated dirty paths, machine-readable validation digest, validation status/head/staleness, and visible commit message. |
| Output | Structured JSON with blockers, warnings, `approvalFacts`, `expectedApprovalToken`, and exact future `git add --`, `pre-commit run --files`, and `git commit -m` command arrays. |
| Boundary | No Git mutation, push, reset, clean, branch rewrite, package apply, provider write, live RIFT input/movement, CE, or x64dbg. |

## Validation

| Check | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\commit_reviewed_slice.py scripts\test_commit_reviewed_slice.py` | Passed |
| `python -m unittest scripts.test_commit_reviewed_slice` | Passed: 6 tests |
| `scripts\riftreader-commit-reviewed-slice.cmd --self-test --json` | Passed |
| Targeted validation ledger | `.riftreader-local\validation-runs\20260616-132315-624147\summary.md`, duration `5.316s`, status `passed` |
| Real dirty-slice preflight | Passed read-only against this 7-path Stage 24 slice and emitted `COMMIT-e453bd867c93cd75`; no staging or commit performed by the helper. |

## Next action

Stage 25 can add the approval-gated local commit execution helper, reusing this
preflight contract. Stage 21 approved package-apply actual-client proof remains
a separate gated MCP proof lane and still requires deliberate approval before
running an approved apply.
