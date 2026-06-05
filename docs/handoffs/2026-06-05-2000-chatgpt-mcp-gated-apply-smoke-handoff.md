# RiftReader ChatGPT MCP current handoff — gated apply smoke and proof contract

Updated: 2026-06-05T20:00Z
Repo: `C:\RIFT MODDING\RiftReader`
Branch at handoff: `main`
Current HEAD: `0fa7125 Cover gated apply denial in MCP smoke`
Upstream state: `main...origin/main [ahead 9]`
Predecessor handoff: `docs\handoffs\2026-06-05-1730-chatgpt-mcp-current-gate-handoff.md`

## TL;DR

The ChatGPT Web/Desktop MCP lane is locally at **Stage 20 complete / Stage 21 gated**.
The local MCP server exposes **11 allowlisted tools**, including
`apply_latest_package_draft`. Apply is exposed only behind the local approval-token
gate. The loopback transport smoke now also calls `apply_latest_package_draft`
without approval and requires fail-closed denial with `APPLY_APPROVAL_MISSING`,
`applied=false`, and `applyFlagSent=false`.

Final readiness is intentionally still **blocked** until a fresh actual ChatGPT
client proof is recorded and current-head CI exists for the unpushed commits.
No push, public tunnel, ChatGPT registration, live RIFT input, CE, x64dbg,
provider write, or proof promotion was performed for this handoff.

## Current local commits in this slice

| Commit | Purpose |
|---|---|
| `0fa7125` | Cover gated apply denial in local MCP proposal transport smoke. |
| `9a1bb3d` | Require actual ChatGPT proof to include apply-without-approval denial fields. |
| `4de49e5` | Update proof/final-readiness tool contracts from 10 tools to 11 tools. |
| `728bdfb` | Expose `apply_latest_package_draft` as a gated MCP tool. |
| `588f337` | Add local package apply bridge behind approval-token preflight. |
| `0586641` | Add package apply preflight gate. |
| `41092a0` | Add MCP apply tool design contract. |
| `79ea0ad` | Add MCP 50-stage product plan. |
| `81d48ba` | Surface MCP future capability roadmap. |
| `591eaaf` | Record previous MCP current gate handoff. |

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

## Apply safety contract

| Gate | Current state |
|---|---:|
| Tool exposed | Yes, as `apply_latest_package_draft` |
| Requires local approval token | Yes |
| Requires dry-run preflight | Yes |
| Requires dry-run diff SHA binding | Yes |
| Applies self-test draft without approval | No |
| Stages/commits/pushes | No |
| Runs arbitrary shell | No |
| Sends RIFT input | No |
| Writes provider repos | No |
| Uses CE/x64dbg | No |

## New local transport-smoke proof

`run_transport_smoke_test(..., include_proposal_submit=True)` now performs:

1. `list_tools`
2. `health`
3. `submit_package_proposal` with a synthetic self-test proposal
4. `list_inbox`
5. `create_package_draft_from_inbox`
6. `review_latest_package_draft`
7. `dry_run_latest_package_draft`
8. `apply_latest_package_draft` without `approvalToken`

Expected apply-denial facts in local readiness:

| Field | Expected |
|---|---|
| `client.applyLatestPackageDraftWithoutApproval.ok` | `false` |
| `client.applyLatestPackageDraftWithoutApproval.applied` | `false` |
| `client.applyLatestPackageDraftWithoutApproval.blockers` | includes `APPLY_APPROVAL_MISSING` |
| `client.applyLatestPackageDraftWithoutApproval.applyFlagSent` | `false` |
| `client.applyLatestPackageDraftWithoutApproval.repoSourceMutationExpected` | `false` |
| `safety.packageDraftApplyWithoutApprovalBlocked` | `true` |

Latest local readiness evidence from this session:

| Field | Value |
|---|---|
| Command | `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` |
| Result | `passed` |
| Tool count | `11` |
| Trial readiness artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T195411Z-trial-readiness.json` |
| Proposal transport smoke artifact | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260605T195411Z-proposal-transport-smoke.json` |
| Apply-denial blockers observed | `APPLY_DRAFT_SELF_TEST_BLOCKED`, `APPLY_PREFLIGHT_NOT_READY`, `APPLY_APPROVAL_MISSING` |

## Validation run

| Command | Result |
|---|---:|
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_final_readiness` | 103 OK |
| Full MCP/local suite (`scripts.test_riftreader_chatgpt_mcp ... scripts.test_mcp_final_readiness`) | 263 OK |
| `git --no-pager diff --check` | Passed |
| `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py` | Passed |
| `pre-commit run --all-files --show-diff-on-failure` | Passed |
| `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` | Passed |
| `scripts\riftreader-mcp-final.cmd --status --compact-json` | Blocked as expected on external/gated items |

## Current final-readiness status

Latest final compact status after `0fa7125`:

| Field | Value |
|---|---|
| `currentHead` | `0fa7125f6741d88352ee1c33566e956e1910bece` |
| `status` / `ok` | `blocked` / `false` |
| `gitDirty` | `false` |
| `toolSurfaceStatus` | `passed` |
| `dependencyStatus` | `passed` |
| `environmentStatus` | `passed` |
| `publicSessionStatus` | `passed` |
| `proofReplayStatus` | `blocked` |
| `proofFreshnessStatus` | `stale` |
| `upstreamStatus` | `blocked` (`ahead=9`) |
| `recommendedNextAction.key` | `record-actual-client-proof` |

Expected blockers remain:

| Blocker class | Meaning |
|---|---|
| `git:upstream-not-synced:behind=0:ahead=9` | Local commits are not pushed; push is gated. |
| `ci:missing:.NET build and test` / `ci:missing:RiftReader Policy` | Current-head CI cannot exist until pushed. |
| `proof:replay-failed:*` | Existing actual-client proof is stale and from the older tool/proof contract. |
| `proof:stale` | Actual ChatGPT proof must be refreshed. |

## Actual ChatGPT proof requirements now

Use:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --template --json
```

The proof must now include:

| Field | Required value |
|---|---|
| `toolCount` | `11` |
| `toolNames` | exact 11-tool surface above |
| `toolOutputSchemaCount` | `11` |
| `toolOutputSchemaToolNames` | exact 11-tool surface above |
| `dryRunDiffPreviewOk` | `true` |
| `dryRunDiffPreviewArtifactUnderPackageIntake` | `true` |
| `dryRunDiffPreviewBoundedBytes` | `true` |
| `applyLatestPackageDraftWithoutApprovalBlocked` | `true` |
| `applyLatestPackageDraftWithoutApprovalBlockers` | includes `APPLY_APPROVAL_MISSING` |
| `applyLatestPackageDraftWithoutApprovalApplied` | `false` |

## Safety boundaries preserved

| Boundary | State |
|---|---:|
| Public tunnel | Not started |
| ChatGPT registration | Not performed |
| Persistent MCP server | Not left running |
| Git push | Not performed |
| Git stage/commit from MCP | Not exposed |
| Arbitrary shell endpoint | Not exposed |
| Live RIFT input | Not sent |
| CE/x64dbg | Not used |
| Provider repo writes | Not performed |
| Proof/current-truth promotion | Not performed |

## Separate non-MCP blocker

The repo decision packet is still in the proof-recovery lane with
`latest-static-owner-readback-root-pointer-null`. Its safe next action is:

```cmd
python .\scripts\postupdate_owner_root_rediscovery.py --json
```

That command was already run earlier in this session and produced the same safe
blocker, so it was not looped again. This does not invalidate the local ChatGPT
MCP Stage 20 work; it blocks live navigation/proof recovery separately.

## Exact resume commands

```cmd
git status --short --branch
git --no-pager log --oneline -20
scripts\riftreader-mcp-final.cmd --status --compact-json
scripts\riftreader-chatgpt-trial-recorder.cmd --template --json
scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json
scripts\riftreader-decision-packet.cmd --compact-json --write
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Approve push of `main` when ready | Current HEAD is ahead of origin; CI requires remote visibility. |
| 2 | Run fresh actual ChatGPT Web/Desktop MCP proof with the 11-tool template | This is the primary remaining MCP final gate. |
| 3 | In ChatGPT, verify `apply_latest_package_draft` exists in tools/output schemas | Confirms ChatGPT sees Stage 20, not the old 10-tool surface. |
| 4 | In ChatGPT, call `apply_latest_package_draft` without `approvalToken` | Proves Stage 21 fail-closed behavior from the actual client. |
| 5 | Record proof immediately with `--record --input <proof.json> --json` | Makes the external ChatGPT proof replayable locally. |
| 6 | Rerun `scripts\riftreader-mcp-final.cmd --status --compact-json` after proof and CI | Confirms remaining MCP blockers clear. |
| 7 | Keep approved apply separate from proof-denial smoke | Denial proof is safe; real approved apply is a repo mutation and needs explicit operator approval. |
| 8 | Update release handoff after actual proof passes | Captures final Stage 21/22 truth for future sessions. |
| 9 | Do not run live RIFT/root rediscovery loops unless the proof-recovery lane is the selected focus | Avoids mixing MCP product work with high-risk live-navigation recovery. |
| 10 | Keep using local readiness before any external ChatGPT trial | It cheaply proves the 11-tool surface and apply-denial safety before spending an ephemeral session. |
