# 2026-06-17 - MCP Control Center GUI compact handoff

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main...origin/main` at `7ad33c593a8b7136c598094de8dd69008a2b93eb` / `7ad33c5 Expose MCP commit tool` |
| Worktree | Dirty with a local, uncommitted GUI slice for the non-Codex ChatGPT MCP lane. |
| Active MCP route | ChatGPT Web/Desktop Developer Mode uses `https://mcp.360madden.com/mcp` with `No Authentication`; local backend is `http://127.0.0.1:8770/mcp`. |
| New GUI | `scripts\riftreader-mcp-control-center.cmd --open` serves `http://127.0.0.1:8790/`. |
| GUI scope | Localhost-only Control Center with tabs for Overview, Server, Readiness, Route & ChatGPT, Proof, Validation, Logs & JSON, and Safety. |
| Safety boundary | No arbitrary shell, arbitrary filesystem, Git mutation, ChatGPT registration, Cloudflare mutation, RIFT input/movement, CE, or x64dbg endpoint. |
| Existing dashboard | `scripts\riftreader-mcp-dashboard.cmd` remains the status-only dashboard on `http://127.0.0.1:8788/`; the new Control Center is separate. |

## Files in this slice

| Path | Purpose |
|---|---|
| `tools\riftreader_workflow\mcp_control_center.py` | Localhost-only GUI backend/API with fixed allowlisted MCP workflow actions and managed adapter process tracking. |
| `tools\mcp-control-center\index.html` | Polished tabbed GUI shell. |
| `tools\mcp-control-center\styles.css` | Readable dark theme, responsive grid, cards, tabs, badges, logs, and action layout. |
| `tools\mcp-control-center\app.js` | Frontend state, refresh, action dropdown, tab switching, copy helpers, confirmation prompts, and rendering. |
| `scripts\riftreader-mcp-control-center.cmd` | Thin CMD wrapper for the GUI backend. |
| `scripts\test_mcp_control_center.py` | Unit tests for action registry safety, confirmation gates, redaction, status shape, and static GUI surfaces. |
| `docs\workflow\riftreader-mcp-control-center.md` | Operator docs for start command, tabs, safety model, and allowlisted action families. |
| `README.md` | Adds optional Control Center start command to the ChatGPT MCP local launcher section. |
| `docs\workflow\riftreader-chatgpt-mcp.md` | Adds Control Center docs near domain diagnostics/local dashboard docs. |

## How to resume / run the GUI

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
scripts\riftreader-mcp-control-center.cmd --open
```

Manual URL if the browser does not open automatically:

```text
http://127.0.0.1:8790/
```

Useful non-GUI checks:

```cmd
scripts\riftreader-mcp-control-center.cmd --self-test --json
scripts\riftreader-mcp-control-center.cmd --once-json
```

## Validation already run

| Check | Result |
|---|---|
| `python -m py_compile tools\riftreader_workflow\mcp_control_center.py scripts\test_mcp_control_center.py` | Passed. |
| `python scripts\test_mcp_control_center.py` | Passed: 6 tests. |
| `python scripts\test_mcp_dashboard.py` | Passed: 6 tests. |
| `node --check tools\mcp-control-center\app.js` | Passed. |
| `scripts\riftreader-mcp-control-center.cmd --self-test --json` | Passed; latest observed `generatedAtUtc=2026-06-17T07:45:42Z`, `actionCount=14`, no blockers. |
| `pre-commit run --files ...` on the explicit GUI/doc paths | Passed. |
| `python -m unittest ...` safe MCP workflow suite | Passed: 256 tests in 42.760s. |
| HTTP smoke while temporary GUI server was running | `GET /` returned 200, `GET /api/status?force=1` returned 200. |
| HTTP action smoke | `POST /api/actions` for `final_gate` worked and returned the current expected blocked state, not an API failure. |
| `git --no-pager diff --check` | Passed; only CRLF warnings from Git. |

Browser plugin visual QA was refreshed on 2026-06-17: the in-app browser loaded `http://127.0.0.1:8790/`, title was `RiftReader MCP Control Center`, tabs/buttons enabled after load, status cards rendered, and no page-level alert/error elements were present.

## Current final-readiness gate

Latest direct command:

```cmd
scripts\riftreader-mcp-final.cmd --status --compact-json
```

Observed at `2026-06-17T02:31:12Z`:

| Field | Value |
|---|---|
| `status` / `ok` | `blocked` / `false` |
| `currentHead` | `7ad33c593a8b7136c598094de8dd69008a2b93eb` |
| `gitDirty` | `true` |
| `toolSurfaceStatus` | `passed` |
| `phase2Status` | `blocked` |
| `proofReplayStatus` | `blocked` |

Primary blockers:

- `git:dirty-worktree` because this GUI slice is not committed yet;
- `phase2:not-ready`;
- latest actual-client proof is still the prior 19-tool proof while current local tool surface expects 20 tools:
  - `proof:replay-failed:tool-count-not-20:19`;
  - `proof:replay-failed:tool-names-count-not-20:19`;
  - output schema count/name mismatches for 19 vs 20.

## Current git status before this handoff

```text
## main...origin/main
 M README.md
 M docs/workflow/riftreader-chatgpt-mcp.md
?? docs/workflow/riftreader-mcp-control-center.md
?? scripts/riftreader-mcp-control-center.cmd
?? scripts/test_mcp_control_center.py
?? tools/mcp-control-center/
?? tools/riftreader_workflow/mcp_control_center.py
```

This handoff adds:

```text
?? docs/handoffs/2026-06-17-mcp-control-center-gui-compact-handoff.md
```

## Important implementation notes

- The GUI backend rejects non-localhost host binding.
- Mutating API calls require `X-RiftReader-Control-Center: 1`.
- Start/stop actions require browser confirmation.
- `stop_managed_server` only targets the tracked PID from `.riftreader-local\riftreader-chatgpt-mcp\control-center\managed-server.json` and verifies the command line contains `riftreader_chatgpt_mcp.py` before killing it.
- Existing/manual MCP server windows are detected as a listener and are not killed by the GUI.
- Some allowlisted actions write ignored `.riftreader-local` diagnostics/proof artifacts, but no tracked files, Git staging, commits, pushes, provider writes, RIFT input, CE, or x64dbg actions.

## Recommended next actions

1. Open `http://127.0.0.1:8790/` in a normal browser and perform visual QA of layout/readability.
2. If visual QA is acceptable, stage the explicit GUI/doc/test paths and commit the slice locally.
3. After commit, rerun `scripts\riftreader-mcp-final.cmd --status --compact-json`; dirty-worktree should clear, but 20-tool actual-client proof will still be required.
4. Use the GUI or trial recorder to write/fill a fresh `final-20-tool` ChatGPT Web/Desktop actual-client proof template.
5. Record current actual-client proof through `https://mcp.360madden.com/mcp` only after the local adapter/tunnel path is operator-confirmed healthy.

## 2026-06-17 refresh

- Wrote a fresh `final-20-tool` proof template at `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260617-073901Z\proof-input.json`.
- Local health reported `toolCount=20` and exposed `commit_reviewed_slice`.
- Local trial readiness passed at `.riftreader-local\riftreader-chatgpt-mcp\transport-smoke\20260617T073918Z-trial-readiness.json`.
- Latest template check remains blocked as expected until actual ChatGPT Web/Desktop observations fill the template.
