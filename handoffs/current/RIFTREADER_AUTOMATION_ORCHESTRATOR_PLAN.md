<!--
Version: riftreader-automation-orchestrator-plan-v0.1.0
Purpose: Durable plan for automating the RiftReader bridge/snapshot/recovery workflow so progress survives closed windows, lost processes, and chat restarts.
-->

# RiftReader Automation Orchestrator Plan v0.1

Created: 2026-06-03
Repo: `360madden/riftreader`
Local path: `C:\RIFT MODDING\RiftReader`
Current source of truth: GitHub `main` + local repo execution
Current durable transport: `chatgpt/snapshot` branch

## Current verified state

1. `main` contains the one-window bridge/tunnel helper:
   - `tools/riftreader_workflow/bridge_tunnel_session.py`
   - `scripts/riftreader-bridge-tunnel-session.cmd`
   - `scripts/test_bridge_tunnel_session.py`
   - `docs/workflow/bridge-tunnel-session.md`
2. `main` contains the ChatGPT snapshot publisher:
   - `tools/riftreader_workflow/chatgpt_snapshot_publisher.py`
   - `scripts/riftreader-publish-chatgpt-snapshot.cmd`
   - `scripts/test_chatgpt_snapshot_publisher.py`
   - `docs/workflow/chatgpt-snapshot-publisher.md`
3. The bridge/tunnel URL works from the operator PC and phone, but Desktop ChatGPT fetch to `trycloudflare.com` is unreliable.
4. The working durable handoff path is:
   ```text
   local bridge payload
   -> localhost snapshot capture
   -> push snapshot to chatgpt/snapshot
   -> ChatGPT reads snapshot through GitHub connector
   ```
5. Fresh snapshot publish was verified on `chatgpt/snapshot` with:
   - `/chatgpt-handoff.json`: `ok`
   - `/health`: `ok`
   - `/payloads/latest/readme.md`: `ok`
   - `/payloads/latest/chunks.json`: `ok`
   - selected chunks: `desktop-chatgpt-workflow`, `local-artifact-bridge-docs`, `repo-status`

## Problem to solve

The workflow still requires too many manual steps and is fragile if a window is closed.

Current weak points:

```text
- operator has to remember which window is bridge/tunnel
- bridge/tunnel token and process state are ephemeral
- stale payload vs fresh payload can be confusing
- a closed window loses the active tunnel/session
- recovery payload generation is not yet chained to snapshot publish
- current state is not always written to a durable handoff before proceeding
```

## Goal

Build a repo-owned automation layer that makes the safest common workflows one-command and recoverable.

Target operator experience:

```powershell
.\scripts\riftreader-workflow.cmd --lane snapshot-refresh --push
.\scripts\riftreader-workflow.cmd --lane repo-status-snapshot --push
.\scripts\riftreader-workflow.cmd --lane recovery-payload-snapshot --push
```

The helper should print the exact next action and write durable JSON/Markdown state before any risky or long-running stage.

## Proposed files for Workflow Orchestrator v0.1

```text
tools/riftreader_workflow/workflow_orchestrator.py
scripts/riftreader-workflow.cmd
scripts/test_workflow_orchestrator.py
docs/workflow/workflow-orchestrator.md
```

## Lane 1: `snapshot-refresh`

Purpose: refresh the current ChatGPT-readable snapshot with as little operator work as possible.

Steps:

1. Verify repo root.
2. Verify current branch and HEAD.
3. Verify local helper files exist.
4. Detect existing bridge session from `.riftreader-local/bridge-one-tab`.
5. If bridge is running and healthy, reuse it.
6. If not running, start bridge/tunnel session in managed mode if supported.
7. Capture fixed localhost bridge endpoints.
8. Write:
   ```text
   handoffs/current/RIFTREADER_CHATGPT_SNAPSHOT.md
   handoffs/current/RIFTREADER_CHATGPT_SNAPSHOT.json
   ```
9. Push only snapshot files to:
   ```text
   chatgpt/snapshot
   ```
10. Verify local/remote snapshot branch SHA.
11. Write run summary under:
   ```text
   .riftreader-local/workflow-sessions/<session-id>/
   ```

## Lane 2: `repo-status-snapshot`

Purpose: create a durable, current repo status snapshot without needing live RIFT or memory tools.

Steps:

1. Run safe Git status commands.
2. Capture branch, HEAD, remote SHA, dirty paths, and recent commits.
3. Capture current workflow policy files.
4. Write a curated payload or direct snapshot.
5. Publish to `chatgpt/snapshot`.
6. Never stage, commit, or push source-code changes.

## Lane 3: `recovery-payload-snapshot`

Purpose: generate the current RIFT recovery payload and immediately publish it for ChatGPT inspection.

Initial v0.1 behavior should be conservative:

1. Verify repo state.
2. Identify existing safe recovery/status helpers.
3. Run only offline/read-only payload generation helpers.
4. Do not run live RIFT input.
5. Do not run movement.
6. Do not run ProofOnly promotion.
7. Do not attach Cheat Engine.
8. Do not attach x64dbg.
9. Create curated text payload under:
   ```text
   artifacts/chatgpt-payloads/<recovery-payload-id>/
   ```
10. Refresh bridge/snapshot and push to `chatgpt/snapshot`.

If the correct recovery payload generator is not yet identified, the lane must stop with a clear blocker and publish a status snapshot instead of guessing.

## Session persistence

The orchestrator should write durable session files before and after every major stage:

```text
.riftreader-local/workflow-sessions/<session-id>/
  session.json
  summary.md
  stdout.log
  stderr.log
  commands.jsonl
  blockers.json
```

Also maintain:

```text
.riftreader-local/workflow-sessions/latest.json
```

This allows recovery after:

```text
- closed terminal
- stopped bridge
- failed tunnel
- chat restart
- accidental process kill
```

## Resume commands

The orchestrator should support:

```powershell
.\scripts\riftreader-workflow.cmd --status
.\scripts\riftreader-workflow.cmd --resume latest
.\scripts\riftreader-workflow.cmd --stop-session latest
.\scripts\riftreader-workflow.cmd --publish-last-snapshot
```

## Safety gates

Always allowed:

```text
- repo root verification
- local Git read-only status checks
- local bridge health checks
- localhost bridge GET/HEAD requests
- curated payload reads
- snapshot branch push
- writing .riftreader-local logs/summaries
```

Allowed only when explicitly requested:

```text
- applying code packages
- committing implementation changes
- pushing main
- creating or deleting review branches
```

Never allowed inside the orchestrator v0.1:

```text
- git add .
- broad staging
- arbitrary command execution endpoints
- arbitrary local file reads through bridge
- live RIFT movement
- live RIFT input
- ProofOnly promotion
- Cheat Engine attach
- x64dbg attach
- deleting unrelated files
- modifying Google Drive files
```

## Validation standard

Every package for this work must pass:

```text
- Python py_compile
- unit tests
- helper --self-test
- synthetic/temp repo smoke test where practical
- package manifest SHA256 validation
- allowlist-only target paths
- git diff --check
- explicit staged-path comparison before commits
- local/remote SHA verification after pushes
```

If a PowerShell block is used, it should be a thin launcher only. Complex logic belongs in Python.

## CI policy

Implementation branches should use this pattern so GitHub CI runs:

```text
chatgpt/review-*
```

The repo CI currently targets `main` and `chatgpt/review-*`.

Use:

```text
chatgpt/review-workflow-orchestrator-v0.1.0
```

for the orchestrator implementation branch.

The runtime snapshot branch remains:

```text
chatgpt/snapshot
```

## Exact next implementation action

Build and validate:

```text
RiftReader_WorkflowOrchestrator_v0.1.0.zip
apply_riftreader_workflow_orchestrator_v0_1_0.py
```

Initial scope:

```text
1. Implement `snapshot-refresh`.
2. Implement `repo-status-snapshot`.
3. Add guarded skeleton for `recovery-payload-snapshot`.
4. Add session persistence under `.riftreader-local/workflow-sessions`.
5. Add tests and docs.
```

Then:

```text
1. Apply package locally.
2. Run validation.
3. Commit to `chatgpt/review-workflow-orchestrator-v0.1.0`.
4. Push review branch.
5. Verify CI if visible.
6. Test snapshot-refresh lane.
7. Merge to main after validation.
```

## Do-not-do notes

Do not resume live RIFT movement or proof-promotion work while building the orchestrator.

Do not use OpenCode.

Do not depend on Google Drive.

Do not use GitHub connector writes for implementation unless explicitly approved in the current turn.

Do not expose arbitrary local paths through the bridge.

Do not let a failed stage print a misleading success marker.

<!-- END_OF_SCRIPT_MARKER -->
