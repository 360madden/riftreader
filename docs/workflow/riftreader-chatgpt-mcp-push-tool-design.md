# RiftReader ChatGPT MCP `push_current_branch` design

Status: **Stage 29 complete-local preflight**. The design spec exists and the
read-only preflight helper exists. The tool is intentionally **not exposed**
until Stage 30 push execution and MCP wrapper tests pass.

## Purpose

`push_current_branch` is the future ChatGPT-visible remote Git mutation tool.
It must stay separate from `commit_reviewed_slice`: committing proves a local
slice; pushing publishes the already-created current branch. The tool may only
perform a normal non-force push of the current branch after a fresh preflight
binds the exact branch, upstream, HEAD, ahead/behind state, and approval token.

## Non-goals

| Forbidden behavior | Rule |
|---|---|
| Force push | Never expose `--force`, `--force-with-lease`, `+refspec`, or branch rewrite. |
| Implicit commit | Never stage, commit, amend, reset, clean, stash, checkout, or restore. |
| Arbitrary remote mutation | Only push the current branch to its unambiguous `origin/<branch>` upstream. |
| Provider writes | Never write ChromaLink, RiftScan, or any repo outside RiftReader. |
| Shell endpoint | Do not accept shell strings or arbitrary Git arguments. |
| Live/debugger work | No RIFT input, movement, `/reloadui`, screenshot key input, CE, or x64dbg. |

## Stage split

| Stage | Deliverable | Mutation? |
|---:|---|---|
| 28 | This design spec plus MCP control-plan contract. | No |
| 29 | `push_current_branch.py --preflight` read-only branch/upstream/ahead-behind checker. | No — implemented |
| 30 | `push_current_branch.py --push` and MCP `push_current_branch` wrapper after preflight tests. | Yes, normal remote push only |
| 31 | ChatGPT-visible current-head CI monitor after push. | No |

## Proposed MCP arguments

| Argument | Required | Meaning |
|---|---:|---|
| `expectedHead` | Yes | Exact 40-character HEAD SHA from the matching preflight. |
| `branch` | Yes | Current branch name from preflight. |
| `upstream` | Yes | Exact upstream ref, normally `origin/<branch>`. |
| `approvalToken` | Yes for push, absent for preflight | `PUSH-...` token derived from preflight facts. |
| `timeoutSeconds` | No | Bounded helper timeout; default remains finite. |

No arbitrary refspec, remote name, shell command, file path, or Git argument is
accepted by the MCP tool.

## Read-only preflight contract

The Stage 29 helper gathers:

| Fact | Required check |
|---|---|
| Current branch | Must be named; detached HEAD blocks. |
| Current HEAD | Must be exact and later matched by `expectedHead`. |
| Upstream | Must exist and be unambiguous, normally `origin/<branch>`. |
| Ahead/behind | Must be `ahead > 0`, `behind == 0`; diverged blocks. |
| Worktree state | Must be clean, including untracked files. |
| Remote URL | Must be reported; unexpected/missing `origin` blocks. |
| Future command | Must be fixed-array form such as `git push origin HEAD:<branch>`. |
| CI follow-up | Must tell the operator to run or call current-head CI status after push. |

The preflight returns `expectedApprovalToken` only when every gate passes.

## Approval token binding

The token must hash only current preflight facts:

```json
{
  "expectedHead": "<HEAD>",
  "branch": "<branch>",
  "upstream": "origin/<branch>",
  "ahead": 1,
  "behind": 0
}
```

Changing branch, HEAD, upstream, ahead/behind, or dirty state invalidates the
token. The execution helper must rerun preflight immediately before pushing.

## Fail-closed blockers

| Blocker | Meaning |
|---|---|
| `PUSH_BRANCH_UNNAMED` | Detached HEAD or unreadable branch. |
| `PUSH_UPSTREAM_MISSING` | No upstream ref is configured. |
| `PUSH_UPSTREAM_AMBIGUOUS` | Upstream is not a simple `origin/<branch>` ref. |
| `PUSH_REMOTE_UNEXPECTED` | Required `origin` remote is absent or unsafe. |
| `PUSH_WORKTREE_DIRTY` | Any tracked or untracked worktree change exists. |
| `PUSH_HEAD_MISMATCH` | Runtime HEAD differs from approved preflight. |
| `PUSH_BRANCH_MISMATCH` | Runtime branch differs from approved preflight. |
| `PUSH_UPSTREAM_MISMATCH` | Runtime upstream differs from approved preflight. |
| `PUSH_NOTHING_TO_PUSH` | Branch is not ahead of upstream. |
| `PUSH_BRANCH_BEHIND` | Upstream contains commits not in local branch. |
| `PUSH_DIVERGED` | Branch is both ahead and behind. |
| `PUSH_APPROVAL_MISSING` | Push requested without current-turn approval token. |
| `PUSH_APPROVAL_TOKEN_MISMATCH` | Token does not match current preflight facts. |
| `PUSH_FORCE_FORBIDDEN` | Any force/rewrite path is requested or detected. |
| `PUSH_REMOTE_HEAD_VERIFY_FAILED` | Remote ref does not equal local HEAD after push. |

## Stage 30 push execution contract

Execution may run only after a passing Stage 29 preflight and matching approval
token:

1. Rerun preflight.
2. Verify `expectedHead`, `branch`, `upstream`, and approval token.
3. Run fixed-array command: `git push origin HEAD:<branch>`.
4. Verify remote head with a read-only `git ls-remote origin refs/heads/<branch>`.
5. Return pushed state, command envelopes, remote head, safety flags, and CI
   follow-up command.

Safety flags must truthfully report `gitMutation=true`,
`remoteMutation=true`, `pushed=true`, `forcePush=false`,
`branchRewrite=false`, `destructiveCleanup=false`, `providerWrites=false`,
`inputSent=false`, and `x64dbgAttach=false`.

## Stage 31 CI follow-up

After any successful push, ChatGPT must be able to call a read-only current-head
CI status surface backed by `tools/riftreader_workflow/mcp_ci_status.py`. Push
success is not the same as CI success; the returned next action must direct the
operator or ChatGPT to verify required GitHub Actions for the pushed HEAD.

## Exposure rule

Do not add `push_current_branch` to `EXPECTED_CHATGPT_MCP_TOOL_NAMES` until:

1. Stage 29 preflight helper exists.
2. Stage 29 tests pass for ready, dirty, missing upstream, behind/diverged, and
   token-fact cases.
3. Stage 30 execution tests prove approved normal push and denied missing or
   mismatched token.
4. MCP wrapper tests prove strict arguments, annotations, output schema, and
   denial behavior.
5. Actual MCP connector proof starts only after
   `scripts\riftreader-mcp-server-status.cmd --json` reports
   `status=running-current`.
