# RiftReader Handoff — ChatGPT MCP Secure Tunnel Proof Template — 2026-06-05 10:22 UTC

## Verdict

**Status:** safe local MCP workflow slice complete and locally validated.

The RiftReader ChatGPT Web/Desktop MCP actual-client proof path is now explicitly
OpenAI Secure MCP Tunnel-first. The proof template and replay summary expose
`connectionMode`, and proof validation fails closed if Secure Tunnel-mode proof
uses a public fallback host such as Cloudflare or ngrok.

## What changed

| Area | Current truth |
|---|---|
| Primary ChatGPT path | `connectionMode=openai-secure-mcp-tunnel`. |
| Fallback path | `connectionMode=public-https-fallback`, only when the operator explicitly chooses the deprecated public HTTPS fallback lane. |
| Proof URL safety | `publicMcpUrl` must be HTTPS, must not be an unfilled placeholder, and cannot contain `trycloudflare.com`, `ngrok.app`, or `ngrok-free.app` while in Secure Tunnel mode. |
| Proof template | `scripts/riftreader-chatgpt-trial-recorder.cmd --template --json` now emits Secure Tunnel-first defaults instead of a Cloudflare placeholder. |
| Proof replay | `tools/riftreader_workflow/mcp_proof_replay.py` includes `connectionMode` in `proofSummary` for operator/debug visibility. |
| Artifact state browser | `tools/riftreader_workflow/mcp_workflow_state.py` surfaces `connectionMode` for actual-client proof artifacts. |
| Docs | `docs/workflow/riftreader-chatgpt-mcp.md` and `docs/workflow/riftreader-chatgpt-mcp-final-readiness.md` now document Secure Tunnel proof rules and the ten-tool allowlist. |

## Files changed

| File | Purpose |
|---|---|
| `tools/riftreader_workflow/chatgpt_trial_recorder.py` | Added required `connectionMode`, allowed-mode validation, Secure Tunnel fallback-host blocker, placeholder URL blocker, and Markdown rendering. |
| `tools/riftreader_workflow/mcp_proof_replay.py` | Added `connectionMode` replay summary and Secure Tunnel-first self-test proof shape. |
| `tools/riftreader_workflow/mcp_workflow_state.py` | Added `connectionMode` to summarized artifacts. |
| `scripts/test_chatgpt_trial_recorder.py` | Added Secure Tunnel default, fallback-host, fallback-mode, invalid-mode, and placeholder tests. |
| `scripts/test_mcp_proof_replay.py` | Updated valid proof fixture to Secure Tunnel-first. |
| `scripts/test_mcp_phase2_status.py` | Updated valid proof fixture to Secure Tunnel-first. |
| `scripts/test_mcp_workflow_state.py` | Added `connectionMode` artifact summary assertion. |
| `docs/workflow/riftreader-chatgpt-mcp.md` | Documented actual-client proof `connectionMode` rules and fixed tool count wording. |
| `docs/workflow/riftreader-chatgpt-mcp-final-readiness.md` | Updated final readiness proof criteria for Secure Tunnel mode. |

## Validation

| Check | Result |
|---|---|
| Focused proof/workflow tests | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state` passed 27 tests in 6.132s. |
| Python compile | `python -m py_compile tools/riftreader_workflow/chatgpt_trial_recorder.py tools/riftreader_workflow/mcp_proof_replay.py tools/riftreader_workflow/mcp_workflow_state.py` passed. |
| Trial recorder template | `scripts/riftreader-chatgpt-trial-recorder.cmd --template --json` passed and emitted `connectionMode=openai-secure-mcp-tunnel`. |
| Trial recorder self-test | `scripts/riftreader-chatgpt-trial-recorder.cmd --self-test --json` passed. |
| Proof replay self-test | `python tools/riftreader_workflow/mcp_proof_replay.py --self-test --json` passed. |
| Broad MCP suite | `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_phase2_status scripts.test_mcp_workflow_state scripts.test_mcp_phase1_completion scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_final_readiness scripts.test_riftreader_chatgpt_mcp scripts.test_local_artifact_bridge scripts.test_package_draft_review` passed 178 tests in 47.060s. |
| Timestamped ledger | `.riftreader-local/validation-runs/20260605-102706-854015/summary.md` passed in 47.278s. |
| Phase 2 status | Still blocked as expected on stale old actual-client proof missing `connectionMode`/new proof fields and missing current-head CI for the unpushed local HEAD. |

## Current blockers / not done

| Blocker | Meaning | Safe next action |
|---|---|---|
| Stale external actual-client proof | Existing ignored proof was recorded before the Secure Tunnel/diff-preview contract and now fails replay with `required-field-missing:connectionMode` plus other proof gaps. | Record a fresh ChatGPT Web/Desktop proof through OpenAI Secure MCP Tunnel using the current template. |
| Current-head CI missing | Local branch is ahead of origin, so GitHub Actions do not have runs for current local HEAD. | Push only after explicit approval, then wait for `.NET build and test` and `RiftReader Policy`. |
| Final readiness upstream sync | Branch remains ahead of origin. | Do not claim final ready until approved push + CI success. |
| Live connector/tunnel operation | Not performed in this safe local slice. | Requires explicit operator action/approval to run `tunnel-client run` and connect ChatGPT. |

## Resume command

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-chatgpt-trial-recorder.cmd --template --json
```

Then fill the proof from actual ChatGPT Web/Desktop observations with
`connectionMode=openai-secure-mcp-tunnel` and the tunnel-selected connector URL,
not a Cloudflare/ngrok fallback host.
