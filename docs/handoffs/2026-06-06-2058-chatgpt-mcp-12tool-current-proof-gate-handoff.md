# ChatGPT Web/Desktop MCP 12-tool current proof gate handoff

Generated: `2026-06-06T20:58:00-04:00` (`2026-06-07T00:58:00Z`)

## ✅ Current result

The ChatGPT Web/Desktop MCP lane is now aligned to the current **12-tool**
manual external-IP proof contract. Fresh proof-input templates are required to
match the active manual-public-IP shape before Phase 1/final gates recommend
checking them; stale 11-tool or Secure Tunnel-mode templates now route back to
writing a current template instead of wasting an operator pass on obsolete
proof input.

| Area | Current truth |
|---|---|
| Current pre-slice HEAD | `7b01345de8c779661c762387a7f08e6701f9519e` (`Add compact ChatGPT MCP workflow summary`). |
| Active ChatGPT route | Manual external-IP ChatGPT `Server URL` with `No Authentication`; Secure Tunnel and Cloudflare remain retired for this lane. |
| Tool contract | 12 tools: includes `get_workflow_control_summary` and gated `apply_latest_package_draft`. |
| New proof template | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-005424Z\proof-input.json`. |
| Manual public-IP plan | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260607T005441Z-manual-public-ip-plan.json`. |
| Trial readiness refresh | `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260607T005601Z-trial-readiness.json` passed locally. |
| Safety posture | No public tunnel, ChatGPT registration, approved package apply, Git push, RIFT input, CE/x64dbg, or provider writes were performed while creating this handoff. |

## What changed in this slice

| File | Change |
|---|---|
| `tools/riftreader_workflow/mcp_workflow_state.py` | `proof_input_template_check_command` now only recommends checking a fresh template when it matches current manual-public-IP / 12-tool shape and includes the current required tool additions. |
| `scripts/test_mcp_final_readiness.py` | Added coverage that current templates are checkable, while old Secure Tunnel / 11-tool templates fall back to `--write-template`. |
| `docs/workflow/riftreader-chatgpt-mcp.md` | Documented the `'python' is not recognized` wrapper failure mode and explicit-Python diagnostic fallback. |
| `docs/HANDOFF.md` | Re-entry pointer updated to this current 12-tool proof-gate handoff. |

## Current proof/operator path

| Step | Command / action | Status |
|---:|---|---|
| 1 | `scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json` | Done; fresh 12-tool template written. |
| 2 | `scripts\riftreader-chatgpt-trial-recorder.cmd --check-latest-template --json` | Blocked as expected until real ChatGPT observations fill the template. |
| 3 | `scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host 173.54.133.37 --json` | Done; plan-only artifact written. |
| 4 | Operator starts loopback MCP server and HTTPS reverse proxy outside Codex. | Not performed here. |
| 5 | Operator configures ChatGPT custom MCP app Server URL as `https://173.54.133.37/mcp` with `No Authentication`. | Not performed here. |
| 6 | Operator fills the fresh proof input from actual ChatGPT observations, then runs the emitted record command. | Blocked on external ChatGPT proof. |

## Local validation so far

| Command | Result |
|---|---|
| `cmd /c scripts\riftreader-chatgpt-mcp.cmd --self-test --json` | Passed after running through the normal CMD wrapper/PATH environment. |
| `cmd /c scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json` | Passed; wrote fresh 12-tool template. |
| `cmd /c scripts\riftreader-chatgpt-trial-recorder.cmd --check-latest-template --json` | Blocked as expected on unfilled operator facts, not on stale 11-tool/Secure Tunnel shape. |
| `cmd /c scripts\riftreader-chatgpt-mcp.cmd --manual-public-ip-plan --public-mcp-host 173.54.133.37 --json` | Passed; plan-only artifact written. |
| `cmd /c scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json` | Passed; local self-test/SDK/loopback proposal transport smoke covered 12 tools and unapproved apply denial. |
| `python -m py_compile <touched workflow modules/tests>` | Passed. |
| `python -m unittest scripts.test_mcp_workflow_state scripts.test_mcp_final_readiness scripts.test_mcp_phase1_completion scripts.test_chatgpt_trial_recorder scripts.test_riftreader_chatgpt_mcp` | Passed: 129 tests in 15.192s. |
| `python -m ruff check tools\riftreader_workflow\mcp_workflow_state.py scripts\test_mcp_final_readiness.py docs\workflow\riftreader-chatgpt-mcp.md` | Passed. |

## Remaining blockers

| Blocker | Why it remains |
|---|---|
| Current-head CI / upstream sync | The branch was still ahead of origin before this handoff slice; push/CI are separate final publication steps. |
| Actual ChatGPT proof | Requires an operator-owned MCP server + HTTPS reverse proxy + ChatGPT custom MCP app observations. Codex did not register ChatGPT or expose a public endpoint here. |
| Proof-input check | The fresh template is intentionally blocked until real ChatGPT observations fill fields such as `publicMcpUrl`, output-schema confirmation, draft/review/dry-run proof, and unapproved apply denial proof. |

## Next safe action

Finish local validation (`git diff --check`, policy lint, targeted/broad MCP tests), commit this handoff/routing slice, then push and wait for current-head CI if operator authorization remains active.
