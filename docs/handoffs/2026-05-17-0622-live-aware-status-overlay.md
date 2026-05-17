# Compact handoff — live-aware OpenCode status overlay

Created: 2026-05-17 06:22 EDT
Branch: `main`
Scope: OpenCode / non-Codex bridge status clarity while a `rift_x64` process is visible but proof is stale.

## TL;DR

Executed the requested 1-10 safe OpenCode/non-Codex actions. OpenCode GPT-5.5 works, no-input observer works, package review dry-run works, and movement remains blocked. A small status-packet fix now prevents compact SITREPs from saying `No live rift_x64 process is available` when a process PID is detected but the proof artifact belongs to a historical PID/HWND.

## Current live/proof truth

| Field | Value |
|---|---|
| Live RIFT PID | `22304` |
| Historical proof PID/HWND | `27552` / `0x3411E2` |
| Live target verdict | `artifact-pid-stale` |
| Current proof | `blocked-target-drift` |
| Movement | Blocked; no input/movement/reload/debugger was sent. |
| OpenCode model | `openai/gpt-5.5`, visible under OpenCode CLI `1.15.3` |

## Change made

| File | Change |
|---|---|
| `tools/riftreader_workflow/status_packet.py` | Adds live-target stale overlay: movement reason now says a live PID exists but artifact PID/HWND is historical; superseded offline blockers move to warnings; explicit `live-target-artifact-pid-stale` blocker is added. |
| `scripts/test_opencode_status_packet.py` | Adds assertions for live-aware movement reason, filtered offline blocker, and explicit stale-artifact blocker. |

## Validation

| Command | Result |
|---|---|
| `scripts\riftreader-opencode-live-observer.cmd` | Passed wrapper execution; reports safe `artifact-pid-stale` blocker. |
| `scripts\riftreader-workflow-status.cmd --compact-json --write` | Expected exit `2` blocker; now reports live-aware movement reason. |
| `scripts\riftreader-live-triage.cmd --json` | Expected exit `2`; reports live PID `22304` and stale artifact PID `27552`. |
| `scripts\riftreader-package-intake-selftest.cmd` | Passed dry-run; no target writes. |
| `scripts\riftreader-opencode-package-review.cmd <selftest-package>` | Passed dry-run review; no apply. |
| `scripts\riftreader-operator-lite.cmd --self-test --json` | Passed. |
| `python .\scripts\validate_current_truth.py --json` | Passed. |
| `python .\scripts\coordinate_recovery_status.py --json` | Expected exit `2`; `artifact-target-pid-not-running:artifact=27552;live=22304`. |
| `python -m compileall tools\riftreader_workflow scripts\test_opencode_status_packet.py scripts\test_live_test_triage.py` | Passed. |
| `python -m unittest scripts.test_opencode_status_packet scripts.test_live_test_triage` | Passed; 16 tests. |

## Resume prompt

```text
Resume RiftReader OpenCode/non-Codex lane after the live-aware status overlay. Start with `scripts\riftreader-workflow-status.cmd --compact-json`; expect RIFT live PID `22304`, stale artifact PID `27552` / HWND `0x3411E2`, and movement blocked. Continue only no-input current-target reacquisition/status-refresh work unless explicitly authorized for live input, movement, CE/x64dbg, or proof promotion.
```
