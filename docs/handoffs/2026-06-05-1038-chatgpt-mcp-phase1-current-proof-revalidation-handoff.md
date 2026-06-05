# RiftReader Handoff — ChatGPT MCP Phase 1 Current-Proof Revalidation — 2026-06-05 10:38 UTC

## Verdict

**Status:** safe local MCP gate-hardening slice complete and locally validated.

The Phase 1 MCP completion gate now revalidates the latest actual-client proof
against the current proof recorder rules instead of trusting a historical
`status=passed` proof artifact. This prevents stale ChatGPT/Cloudflare-era proof
from making Phase 1 look complete after the Secure Tunnel and diff-preview proof
contract changed.

## What changed

| Area | Current truth |
|---|---|
| Phase 1 actual-client proof check | Reloads the latest `proof.json` and applies `chatgpt_trial_recorder.validate_proof()`. |
| Legacy proof behavior | A saved artifact with `status=passed` now blocks if its embedded proof lacks current required fields such as `connectionMode`, draft review, or bounded `dryRun.diffPreview`. |
| Operator output | Actual-client proof check blockers are surfaced as `actual-client-proof-invalid:<rule>`. |
| Documentation | `docs/workflow/riftreader-chatgpt-mcp.md` now states that Phase 1 requires current proof-rule revalidation, not just historical artifact status. |

## Files changed

| File | Purpose |
|---|---|
| `tools/riftreader_workflow/mcp_phase1_completion.py` | Added current proof-rule validation for the actual-client proof check and surfaced `connectionMode` in Phase 1 check entries. |
| `scripts/test_mcp_phase1_completion.py` | Updated valid proof fixture to the Secure Tunnel proof contract and added regression coverage for legacy passed proof blocking. |
| `docs/workflow/riftreader-chatgpt-mcp.md` | Documented that Phase 1 revalidates actual-client proof against current rules. |

## Validation

| Check | Result |
|---|---|
| Focused gate tests | `python -m unittest scripts.test_mcp_phase1_completion scripts.test_mcp_phase2_status scripts.test_mcp_final_readiness scripts.test_mcp_workflow_state` passed 41 tests in 8.659s. |
| Python compile | `python -m py_compile tools/riftreader_workflow/mcp_phase1_completion.py` passed. |
| Live local Phase 1 status | `scripts/riftreader-mcp-phase1.cmd --status --json` blocked as expected on stale proof with `actual-client-proof-invalid:required-field-missing:connectionMode`. |
| Broad MCP validation | `python -m unittest scripts.test_mcp_phase1_completion scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 179 tests in 48.076s. |
| Final ledger | `.riftreader-local/validation-runs/20260605-103641-064539/summary.md` passed in 46.529s. |

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
.\scripts\riftreader-mcp-phase1.cmd --status --json
```

Expected current local result: blocked on stale proof until a fresh Secure
Tunnel-mode actual-client proof is recorded.
