# RiftReader ChatGPT MCP current handoff — actual proof checklist hardening

Updated: 2026-06-05T20:35Z  
Repo: `C:\RIFT MODDING\RiftReader`  
Branch at handoff: `main`  
Current HEAD: `df35954 Harden MCP actual proof checklist`  
Upstream state: `main...origin/main [ahead 12]`  
Predecessor handoff: `docs\handoffs\2026-06-05-2000-chatgpt-mcp-gated-apply-smoke-handoff.md`

## TL;DR

The ChatGPT Web/Desktop MCP lane remains locally ready for the next explicit
actual-client proof step, but final readiness is still intentionally
**blocked** on external/gated evidence:

- `main` is ahead of `origin/main` by 12 commits, so remote CI cannot exist yet.
- The only actual ChatGPT proof artifact is stale and still reflects the old
  8-tool contract.
- No public tunnel, ChatGPT registration, push, live RIFT input, CE, x64dbg,
  provider write, or proof promotion was performed for this handoff.

Two local hardening commits were added after the previous handoff:

| Commit | Purpose |
|---|---|
| `df35954` | Harden Mission Control checklist/progress so actual-client completion requires template, output schemas, draft/review/dry-run, and apply-denial proof. |
| `c6073a4` | Extend fallback public trial preflight client to run proposal submit, inbox, draft, review, dry-run, and `apply_latest_package_draft` without approval. |

## Current 11-tool MCP surface

1. `health`
2. `get_repo_status`
3. `get_latest_handoff`
4. `get_package_proposal_template`
5. `submit_package_proposal`
6. `list_inbox`
7. `create_package_draft_from_inbox`
8. `review_latest_package_draft`
9. `dry_run_latest_package_draft`
10. `apply_latest_package_draft`
11. `get_workflow_control_plan`

## What changed since the previous handoff

### Public trial preflight now mirrors local proposal smoke

`cloudflare_smoke_client_result(..., include_proposal_submit=True)` now runs:

1. `initialize`
2. `tools/list`
3. `health`
4. `submit_package_proposal`
5. `list_inbox`
6. `create_package_draft_from_inbox`
7. `review_latest_package_draft`
8. `dry_run_latest_package_draft`
9. `apply_latest_package_draft` without an approval token

The fallback public trial session enables that sequence. Basic Cloudflare smoke
remains health/tools-only unless the proposal flag is explicitly used.

Expected fail-closed apply facts:

| Field | Required value |
|---|---|
| `applyLatestPackageDraftWithoutApprovalStructuredContent.ok` | `false` |
| `applyLatestPackageDraftWithoutApprovalStructuredContent.applied` | `false` |
| `applyLatestPackageDraftWithoutApprovalStructuredContent.blockers` | includes `APPLY_APPROVAL_MISSING` |
| `applyLatestPackageDraftWithoutApprovalStructuredContent.safety.applyFlagSent` | `false` |
| `applyLatestPackageDraftWithoutApprovalStructuredContent.safety.repoSourceMutationExpected` | `false` |

### Mission Control checklist now matches the proof contract

`scripts\riftreader-mcp-mission-control.cmd --checklist-md` now explicitly asks
the operator to:

- generate the current proof template,
- confirm all 11 tools and output schemas,
- call `get_package_proposal_template`,
- submit a tiny package proposal,
- confirm the returned inbox ID,
- call `create_package_draft_from_inbox`,
- call `review_latest_package_draft` and confirm `readOnlyReview: true`,
- call `dry_run_latest_package_draft` and record `dryRun.diffPreview` evidence,
- call `apply_latest_package_draft` without an approval token and confirm
  `APPLY_APPROVAL_MISSING` plus `applied: false`,
- record the resulting proof with the trial recorder.

Mission Control’s internal actual-client completion check now requires these
same proof facts before it can mark the external proof phase complete.

### Workflow-state summaries now preserve new proof fields

Latest actual-client proof summaries now carry:

| Field |
|---|
| `createPackageDraftSucceeded` |
| `reviewLatestPackageDraftSucceeded` |
| `reviewLatestPackageDraftReadOnly` |
| `dryRunDiffPreviewOk` |
| `dryRunDiffPreviewArtifactUnderPackageIntake` |
| `dryRunDiffPreviewBoundedBytes` |
| `dryRunDiffPreviewTextLength` |
| `dryRunDiffPreviewTruncated` |
| `applyLatestPackageDraftWithoutApprovalBlocked` |
| `applyLatestPackageDraftWithoutApprovalBlockers` |
| `applyLatestPackageDraftWithoutApprovalApplied` |

## Latest local readiness evidence

| Field | Value |
|---|---|
| Command | `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` |
| Result | `passed` |
| Run UTC | `2026-06-05T20:19:38Z` |
| Tool count | `11` |
| Trial readiness artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T201938Z-trial-readiness.json` |
| Proposal transport smoke artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T201938Z-proposal-transport-smoke.json` |
| Apply-denial blockers observed | `APPLY_DRAFT_SELF_TEST_BLOCKED`, `APPLY_PREFLIGHT_NOT_READY`, `APPLY_APPROVAL_MISSING` |

Safety facts from readiness:

| Boundary | State |
|---|---:|
| Public tunnel started | No |
| ChatGPT registration performed | No |
| Git mutation | No |
| Package apply flag sent | No |
| RIFT input | No |
| CE/x64dbg | No |
| Provider writes | No |

## Validation run for current HEAD

| Command | Result |
|---|---:|
| `python -m unittest scripts.test_mcp_mission_control scripts.test_mcp_workflow_state` | 13 OK |
| Full MCP/local suite (`scripts.test_riftreader_chatgpt_mcp ... scripts.test_mcp_final_readiness`) | 265 OK |
| `git --no-pager diff --check` | Passed |
| `python -m py_compile tools\riftreader_workflow\mcp_mission_control.py tools\riftreader_workflow\mcp_workflow_state.py` | Passed |
| `pre-commit run --all-files --show-diff-on-failure` | Passed |
| `scripts\riftreader-mcp-mission-control.cmd --checklist-md` | Generated updated checklist |
| `scripts\riftreader-mcp-final.cmd --status --compact-json` | Blocked as expected on external/gated items |

## Current final-readiness status

Latest final compact status before this handoff:

| Field | Value |
|---|---|
| `currentHead` | `df35954ea141b52aa3112082118d81b88c8f1dd2` |
| `status` / `ok` | `blocked` / `false` |
| `gitDirty` | `false` |
| `toolSurfaceStatus` | `passed` |
| `dependencyStatus` | `passed` |
| `environmentStatus` | `passed` |
| `publicSessionStatus` | `passed` |
| `proofReplayStatus` | `blocked` |
| `proofFreshnessStatus` | `stale` |
| `upstreamStatus` | `blocked` (`ahead=12`) |
| `recommendedNextAction.key` | `record-actual-client-proof` |

Expected blockers remain:

| Blocker class | Meaning |
|---|---|
| `git:upstream-not-synced:behind=0:ahead=12` | Local commits are not pushed; push is gated. |
| `ci:missing:.NET build and test` / `ci:missing:RiftReader Policy` | Current-head CI cannot exist until pushed. |
| `proof:replay-failed:*` | Existing actual-client proof is stale and from the older tool/proof contract. |
| `proof:stale` | Actual ChatGPT proof must be refreshed. |

## Actual ChatGPT proof requirements now

Start with:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json
```

The proof must include:

| Field | Required value |
|---|---|
| `connectionMode` | `openai-secure-mcp-tunnel` unless fallback explicitly selected |
| `chatgptRegistrationSucceeded` | `true` |
| `templateFetched` | `true` |
| `toolCount` | `11` |
| `toolNames` | exact 11-tool surface above |
| `toolOutputSchemasPresent` | `true` |
| `toolOutputSchemaCount` | `11` |
| `toolOutputSchemaToolNames` | exact 11-tool surface above |
| `submitPackageProposalSucceeded` | `true` |
| `listInboxSawInboxId` | `true` |
| `createPackageDraftSucceeded` | `true` |
| `reviewLatestPackageDraftSucceeded` | `true` |
| `reviewLatestPackageDraftReadOnly` | `true` |
| `dryRunSucceeded` | `true` |
| `dryRunDiffPreviewOk` | `true` |
| `dryRunDiffPreviewArtifactUnderPackageIntake` | `true` |
| `dryRunDiffPreviewBoundedBytes` | `true` |
| `dryRunDiffPreviewTextLength` | integer `> 0` |
| `dryRunDiffPreviewTruncated` | boolean |
| `applyLatestPackageDraftWithoutApprovalBlocked` | `true` |
| `applyLatestPackageDraftWithoutApprovalBlockers` | includes `APPLY_APPROVAL_MISSING` |
| `applyLatestPackageDraftWithoutApprovalApplied` | `false` |

Record after filling:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --record --input proof.json --json
scripts\riftreader-mcp-final.cmd --status --compact-json
```

## Safety boundaries preserved

| Boundary | State |
|---|---:|
| Public tunnel | Not started |
| ChatGPT registration | Not performed |
| Persistent MCP server | Not left running |
| Git push | Not performed |
| Git mutation endpoint exposed to MCP | No |
| Arbitrary shell endpoint exposed to MCP | No |
| Live RIFT input | Not sent |
| CE/x64dbg | Not used |
| Provider repo writes | Not performed |
| Proof/current-truth promotion | Not performed |

## Separate non-MCP blocker

The repo decision packet remains in the proof-recovery lane with
`latest-static-owner-readback-root-pointer-null`. That is separate from the
ChatGPT MCP product lane. Do not loop root rediscovery during MCP continuation
unless the user explicitly shifts focus back to proof recovery.

## Exact resume commands

```cmd
git status --short --branch
git --no-pager log --oneline -20
scripts\riftreader-mcp-final.cmd --status --compact-json
scripts\riftreader-mcp-mission-control.cmd --checklist-md
scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json
scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Approve push of `main` when ready | Current HEAD is ahead of origin by 12; remote CI requires the commits. |
| 2 | Run `scripts\riftreader-mcp-mission-control.cmd --checklist-md` | This is now the most accurate operator proof checklist. |
| 3 | Generate the current proof template | Prevents using stale 8-tool proof structure. |
| 4 | Use OpenAI Secure MCP Tunnel for actual ChatGPT Web/Desktop proof | This is the preferred primary route; Cloudflare is fallback-only. |
| 5 | In ChatGPT, verify all 11 tools and all output schemas | Final gate requires exact surface/schema proof. |
| 6 | In ChatGPT, exercise proposal submit through dry-run | Proves meaningful bidirectional data/tool interaction. |
| 7 | In ChatGPT, call apply without approval and confirm `APPLY_APPROVAL_MISSING` | Proves fail-closed behavior before any real apply is considered. |
| 8 | Record proof immediately with `--record --input proof.json --json` | Makes external ChatGPT observations replayable locally. |
| 9 | Rerun final readiness after proof and CI | Confirms whether blockers clear. |
| 10 | Write the final release handoff only after proof and CI pass | Avoids overstating current product completion. |
