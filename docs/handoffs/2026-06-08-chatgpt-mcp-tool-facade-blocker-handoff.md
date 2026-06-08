# ChatGPT MCP tool-facade blocker handoff

## Verdict

Actual ChatGPT Web/Desktop proof is now past route/registration/schema discovery,
but still blocked because ChatGPT reported the package-loop tools as unavailable
through its callable tool facade.

This is not a Caddy/router issue. The active public route remains:

| Field | Value |
|---|---|
| Connection mode | Cloudflare named Tunnel |
| Public MCP URL | `https://mcp.360madden.com/mcp` |
| ChatGPT auth | No Authentication |
| Expected tool profile | `full` |
| Expected tool count | 12 |

## New evidence from actual ChatGPT

Operator-supplied ChatGPT-side facts:

| Fact | Status |
|---|---|
| ChatGPT app registration | Passed |
| Public URL | `https://mcp.360madden.com/mcp` |
| Tool count observed | 12 |
| Tool output schemas observed | 12 |
| Read tools called | `health`, `get_repo_status`, `get_latest_handoff`, `get_workflow_control_summary`, `get_workflow_control_plan` |
| Package-loop tools callable | Blocked by ChatGPT facade |

Facade blockers reported by ChatGPT:

```text
TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:get_package_proposal_template
TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:submit_package_proposal
TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:list_inbox
TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:create_package_draft_from_inbox
TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:review_latest_package_draft
TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:dry_run_latest_package_draft
TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:apply_latest_package_draft
```

## Patch applied in this slice

| File | Change |
|---|---|
| `tools/riftreader_workflow/riftreader_chatgpt_mcp.py` | Added `PACKAGE_PROOF_TOOL_ORDER`, surfaced package-proof recovery guidance in `health` and compact workflow summary, and moved the package-loop sequence into FastMCP server instructions so ChatGPT sees it during initialization. |
| `tools/riftreader_workflow/chatgpt_trial_recorder.py` | Detects `TOOL_NOT_AVAILABLE_IN_CHATGPT_TOOL_FACADE:*` proof blockers and reports a direct `chatgpt-tool-facade-unavailable:*` blocker. |
| `scripts/test_riftreader_chatgpt_mcp.py` | Covers new health/summary package-proof guidance. |
| `scripts/test_chatgpt_trial_recorder.py` | Covers direct facade-unavailable blocker reporting. |

## Current local validation

| Command | Result |
|---|---|
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder` | Passed: 97 tests |
| `python -m unittest scripts.test_riftreader_chatgpt_mcp scripts.test_chatgpt_trial_recorder scripts.test_mcp_proof_replay scripts.test_mcp_final_readiness scripts.test_mcp_workflow_state scripts.test_mcp_mission_control scripts.test_workflow_router scripts.test_mcp_phase2_status scripts.test_local_artifact_bridge scripts.test_package_draft_review` | Passed: 219 tests in 37.216s |
| `python -m py_compile tools\riftreader_workflow\riftreader_chatgpt_mcp.py tools\riftreader_workflow\chatgpt_trial_recorder.py scripts\test_riftreader_chatgpt_mcp.py scripts\test_chatgpt_trial_recorder.py` | Passed |
| `python tools\riftreader_workflow\chatgpt_trial_recorder.py --check-latest-template --json` | Blocked, now with explicit `chatgpt-tool-facade-unavailable:*` blocker |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call get_workflow_control_summary --json` | Passed and includes `actualClientProofRecovery` |

## Next actual ChatGPT prompt

Use this in a fresh ChatGPT Web/Desktop chat after opening the app selector and
selecting Developer Mode / `rift-mcp`:

```text
Use only the rift-mcp Developer Mode app. Do not use built-in browsing or any
other connector. Call these rift-mcp tools in this exact order:
1. get_package_proposal_template
2. submit_package_proposal with one tiny harmless package-proposal
3. list_inbox
4. create_package_draft_from_inbox using the returned inboxId
5. review_latest_package_draft
6. dry_run_latest_package_draft
7. apply_latest_package_draft without approvalToken

If any tool is unavailable, stop and report the exact unavailable tool name.
Do not treat health.tools as proof that a tool was actually callable.
```

If ChatGPT still reports package tools unavailable, the next likely fix is in
ChatGPT app settings/tool enablement or the developer-mode app refresh/cache
path, not the public Cloudflare route.

