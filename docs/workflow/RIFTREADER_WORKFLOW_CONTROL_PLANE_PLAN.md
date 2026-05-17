# RiftReader Workflow Control Plane Plan

## Purpose

Shift current RiftReader work from feature expansion to workflow acceleration.

Primary focus:

- Faster discovery.
- More reliable live-test triage.
- Safer desktop ChatGPT to local repo package intake.
- Less manual terminal work.
- Better continuation artifacts for future sessions.
- Modular helper tooling that can later be chained or merged.

This is not a new movement, yaw, or auto-turn phase.

## Design Principles

1. **Modular first**
   - Avoid one large operator mega-script.
   - Build small tools with clear responsibilities.
   - Merge helper apps later only after stable patterns emerge.

2. **Python-first helper workflow**
   - Python for helper logic, validation, reports, package intake, and workflow status.
   - CMD launchers should stay thin.
   - PowerShell only for small Windows-specific bridges or local applier wrappers.

3. **Fail closed**
   - Clear `PASS`, `BLOCKED`, or `FAIL`.
   - No hidden auto-commit.
   - No hidden auto-push.
   - No `git add .`.
   - No services, listeners, polling, scheduled tasks, or clipboard watchers.

4. **Fast operator feedback**
   - One command should show current workflow state.
   - Reports should identify the failed stage and next safe action.
   - Avoid forcing manual artifact hunting.

5. **Security hygiene**
   - Do not expose local Windows usernames.
   - Use `%USERNAME%`, `$env:USERPROFILE`, or `<REDACTED_SECRET>`.
   - Watch for API keys, tokens, webhooks, `.env` contents, private keys, secrets, and personal paths.

## Phase A — Workflow Status Packet

### Goal

Create a fast, read-only status packet for desktop ChatGPT and local operator use.

### Output

```text
handoffs/current/workflow-status/WORKFLOW_STATUS_REPORT.md
handoffs/current/workflow-status/workflow-status-summary.json
handoffs/current/workflow-status/workflow-status-log.jsonl
```

### Should summarize

- Current branch.
- Git cleanliness.
- Recent commits.
- Latest live-test run.
- Latest target-control result.
- Latest visual-gate wrapper result.
- Latest ProofOnly result.
- Latest blocked stage.
- Latest reference-capture error.
- Current proof pointer status.
- Recommended next command.

### Safety

Read-only except writing report artifacts.

No live input, no movement, no yaw, no `/reloadui`, no capture expansion.

## Phase B — Package Intake Lite

### Goal

Replace giant pasted scripts with validated local package intake.

### Proposed files

```text
tools/riftreader_workflow/intake.py
tools/riftreader_workflow/package_manifest.py
tools/riftreader_workflow/apply_package.py
scripts/riftreader-package-intake.cmd
```

### Required behavior

- Validate package manifest.
- Verify SHA-256 checksums.
- Back up changed files.
- Apply changed files.
- Run declared checks.
- Roll back on failure.
- Show git status.
- Never auto-commit.
- Never auto-push.
- Never stage dot.

### Purpose

Make ZIP/package transfer from desktop ChatGPT to local RiftReader faster and safer.

## Phase C — Discovery / Live-Test Fast Lane

### Goal

Speed up discovery and live-test triage.

### Proposed files

```text
tools/riftreader_workflow/discovery_status.py
tools/riftreader_workflow/live_test_triage.py
scripts/riftreader-live-triage.cmd
```

### Should answer

- What failed?
- Which stage failed?
- Which artifact proves it?
- Is the issue target-control, reference capture, proof refresh, readback, or movement?
- What is the next safest command?

### Current example problem

Reference capture can fail on malformed `RRAPICOORD1` memory-scan markers. This should be surfaced as a specific reference-capture issue, not vague JSON parse failure.

## Phase D — Operator Lite

### Goal

Create a small GUI after CLI workflow stabilizes.

### Proposed files

```text
tools/riftreader_operator_lite.py
scripts/riftreader-operator-lite.cmd
```

### Initial buttons

- Refresh Workflow Status
- Run Target-Control
- Run Visual Gate Wrapper
- Run ProofOnly
- Run Live-Test Triage
- Open Latest Report
- Git Status

### Not included initially

- No movement buttons.
- No yaw buttons.
- No auto-turn.
- No package-intake GUI until the CLI intake is stable.

## Phase E — Consolidation

### Goal

After useful patterns stabilize, merge shared helper logic into a small internal workflow package.

### Current status

Started with the smallest safe consolidation slice:

- `tools/riftreader_workflow/common.py` now owns shared UTC timestamps, repo-relative path rendering, duplicate filtering, bounded command envelopes/text previews, repo-root discovery, timestamped output directory creation, and fail-closed safety flags.
- `status_packet.py`, `apply_package.py`, `live_test_triage.py`, and `operator_lite.py` consume those shared primitives instead of carrying local copies.
- Entry points remain separate and modular; this did not create a new operator mega-script.

### Proposed structure

```text
tools/riftreader_workflow/
  common.py        # implemented
  git.py
  artifacts.py
  status_packet.py
  intake.py
  validation.py
  reports.py
```

### Rule

Shared modules, small entrypoints.

Avoid a single giant operator application.

## Immediate Next Package

### Name

```text
RiftReader_Workflow_Status_Packet_v0.1.0.zip
```

### Proposed files

```text
tools/riftreader_workflow/common.py
tools/riftreader_workflow/status_packet.py
scripts/riftreader-workflow-status.cmd
scripts/test_riftreader_workflow_status.py
docs/workflow/WORKFLOW_CONTROL_PLANE.md
```

### Target command

```powershell
cd "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-workflow-status.cmd
```

### Expected result

A concise report showing current workflow state and the next safest action.

## Package Validation Standard

Every package must be checked before delivery:

```text
python -m py_compile
offline unit tests
fixture status-packet test
post-extraction smoke test
manifest hash check
no __pycache__
no .pyc
no local username leakage
no secrets
```

## Major Milestone Rule

Major milestones get a push helper script only after local validation passes.

The helper must:

- Stage explicit paths only.
- Exclude runtime artifacts unless intentionally requested.
- Exclude `.riftreader-local/`.
- Run relevant tests before commit.
- Commit with a clear message.
- Push to branch or main as appropriate.
- Leave final `git status --short` clean.

## Current Roadmap Priority

| # | Item | Status |
|---:|---|---|
| 1 | Workflow Status Packet | Implemented and pushed. |
| 2 | Package Intake Lite | Implemented and pushed. |
| 3 | Live-Test Fast Lane | Implemented and pushed. |
| 4 | Operator Lite | Implemented and pushed. |
| 5 | Consolidation | In progress; common utility slice implemented. |

Do not expand preflight further unless a specific workflow failure requires it.
