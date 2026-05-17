# Compact handoff — OpenCode GPT-5.5 xhigh default

Created: 2026-05-17 09:33 EDT
Branch: `main`
Scope: Set OpenCode defaults for the RiftReader non-Codex bridge to GPT-5.5 extra-high reasoning.

## TL;DR

OpenCode defaults are now `openai/gpt-5.5` with `xhigh` reasoning. The user-level OpenCode config was updated with a timestamped backup, and the repo OpenCode wrappers now pass `--variant xhigh` explicitly so the bridge does not depend on global/default UI state.

## Local OpenCode config update

| Field | Value |
|---|---|
| Config path | `C:\Users\mrkoo\.config\opencode\opencode.json` |
| Backup path | `C:\Users\mrkoo\.config\opencode\opencode.json.backup-20260517-092817` |
| Default model | `openai/gpt-5.5` |
| Small model | `openai/gpt-5.5-fast` |
| OpenAI model option | `provider.openai.models.gpt-5.5.options.reasoningEffort = xhigh` |
| Reasoning summary | `auto` |

Do not paste or publish the full user config because it may contain MCP headers or secrets.

## Repo changes

| File | Change |
|---|---|
| `.opencode/opencode.example.jsonc` | Adds secret-free OpenAI GPT-5.5 `reasoningEffort: xhigh` model options. |
| `scripts/riftreader-opencode-sitrep.cmd` | Defaults `RIFTREADER_OPENCODE_VARIANT=xhigh` and passes `--variant`. |
| `scripts/riftreader-opencode-live-observer.cmd` | Same xhigh variant default. |
| `scripts/riftreader-opencode-package-review.cmd` | Same xhigh variant default. |
| `tools/riftreader_workflow/status_packet.py` | Reports desired OpenCode reasoning variant. |
| `scripts/test_opencode_status_packet.py` | Adds regression coverage for default `xhigh` variant reporting. |
| `docs/workflow/opencode-non-codex-bridge.md` | Documents `RIFTREADER_OPENCODE_VARIANT` and xhigh verification command. |
| `docs/workflow/non-codex-desktop-chatgpt-workflow.md` | Notes wrappers request GPT-5.5 plus xhigh explicitly. |

## Validation

| Command | Result |
|---|---|
| `opencode run --dir . --variant xhigh "Say only: xhigh default works"` | Passed. |
| `opencode run --dir . "Say only: default xhigh configured"` | Passed. |
| `scripts\riftreader-opencode-sitrep.cmd` | Passed; echoed `openai/gpt-5.5 variant: xhigh` and status reported `desiredVariant: xhigh`. |
| `scripts\riftreader-opencode-package-review.cmd <selftest-package>` | Passed dry-run; echoed `openai/gpt-5.5 variant: xhigh`; no apply. |
| `scripts\riftreader-workflow-status.cmd --compact-json` | Expected exit `2`; reports `desiredVariant: xhigh`. |
| `scripts\riftreader-package-intake-selftest.cmd` | Passed dry-run. |
| `python -m compileall tools\riftreader_workflow scripts\test_opencode_status_packet.py scripts\test_live_test_triage.py` | Passed. |
| `python -m unittest scripts.test_opencode_status_packet scripts.test_live_test_triage` | Passed; 16 tests. |
| `git --no-pager diff --check` | Passed. |

## Current proof status

| Field | Value |
|---|---|
| Visible process | `rift_x64` PID `22304` |
| Historical proof PID/HWND | `27552` / `0x3411E2` |
| Proof status | `blocked-target-drift` |
| Movement | Blocked; no input/movement/reload/debugger sent. |

## Resume prompt

```text
Resume RiftReader OpenCode/non-Codex lane after setting OpenCode default to `openai/gpt-5.5` with `xhigh` reasoning. Start with `scripts\riftreader-workflow-status.cmd --compact-json` and confirm `opencode.desiredVariant` is `xhigh`. Keep stale PID `27552` / HWND `0x3411E2` historical only and movement blocked unless current-target proof recovery is explicitly authorized.
```
