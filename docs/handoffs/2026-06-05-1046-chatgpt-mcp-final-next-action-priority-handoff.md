# RiftReader Handoff — ChatGPT MCP Final Next-Action Priority — 2026-06-05 10:46 UTC

## Verdict

**Status:** safe local MCP workflow-routing slice complete and locally validated.

The final readiness gate now chooses specific actionable blockers before generic
wrapper blockers. Proof replay failures now route operators directly to the
actual-client proof template instead of stopping at generic `phase2:not-ready`,
and upstream-sync-only failures route to a non-mutating status command that asks
for push approval rather than implying an automated push.

## What changed

| Area | Current truth |
|---|---|
| Final next-action priority | Dirty worktree still wins first; then specific dependency/environment/safety/public-session/artifact/proof/CI/upstream blockers; generic Phase 2 is last. |
| Proof blocker routing | `proof:*` blockers recommend `record-actual-client-proof` with `scripts/riftreader-chatgpt-trial-recorder.cmd --template --json`. |
| Upstream blocker routing | `git:upstream-not-synced:*` recommends `request-push-approval` with `git --no-pager status --short --branch`; no push command is emitted. |
| Docs | `docs/workflow/riftreader-chatgpt-mcp-final-readiness.md` documents the priority-based next-action mapping. |

## Files changed

| File | Purpose |
|---|---|
| `tools/riftreader_workflow/mcp_final_readiness.py` | Made `_next_action` priority-based and added an explicit non-mutating upstream-sync recommendation. |
| `scripts/test_mcp_final_readiness.py` | Added coverage for proof-over-phase2/CI priority and upstream-sync-only recommendation. |
| `docs/workflow/riftreader-chatgpt-mcp-final-readiness.md` | Updated recommended next-action mapping and priority semantics. |

## Validation

| Check | Result |
|---|---|
| Focused final-routing tests | `python -m unittest scripts.test_mcp_final_readiness scripts.test_mcp_phase2_status scripts.test_mcp_phase1_completion scripts.test_mcp_mission_control scripts.test_workflow_router` passed 51 tests in 11.650s. |
| Python compile | `python -m py_compile tools/riftreader_workflow/mcp_final_readiness.py` passed. |
| Dirty-tree compact final gate | `scripts/riftreader-mcp-final.cmd --status --compact-json` correctly recommended `safe-commit-plan` while this slice was dirty. |
| Broad MCP validation | `python -m unittest scripts.test_mcp_final_readiness scripts.test_mcp_phase1_completion scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 181 tests in 46.618s. |
| Final ledger | `.riftreader-local/validation-runs/20260605-104515-615980/summary.md` passed in 46.777s. |

## Current blockers / not done

| Blocker | Meaning | Safe next action |
|---|---|---|
| Stale actual-client proof | Latest ignored proof predates Secure Tunnel/current proof rules. | Record fresh ChatGPT Web/Desktop proof using `scripts/riftreader-chatgpt-trial-recorder.cmd --template --json`. |
| Current-head CI missing | Local branch is ahead of origin, so GitHub Actions do not cover HEAD. | Push only after explicit approval, then wait for `.NET build and test` and `RiftReader Policy`. |
| Final readiness upstream sync | Branch remains ahead of origin. | Do not claim final ready until approved push + CI success. |
| Live Secure Tunnel / ChatGPT connector proof | Not performed in this safe local slice. | Requires explicit operator action/approval to run `tunnel-client run` and connect ChatGPT. |

## Resume command

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-mcp-final.cmd --status --compact-json
```

After this slice is committed, expected current local result should recommend
`record-actual-client-proof` until a fresh Secure Tunnel-mode proof exists.
