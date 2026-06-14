# 2026-06-14 - ChatGPT proof-mode label refreshed for 19-tool surface

## Current lane

MCP / actual-client proof recorder maintenance lane. This is not a live RIFT input,
movement, CE, x64dbg, provider-write, public-tunnel start, ChatGPT API, or Git-push
lane.

## Local result

| Item | Current truth |
|---|---|
| Base HEAD | `a49038f Support region-pinned string scans`. |
| Problem | Fresh final proof templates still labeled the full surface as `final-12-tool` even though the expected ChatGPT MCP surface is now 19 tools. |
| Fix | Final proof-mode label now derives from `EXPECTED_CHATGPT_MCP_TOOL_COUNT`, producing `final-19-tool` for the current surface. |
| Compatibility | `FINAL_12_TOOL_PROOF_MODE` remains as an import alias, and existing final-proof validation remains count-driven to avoid invalidating historical proof JSON solely by label. |
| Fresh template | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260614-100749Z\proof-input.json` was generated with `proofMode=final-19-tool` and `toolCount=19`. |
| Scope | Trial-recorder template/label/test behavior only; no actual ChatGPT proof was recorded. |

## Files changed by this slice

- `tools/riftreader_workflow/chatgpt_trial_recorder.py`
- `scripts/test_chatgpt_trial_recorder.py`
- `docs/HANDOFF.md`
- `docs/handoffs/2026-06-14-chatgpt-proof-mode-label-handoff.md`

## Validation evidence

| Check | Result |
|---|---|
| py_compile | Passed: `python -m py_compile tools\riftreader_workflow\chatgpt_trial_recorder.py scripts\test_chatgpt_trial_recorder.py`. |
| Focused tests | Passed: `python -m unittest scripts.test_chatgpt_trial_recorder scripts.test_mcp_final_readiness` (`57` tests). |
| Template print smoke | Passed: `scripts\riftreader-chatgpt-trial-recorder.cmd --template --json`; emitted `proofMode=final-19-tool`. |
| Template write smoke | Passed: `scripts\riftreader-chatgpt-trial-recorder.cmd --write-template --json`; wrote the fresh ignored template listed above. |

## Remaining blockers / gates

| Gate | State |
|---|---|
| Actual ChatGPT proof | Still stale until an operator fills/checks/records a fresh 19-tool actual-client proof input. |
| Final readiness | Still blocked until proof replay is fresh and current-head CI passes. |
| Git push | Not authorized by this handoff. |
| Live RIFT / movement / desktop input | Not authorized by this handoff. |
| CE / x64dbg | Not authorized by this handoff. |
| Provider writes | Not authorized by this handoff. |

## Exact next action

Run pre-commit on the explicit trial-recorder/test/handoff paths, commit this
label-refresh slice locally if it passes, then use the fresh template for actual
ChatGPT-side proof collection:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260614-100749Z\proof-input.json --json
```
