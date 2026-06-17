# 2026-06-17 - MCP 20-tool Control Center post-commit compact handoff

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main...origin/main [ahead 1]` after `git fetch --prune origin` |
| HEAD | `58988ad7dcf80d01ba88212e905c8e8445476854` / `58988ad Add MCP control center GUI` |
| Upstream | `origin/main` is `7ad33c593a8b7136c598094de8dd69008a2b93eb` / `Expose MCP commit tool` |
| Worktree before this handoff | Clean; creating this handoff and updating `docs/HANDOFF.md` makes the repo dirty until committed. |
| Active lane | Non-Codex ChatGPT Web/Desktop Developer Mode MCP workflow. |
| Public MCP URL | `https://mcp.360madden.com/mcp` with `No Authentication`. |
| Local backend | `http://127.0.0.1:8770/mcp`; the saved ChatGPT connector does not start the local server or Cloudflared. |
| Local GUI | `scripts\riftreader-mcp-control-center.cmd --open` serves `http://127.0.0.1:8790/`. |

## What just changed

Local commit `58988ad Add MCP control center GUI` added a localhost-only Control Center for the safe local parts of the non-Codex ChatGPT MCP workflow:

| Path | Purpose |
|---|---|
| `tools\riftreader_workflow\mcp_control_center.py` | Localhost-only backend/API with fixed allowlisted actions and managed adapter tracking. |
| `tools\mcp-control-center\index.html` | Tabbed GUI shell. |
| `tools\mcp-control-center\styles.css` | Dark responsive GUI styling. |
| `tools\mcp-control-center\app.js` | Frontend refresh/actions/copy helpers/rendering. |
| `scripts\riftreader-mcp-control-center.cmd` | Thin CMD launcher for the Python backend. |
| `scripts\test_mcp_control_center.py` | Safety and GUI surface tests. |
| `docs\workflow\riftreader-mcp-control-center.md` | Operator docs for the GUI. |
| `docs\handoffs\2026-06-17-mcp-control-center-gui-compact-handoff.md` | Pre-commit compact handoff for the GUI slice. |
| `README.md`, `docs\workflow\riftreader-chatgpt-mcp.md`, `docs\HANDOFF.md` | Discovery and workflow pointers. |

## Validation already run for the committed slice

| Check | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\mcp_control_center.py scripts\test_mcp_control_center.py` | Passed. |
| `python scripts\test_mcp_control_center.py` | Passed: 6 tests. |
| `python scripts\test_mcp_dashboard.py` | Passed: 6 tests. |
| `node --check tools\mcp-control-center\app.js` | Passed. |
| `scripts\riftreader-mcp-control-center.cmd --self-test --json` | Passed; `actionCount=14`, no blockers. |
| Browser plugin visual QA | Passed: GUI loaded, tabs/buttons enabled, status cards rendered, no page-level errors. |
| `pre-commit run --files ...` explicit GUI/doc paths | Passed. |
| Safe MCP workflow unittest suite | Passed: 256 tests in 42.760s. |
| Commit hook pre-commit | Passed during commit `58988ad`. |
| `git --no-pager diff --check` | Passed; only CRLF normalization warnings from Git. |

## Final-readiness gate snapshot

Latest command:

```cmd
scripts\riftreader-mcp-final.cmd --status --compact-json
```

Observed at `2026-06-17T07:52:36Z`:

| Field | Value |
|---|---|
| `status` / `ok` | `blocked` / `false` |
| `currentHead` | `58988ad7dcf80d01ba88212e905c8e8445476854` |
| `gitDirty` at gate run | `false` |
| `toolSurfaceStatus` | `passed` |
| `dependencyStatus` / `environmentStatus` | `passed` / `passed` |
| `upstreamStatus` | `blocked` because `ahead=1` |
| `ciStatus` | `blocked` because current-head GitHub CI has not run on `58988ad` |
| `proofReplayStatus` | `blocked` |
| `phase2Status` | `blocked` |

Current blockers from the final gate:

| Blocker | Meaning |
|---|---|
| `git:upstream-not-synced:behind=0:ahead=1` | Local commit `58988ad` has not been pushed. |
| `ci:missing:.NET build and test` | No current-head CI result for `58988ad`. |
| `ci:missing:RiftReader Policy` | No current-head policy CI result for `58988ad`. |
| `proof:replay-failed:tool-count-not-20:19` | Latest actual-client proof is still the older 19-tool proof. |
| `proof:replay-failed:tool-names-count-not-20:19` | Actual-client tool-name evidence does not cover the current 20-tool surface. |
| `proof:replay-failed:tool-output-schema-count-not-20:19` | Actual-client output-schema evidence does not cover the current 20-tool surface. |
| `phase2:not-ready` | Final gate keeps the phase blocked until required proof/CI conditions are met. |

## Current proof lane

| Item | Current value |
|---|---|
| Expected local full profile | 20 tools. |
| New tool needing actual-client proof | `commit_reviewed_slice`. |
| Latest fresh proof-input template | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-073901Z\proof-input.json` |
| Read-only check command | `scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-073901Z\proof-input.json --json` |
| Current check state | Blocked until actual ChatGPT Web/Desktop observations fill the template. |

Do not confuse local `health` or local trial readiness with actual-client proof. The missing evidence must come from ChatGPT Web/Desktop Developer Mode calling the `rift-mcp` tools through `https://mcp.360madden.com/mcp`.

## Safety boundaries still in force

No one has run or approved any of these in this slice:

- Git push;
- approved `apply_latest_package_draft` proof;
- approved `commit_reviewed_slice` proof through MCP;
- `push_current_branch` design/implementation;
- ChatGPT connector mutation;
- Cloudflare mutation or public tunnel startup from Codex;
- RIFT input/movement, `/reloadui`, screenshot key input;
- Cheat Engine or x64dbg attach;
- provider repo writes.

## Fast resume commands

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
git --no-pager status --short --branch
scripts\riftreader-mcp-final.cmd --status --compact-json
scripts\riftreader-mcp-control-center.cmd --open
```

For actual-client proof checking after filling the template:

```cmd
scripts\riftreader-chatgpt-trial-recorder.cmd --check-input --input .riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-073901Z\proof-input.json --json
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Decide whether to push `58988ad` to `origin/main`. | Required for current-head GitHub CI. |
| 2 | If pushed, wait for `.NET build and test` and `RiftReader Policy`. | Final gate requires current-head CI. |
| 3 | Start the local MCP adapter explicitly before ChatGPT proof work. | The saved ChatGPT connector does not start the local backend or Cloudflared. |
| 4 | Use `scripts\riftreader-mcp-control-center.cmd --open` for local operator workflow. | GUI centralizes safe local status/readiness/proof helpers. |
| 5 | In ChatGPT Web/Desktop, use `https://mcp.360madden.com/mcp` with `No Authentication`. | This is the active non-Codex route. |
| 6 | In ChatGPT, call `health` and verify the actual client sees 20 tools. | Local health already passes, but actual-client visibility is the proof gap. |
| 7 | Confirm `commit_reviewed_slice` is visible in ChatGPT but do not approve it. | Stage 27 approved commit proof remains gated. |
| 8 | Fill the `20260617-073901Z` proof template with actual ChatGPT observations. | The final gate is blocked by stale 19-tool proof replay. |
| 9 | Run the read-only `--check-input` command before recording proof. | Catches missing fields without recording bad proof. |
| 10 | Only after proof and CI pass, rerun `scripts\riftreader-mcp-final.cmd --status --compact-json`. | This verifies the release gate from current evidence. |
