# ChatGPT MCP apply_latest_package_draft design

Status: Stage 19 local apply bridge implemented. This does **not** expose an apply MCP tool yet.

Stage 18 local-only preflight is implemented in
`tools\riftreader_workflow\package_draft_review.py --apply-preflight-latest-operator`.
It validates the operator draft, package root, matching dry-run summary, dry-run
age budget, and diff SHA-256 binding without calling package intake with
`--apply`.

Stage 19 local-only apply bridge is implemented in
`tools\riftreader_workflow\package_draft_review.py --apply-latest-operator`.
It requires the Stage 18 approval token before passing `--apply` to package
intake and remains outside the MCP tool manifest.

## Purpose

`apply_latest_package_draft` is the planned first repo-source-mutation tool for the RiftReader ChatGPT Web/Desktop MCP. It should bridge the already-proven package proposal -> inert draft -> review -> dry-run flow into a tightly gated package-intake apply step.

The tool must never become arbitrary filesystem write, shell execution, Git mutation, RIFT input, provider write, CE, or x64dbg control. Its only mutation path is the existing repo-owned package-intake helper using a reviewed package draft under `.riftreader-local`.

## Non-goals

- No Git staging, commit, push, reset, clean, branch rewrite, or remote mutation.
- No arbitrary command execution or shell-string command input.
- No arbitrary file write outside the package manifest target set.
- No provider repo writes.
- No RIFT input, target control, movement, CE, or x64dbg attach.
- No automatic apply from a self-test draft.

## Planned MCP tool shape

| Field | Rule |
|---|---|
| Tool name | `apply_latest_package_draft` |
| Read-only hint | `false` |
| Destructive hint | `false` initially only if apply is reversible/reviewable and excludes deletes; revisit before exposure. |
| Open-world hint | `false` |
| Arguments | `operatorOnly`, `draftId`, `dryRunSummaryPath`, `dryRunDiffSha256`, `approvalToken`, `timeoutSeconds` |
| Output | Structured JSON with `status`, `ok`, `applied`, `changedFiles`, `intakeSummary`, `validation`, `safety`, `blockers`, and `next`. |

## Required gates before apply

| Gate | Required behavior |
|---|---|
| Operator-origin draft | Latest or selected draft must be non-self-test unless an explicit self-test-only test mode is used outside ChatGPT. |
| Draft root confinement | Draft root must resolve under `.riftreader-local\artifact-bridge-package-drafts`. |
| Package root confinement | Package root must be the draft package directory; no arbitrary package path from ChatGPT. |
| Fresh dry-run | A matching dry-run summary must exist and be within the configured age budget. |
| Diff hash binding | Apply must verify the current dry-run diff SHA-256 or equivalent content hash before mutation. |
| Explicit approval | Tool must require an approval token or phrase generated from the selected draft/dry-run facts in the same session. |
| Clean preflight | Worktree state must be captured before apply; unrelated dirty files must block unless explicitly allowed by a future design. |
| No apply flag leakage | Only the apply helper may pass `--apply`; dry-run paths must keep blocking `--apply`. |
| Validation | Manifest checks must run by default after apply unless separately and explicitly disabled outside ChatGPT. |
| Safety truth | Response must truthfully report `applyFlagSent`, `repoSourceMutationExpected`, `gitMutation=false`, `providerWrites=false`, `inputSent=false`, `movementSent=false`, `x64dbgAttach=false`, and `noCheatEngine=true`. |

## Fail-closed blockers

| Code | Meaning |
|---|---|
| `APPLY_TOOL_NOT_ENABLED` | MCP tool is still hidden or disabled. |
| `APPLY_APPROVAL_MISSING` | Current-turn approval token/phrase was not supplied. |
| `APPLY_DRAFT_SELF_TEST_BLOCKED` | Selected draft is self-test. |
| `APPLY_DRAFT_NOT_FOUND` | Draft id/path is missing or invalid. |
| `APPLY_DRAFT_ROOT_INVALID` | Draft escaped `.riftreader-local`. |
| `APPLY_DRY_RUN_MISSING` | No matching dry-run summary exists. |
| `APPLY_DRY_RUN_STALE` | Dry-run exceeds age budget. |
| `APPLY_DRY_RUN_HASH_MISMATCH` | Diff/package hash no longer matches reviewed dry-run. |
| `APPLY_WORKTREE_DIRTY_UNRELATED` | Unrelated dirty files would make apply ambiguous. |
| `APPLY_PACKAGE_TARGET_INVALID` | Manifest target escapes allowed repo paths. |
| `APPLY_VALIDATION_FAILED` | Post-apply checks failed. |

## Minimal implementation sequence

1. Add a Python-only preflight helper that selects the operator draft and matching dry-run evidence.
2. Add hash/freshness binding tests around `.riftreader-local\package-intake\*` summaries.
3. Add an approval-token generator that includes draft id, diff hash, and changed file count.
4. Add an apply helper that calls `scripts\riftreader-package-intake.cmd --package <draft package> --apply` using argument arrays only.
5. Keep the MCP tool unregistered until helper tests, docs, and proof-template updates are ready.
6. Update actual ChatGPT proof contract only when the tool is intentionally exposed.

## Stage mapping

| Stage | Scope |
|---:|---|
| 17 | This design contract. |
| 18 | Package identity and freshness gate implemented local-only. |
| 19 | Apply dry-run-to-apply bridge helper implemented local-only. |
| 20 | Expose `apply_latest_package_draft` as MCP tool. |
| 21 | Actual-client apply proof. |
| 22 | Post-apply validation reporting. |
