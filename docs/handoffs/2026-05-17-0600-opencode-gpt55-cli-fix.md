# Compact handoff — OpenCode CLI GPT-5.5 model mismatch fixed

Created: 2026-05-17 06:00 EDT
Branch: `main`
Scope: OpenCode / non-Codex desktop ChatGPT bridge model/provider mismatch.

## TL;DR

The local OpenCode mismatch was a stale CLI install, not a missing GPT-5.5 provider/model. The npm CLI shim was upgraded from `opencode-ai@1.4.3` to `opencode-ai@1.15.3`, matching the desktop app generation. `opencode models openai` now lists `openai/gpt-5.5`, and `opencode run --dir . -m openai/gpt-5.5 "Say only: provider works"` succeeds.

Repo wrappers now request an explicit model through `RIFTREADER_OPENCODE_MODEL`, defaulting to `openai/gpt-5.5`, so they no longer inherit a broken user/global default. The deterministic status packet reports OpenCode version, requested model, provider, and model visibility.

Follow-up local default fix: bare `opencode run --dir . "Say only: default works"` also succeeds after adding top-level `model` / `small_model` keys to the user-level OpenCode config with a timestamped local backup. Do not paste or publish the full user config because it may contain MCP headers or provider secrets.

## Root cause

| Finding | Evidence |
|---|---|
| Desktop OpenCode saw GPT-5.5 | Desktop app UI showed OpenAI `GPT-5.5` connected/selected. |
| CLI was stale | Before fix, `opencode --version` returned `1.4.3` and `opencode models openai` stopped at GPT-5.4. |
| Current CLI package exists | `npm view opencode-ai version` returned `1.15.3`. |
| After upgrade, model is visible | `opencode --version` returns `1.15.3`; `opencode models openai` lists `openai/gpt-5.5`, `openai/gpt-5.5-fast`, and `openai/gpt-5.5-pro`. |
| Provider works with explicit model | `opencode run --dir . -m openai/gpt-5.5 "Say only: provider works"` prints `provider works`. |
| Bare default now works | `opencode run --dir . "Say only: default works"` prints `default works`. |

## Repo changes in this milestone

| File | Change |
|---|---|
| `.opencode/opencode.example.jsonc` | Added explicit `model` / `small_model` defaults and allowed safe model-list commands. |
| `scripts/riftreader-opencode-sitrep.cmd` | Uses `%RIFTREADER_OPENCODE_MODEL%`, default `openai/gpt-5.5`, and includes model visibility in the prompt. |
| `scripts/riftreader-opencode-package-review.cmd` | Same explicit model default for package-review runs. |
| `scripts/riftreader-opencode-live-observer.cmd` | Same explicit model default for live-observer runs. |
| `tools/riftreader_workflow/status_packet.py` | Added deterministic OpenCode model/provider visibility checks. |
| `scripts/test_opencode_status_packet.py` | Added tests for model helper parsing and compact model fields. |
| `docs/workflow/opencode-non-codex-bridge.md` | Added model/provider sanity-check commands and stale CLI diagnosis. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Noted explicit wrapper model default and override path. |

## Validation

| Command | Result |
|---|---|
| `npm install -g opencode-ai@latest` | Passed; CLI package updated to `1.15.3`. |
| `opencode --version` | `1.15.3`. |
| `opencode models openai` | Lists `openai/gpt-5.5`, `openai/gpt-5.5-fast`, `openai/gpt-5.5-pro`. |
| `opencode run --dir . -m openai/gpt-5.5 "Say only: provider works"` | Passed; prints `provider works`. |
| `opencode run --dir . "Say only: default works"` | Passed after user-level config default model was set. |
| `scripts\riftreader-opencode-sitrep.cmd` | Passed; uses `openai/gpt-5.5`, runs the status helper, summarizes model visibility and stale-proof blocker. |
| `python -m compileall tools\riftreader_workflow scripts\test_opencode_status_packet.py` | Passed. |
| `python -m unittest scripts.test_opencode_status_packet` | Passed; 10 tests. |
| `scripts\riftreader-workflow-status.cmd --compact-json` | Completed with expected safe blocker; reports `modelVisible: true`. |
| `git --no-pager diff --check` | Passed. |

## Current live/safety status

| Item | Current value |
|---|---|
| Live RIFT PID | `22304` |
| Historical proof PID/HWND | `27552` / `0x3411E2` |
| Live target verdict | `artifact-pid-stale` |
| Proof status | `blocked-target-drift` |
| Movement | Blocked; no input/movement/reload/debugger was sent. |

## Resume prompt

```text
Resume the RiftReader OpenCode / non-Codex bridge after the GPT-5.5 CLI mismatch fix. Start by running `scripts\riftreader-workflow-status.cmd --compact-json`, confirm `opencode.version` is `1.15.3` and `opencode.modelVisible` is true for `openai/gpt-5.5`, then continue the next safe OpenCode/non-Codex slice. Do not send live input, move, attach CE/x64dbg, or reuse stale PID 27552 / HWND 0x3411E2 proof as current truth.
```
