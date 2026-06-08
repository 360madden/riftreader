# 2026-06-08 — Desktop control command queue contract

## Current truth

| Item | Status |
|---|---|
| New plan-only helper | `scripts\riftreader-desktop-control-queue-contract.cmd --json` prints an inert Browser/Computer command queue contract. |
| Operator Lite | Adds `desktop-control-queue-contract` / `--desktop-control-queue-contract` plus a `Desktop Queue Contract` button in the MCP & Proof tab. |
| Execution state | Disabled. No queue writer, executor, MCP tool, Browser Use automation, Computer Use automation, desktop click/typing, RIFT input, tunnel start, package apply, Git mutation, CE, or x64dbg endpoint exists. |
| Current external blocker | Computer Use still fails before bootstrap/list-app proof with `Computer Use native pipe path is unavailable`. |
| Required next proof | Repair/reconnect the Codex Computer Use plugin/runtime, run only bootstrap/list-apps, then record a success observation with `scripts\riftreader-desktop-control-readiness.cmd --record-observation --browser-dashboard-smoke-ok --computer-use-native-pipe-ok --computer-use-list-apps-ok --computer-use-stage passed --json`. |

## Validation

Passed locally before commit:

- `python -m py_compile tools\riftreader_workflow\desktop_control_queue_contract.py tools\riftreader_workflow\operator_lite.py tools\riftreader_workflow\desktop_control_readiness.py`
- `python -m unittest scripts.test_desktop_control_queue_contract scripts.test_operator_lite scripts.test_desktop_control_readiness`
- `scripts\riftreader-desktop-control-queue-contract.cmd --self-test --json`
- `scripts\riftreader-desktop-control-queue-contract.cmd --json`
- `scripts\riftreader-operator-lite.cmd --desktop-control-queue-contract --json`
- `git --no-pager diff --check`
- `pre-commit run --files docs/HANDOFF.md docs/handoffs/2026-06-08-desktop-control-command-queue-contract-handoff.md docs/workflow/operator-lite.md scripts/riftreader-desktop-control-queue-contract.cmd scripts/test_desktop_control_queue_contract.py scripts/test_operator_lite.py tools/riftreader_workflow/desktop_control_queue_contract.py tools/riftreader_workflow/operator_lite.py --show-diff-on-failure`

## Safety boundaries

- This is a schema/plan contract only.
- It intentionally does not add an executor or expose a new ChatGPT MCP tool.
- Future executor work remains gated on fresh Browser/Computer readiness proof and separate explicit review.
- Live RIFT input, movement/stimulus, proof promotion, CE/x64dbg, provider writes, package apply, and Git mutation remain outside this helper.
