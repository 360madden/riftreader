# ChatGPT MCP commit_reviewed_slice design

Status: Stage 25 approval-gated local commit execution helper implemented
locally. No MCP commit tool is exposed yet.

## Stage 24-25 implementation status

| Item | Current local surface |
|---|---|
| Python helper | `tools\riftreader_workflow\commit_reviewed_slice.py` |
| Thin wrapper | `scripts\riftreader-commit-reviewed-slice.cmd` |
| Read-only mode | `--preflight` reads `HEAD`, porcelain Git status, requested paths, commit message, and machine-readable validation evidence. |
| Local commit mode | `--commit` reruns preflight, checks the approval token, stages explicit paths only, runs `pre-commit run --files`, and creates one local commit. |
| Self-test | `scripts\riftreader-commit-reviewed-slice.cmd --self-test --json` |
| Focused tests | `python -m unittest scripts.test_commit_reviewed_slice` |
| Mutation boundary | Commit mode allows only `git add -- <explicit paths>`, `pre-commit run --files <explicit paths>`, and `git commit -m <message>` after approval. No push, reset, clean, branch rewrite, package apply, provider write, live input, CE, or x64dbg. |

## Purpose

`commit_reviewed_slice` is the planned local Git commit tool for the
RiftReader ChatGPT Web/Desktop MCP after a package apply has already happened
and the operator has reviewed the resulting source diff.

The tool must keep Git mutation separate from package apply and push. Its only
intended mutation is one local `git commit` containing an explicitly reviewed,
validated, bounded path set.

## Non-goals

- No `git push`, remote mutation, force push, branch rewrite, merge, rebase, or
  tag creation.
- No `git reset`, `git clean`, checkout/discard, stash, or destructive cleanup.
- No `git add .`, wildcard staging, shell-string command input, or arbitrary
  command execution.
- No package apply, provider repo write, live RIFT input, movement, CE, or
  x64dbg attach.
- No committing ignored `.riftreader-local` artifacts.

## Planned MCP tool shape

| Field | Rule |
|---|---|
| Tool name | `commit_reviewed_slice` |
| Read-only hint | `false` |
| Destructive hint | `false`; local commit only, no discard/rewrite/push path. |
| Open-world hint | `false` |
| Arguments | `expectedHead`, `paths`, `commitMessage`, `validationSummaryPath`, `validationDigest`, `approvalToken`, `timeoutSeconds` |
| Output | Structured JSON with `status`, `ok`, `committed`, `commitHash`, `stagedPaths`, `validation`, `safety`, `blockers`, `warnings`, and `next`. |

## Required gates before commit

| Gate | Required behavior |
|---|---|
| Clean base identity | `expectedHead` must match current `HEAD`; stale requests block. |
| Explicit path set | Every staged path must be listed in `paths`; empty path sets block. |
| No unrelated dirty files | Dirty tracked/untracked paths outside `paths` block unless a future design explicitly labels them ignored evidence. |
| No ignored artifacts | `.riftreader-local/**`, `.git/**`, binary dumps, local captures, and secret-like paths are never stageable. |
| Package lineage | Preferred source is `postApplyValidationReport.changedFiles`; commit paths must be a subset of reviewed changed files unless a future non-package lane defines another source. |
| Validation gate | Required validation must have run after the latest source change; failed, missing, stale, or mismatched validation blocks. |
| Pre-commit gate | Local pre-commit must pass for the staged path set or all files, depending on changed surface. |
| Visible commit message | Commit message must be operator-visible, non-empty, bounded length, and free of secrets/control characters. |
| Explicit approval | Commit requires an approval token generated from `expectedHead`, normalized path list, commit message, and validation digest. |
| Local-only Git mutation | Helper may stage explicit paths and create one local commit; it must not push, rewrite, clean, reset, or mutate remote refs. |

## Fail-closed blockers

| Code | Meaning |
|---|---|
| `COMMIT_TOOL_NOT_ENABLED` | MCP tool is still hidden or disabled. |
| `COMMIT_APPROVAL_MISSING` | Approval token was not supplied. |
| `COMMIT_APPROVAL_TOKEN_MISMATCH` | Token does not match current commit facts. |
| `COMMIT_HEAD_MISMATCH` | Current `HEAD` differs from `expectedHead`. |
| `COMMIT_PATHS_EMPTY` | No explicit path set was supplied. |
| `COMMIT_PATH_NOT_DIRTY` | Requested path has no staged/unstaged change to commit. |
| `COMMIT_PATH_UNTRACKED_NOT_ALLOWED` | Untracked path is not allowed by the current source policy. |
| `COMMIT_PATH_FORBIDDEN` | Path is ignored/local, secret-like, binary, outside repo, or otherwise forbidden. |
| `COMMIT_UNRELATED_DIRTY_PATHS` | Worktree contains dirty paths outside the requested commit set. |
| `COMMIT_VALIDATION_MISSING` | Required validation evidence is absent. |
| `COMMIT_VALIDATION_DIGEST_MISMATCH` | Supplied validation digest does not match the evidence file. |
| `COMMIT_VALIDATION_HEAD_MISMATCH` | Validation evidence was generated against another `HEAD`. |
| `COMMIT_VALIDATION_STALE` | Validation predates the latest requested path change. |
| `COMMIT_VALIDATION_FAILED` | Validation evidence includes failures or blockers. |
| `COMMIT_PRECOMMIT_FAILED` | Local pre-commit gate failed. |
| `COMMIT_MESSAGE_INVALID` | Commit message is empty, too long, control-character-containing, or secret-like. |
| `COMMIT_GIT_COMMAND_FAILED` | `git add` or `git commit` returned an unexpected exit code. |

## Planned helper split

| Stage | Helper | Mutation | Purpose |
|---:|---|---|---|
| 24 | `commit_reviewed_slice_preflight` | None | Implemented locally; reads Git status, validates paths/message/validation, and returns approval facts plus exact future commands. |
| 25 | `commit_reviewed_slice_apply` | Local Git only | Implemented locally; re-validates preflight facts, stages explicit paths, runs pre-commit, and creates one local commit after approval. |
| 26 | MCP wrapper | Local Git only | Exposes the Stage 25 helper as `commit_reviewed_slice` with strict argument caps and output schema. |
| 27 | Actual-client proof | Local Git only | Proves ChatGPT can request a local commit without push/rewrite and receives commit hash/status. |

## Command policy

Allowed command forms inside the future helper:

```text
git --no-pager status --porcelain=v1 -z
git rev-parse HEAD
git add -- <explicit path>...
pre-commit run --files <explicit path>...
git commit -m <visible message>
```

Forbidden command forms:

```text
git add .
git add -A
git commit -a
git push
git reset
git clean
git checkout -- <path>
git restore <path>
git rebase
git merge
shell=True / cmd.exe / powershell command strings for Git mutation
```

## Safety output contract

Every preflight and commit response must include:

```json
{
  "safety": {
    "gitMutation": true,
    "localCommitOnly": true,
    "remoteMutation": false,
    "branchRewrite": false,
    "destructiveCleanup": false,
    "explicitPathsOnly": true,
    "providerWrites": false,
    "inputSent": false,
    "movementSent": false,
    "x64dbgAttach": false,
    "noCheatEngine": true,
    "applyFlagSent": false
  }
}
```

For preflight-only responses, `gitMutation` must be `false` while preserving the
same remote/live/provider safety fields.

## Acceptance tests for implementation

- Blocks `git add .`, wildcard-like paths, path traversal, `.riftreader-local`,
  secret-like paths, and binary dump paths.
- Blocks unrelated dirty worktree paths.
- Blocks stale `expectedHead`.
- Blocks stale, missing, or failed validation evidence.
- Preflight emits an approval token preview; commit mode blocks missing or mismatched approval tokens before Git mutation.
- Emits exact explicit-path commands in preflight without mutating Git.
- On approved execution, stages only explicit paths, runs pre-commit, and
  creates one local commit.
- Reports `commitHash`, `stagedPaths`, pre/post `HEAD`, and clean/dirty status
  after commit.
- Proves no push, branch rewrite, reset, clean, provider write, live input, CE,
  or x64dbg action occurred.
