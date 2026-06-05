# ChatGPT Web/Desktop MCP proof-template index handoff

Generated: `2026-06-05T21:09:21Z`

## ✅ Current result

The local ChatGPT Web/Desktop MCP workflow is now aligned around the current
fillable actual-client proof packet instead of stale stdout-only templates or
ad hoc `proof.json` instructions.

| Area | Current truth |
|---|---|
| Tool contract | 11 MCP tools are expected, including gated `apply_latest_package_draft`. |
| Proof template command | `scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json` writes the ignored fillable packet. |
| Proof template artifact kind | `proof-input-template` is indexed by `scripts\riftreader-mcp-artifacts.cmd`. |
| Actual proof record command | The template payload includes the exact `--record --input <proof-input.json> --json` command to run after filling ChatGPT-side observations. |
| Phase 1 recommendation | Missing/stale actual-client proof now routes to `--write-template --json`. |
| Safety posture | No push, no persistent server, no public tunnel start, no ChatGPT registration, no live RIFT input, no CE/x64dbg. |

## Recent commits in this lane

| Commit | Purpose |
|---|---|
| `aa8320a` | Index ignored proof-input templates as first-class MCP artifacts. |
| `9f8d45a` | Add `--write-template` to produce fillable actual-client proof input packets. |
| `5de5891` | Preserve the actual proof checklist handoff. |
| `df35954` | Require full actual-client proof checklist fields in Mission Control. |
| `c6073a4` | Preflight gated apply denial in public MCP trial flows. |
| `0fa7125` | Add gated apply denial to local MCP smoke. |
| `9a1bb3d` | Require apply-denial evidence in ChatGPT proof replay. |
| `4de49e5` | Update proof contract to the 11-tool gated apply surface. |
| `728bdfb` | Expose the gated package-apply MCP tool. |
| `588f337` | Add the local package apply bridge. |

## Current final gate snapshot

Last checked with:

```cmd
scripts\riftreader-mcp-final.cmd --status --compact-json
```

| Field | Result |
|---|---|
| `status` | `blocked` |
| `currentHead` | `80b7498884b15603be351ee3318eb37d5be3407f` after the Phase 1 recommendation alignment commit |
| `gitDirty` | `false` after commit |
| `toolSurfaceStatus` | `passed` |
| `dependencyStatus` | `passed` |
| `environmentStatus` | `passed` |
| `publicSessionStatus` | `passed` (`expected-expired` sessions only) |
| `recommendedNextAction.key` | `record-actual-client-proof` |
| `recommendedNextAction.command` | `scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json` |

## Remaining blockers

| Blocker | Why it remains |
|---|---|
| `git:upstream-not-synced:behind=0:ahead=15` | Local branch has unpushed commits; remote mutation still requires explicit push approval. |
| `phase2:not-ready` | External proof/CI gates are not complete. |
| `ci:missing:.NET build and test` | Current-head CI evidence is absent. |
| `ci:missing:RiftReader Policy` | Current-head policy CI evidence is absent. |
| `proof:replay-failed:*` | Latest recorded actual-client proof is old 8-tool/field-incomplete proof. |
| `proof:stale` | Actual ChatGPT Web/Desktop proof is older than the configured freshness budget. |

## Exact next operator proof path

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json
```

Then fill the emitted `proof-input.json` with actual ChatGPT Web/Desktop
observations and run the emitted `recordCommand`.

## Validation status for this handoff slice

| Command | Result |
|---|---|
| `python -m unittest scripts.test_mcp_phase1_completion scripts.test_mcp_workflow_state scripts.test_chatgpt_trial_recorder scripts.test_mcp_final_readiness` | Passed: 55 tests in 7.500s. |
| `python -m unittest scripts.test_mcp_final_readiness scripts.test_mcp_phase1_completion scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review scripts.test_mcp_artifact_browser` | Passed: 211 tests in 52.440s. |
| `python -m py_compile tools\riftreader_workflow\mcp_phase1_completion.py` | Passed. |
| `git --no-pager diff --check` | Passed. |
| `scripts\riftreader-mcp-phase1.cmd --status --json` | Blocked as expected while dirty; recommended `safe-commit-plan` before proof work. |
| `pre-commit run --all-files --show-diff-on-failure` | Passed. |
| `dotnet restore .\RiftReader.slnx` | Passed. |
| `dotnet build .\RiftReader.slnx --configuration Release --no-restore` | Passed: 0 warnings, 0 errors. |
| `dotnet test .\RiftReader.slnx --configuration Release --no-build --verbosity normal` | Passed: 109 tests. |
| `python -m py_compile <workflow-tools-and-script-tests>` | Passed. |
| `python -m unittest discover -s scripts -p "test_*.py"` | Passed: 1888 tests in 446.708s. |
| `python tools\riftreader_workflow\policy_lint.py --json validate-repo --scope changed --no-write-summary` | Passed: 0 blockers, 0 warnings. |

These local checks are CI-parity confidence only. They do not replace the final
gate requirement for GitHub Actions evidence on the pushed current HEAD.
