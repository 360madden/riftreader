# 2026-06-17 - MCP Stage 21 approved apply and Stage 27 commit proof

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Active lane | Non-Codex ChatGPT Web/Desktop Developer Mode MCP workflow. |
| MCP surface | Full 20-tool profile, including `apply_latest_package_draft` and `commit_reviewed_slice`. |
| Server status | `running-current` before approved apply and before approved commit proof. |
| Stage 21 result | Passed: actual connector approved `apply_latest_package_draft` returned `applied=true`. |
| Stage 27 result | Passed: actual connector `commit_reviewed_slice` created local commit `a90c9dd6e9eeb68b7bd11680455f088d020d6604`. |
| Applied/committed file | `docs/workflow/riftreader-chatgpt-mcp-stage21-apply-proof.md`. |

## Server dependency evidence

`scripts\riftreader-mcp-server-status.cmd --json` was run immediately before
the approved apply and commit calls.

| Field | Value |
|---|---|
| `status` / `ok` | `running-current` / `true` |
| Local URL | `http://127.0.0.1:8770/mcp` |
| Process | `python.exe` |
| Command identity | `tools\riftreader_workflow\riftreader_chatgpt_mcp.py --serve --tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http` |
| Tool profile | `full` |
| Public host/origin | `mcp.360madden.com` / `https://chatgpt.com` |

This matters because the saved ChatGPT connector entry is configuration only;
it does not start the local backend. Proof work only proceeded after the
repo-owned status helper proved the current server was listening.

## Stage 21 approved apply proof

| Step | Evidence |
|---|---|
| Superseded draft | `20260617T101811Z-aab94584f623`; not applied because the diff had unnecessary line-ending churn. |
| Applied proposal/draft | `20260617T101929Z-efafb87b4f3c` |
| Dry-run summary | `.riftreader-local\package-intake\20260617-101939Z\package-intake-summary.json` |
| Dry-run diff SHA-256 | `59b9d60602774d3c1d113f358db1c1d564573953a5b19411d2007a6e751e2359` |
| Apply approval token | `APPLY-f8a80992d636f563` |
| Apply summary | `.riftreader-local\package-intake\20260617-102018Z\package-intake-summary.json` |
| Changed files | `docs/workflow/riftreader-chatgpt-mcp-stage21-apply-proof.md` |
| Declared checks | `2` declared, `2` run, `0` failed |
| Apply safety | `gitMutation=false`; no provider writes, RIFT input, CE, or x64dbg |

The apply path was the actual MCP connector tool call, not direct local package
intake. The call used the current dry-run summary path, current diff hash, and
the current local preflight approval token.

## Stage 27 actual-client commit proof

| Step | Evidence |
|---|---|
| Validation summary | `.riftreader-local\validation-runs\20260617-102132-stage27\summary.json` |
| Validation digest | `48478395f38a3db668667aa9373a858e7006a29c176e18d0ca683a90062b5fa3` |
| Validation commands | `py_compile`, focused package/commit/MCP unit tests, `git diff --check` |
| Preflight expected HEAD | `688b72ebf00e9c73ad4660a5338be42d651cd55e` |
| Commit approval token | `COMMIT-0d808ed51a2634d2` |
| Commit hash | `a90c9dd6e9eeb68b7bd11680455f088d020d6604` |
| Commit message | `Prove MCP approved apply and commit` |
| Staged paths | `docs/workflow/riftreader-chatgpt-mcp-stage21-apply-proof.md` only |
| Commit safety | Local commit only; no push, rewrite, reset, clean, provider write, RIFT input, CE, or x64dbg |

`commit_reviewed_slice` reran preflight, staged only the explicit path, ran
pre-commit for that path, and created the local commit.

## Validation

| Command / gate | Result |
|---|---|
| Package dry-run checks | Passed: `2` declared, `2` run, `0` failed |
| Approved package apply checks | Passed: `2` declared, `2` run, `0` failed |
| `python -m py_compile ...` for apply/commit/MCP lane | Passed |
| `python -m unittest scripts.test_package_draft_review scripts.test_commit_reviewed_slice scripts.test_riftreader_chatgpt_mcp` | Passed |
| `git --no-pager diff --check -- docs/workflow/riftreader-chatgpt-mcp-stage21-apply-proof.md` | Passed |
| `pre-commit run --files docs/workflow/riftreader-chatgpt-mcp-stage21-apply-proof.md` | Passed inside `commit_reviewed_slice` |

## Safety boundaries observed

No action in this proof sequence performed or approved:

- RIFT input, movement, target selection, `/reloadui`, or screenshot key input;
- Cheat Engine, x64dbg, debugger attach, breakpoints, or watchpoints;
- provider repo writes;
- broad shell/arbitrary filesystem MCP endpoint;
- branch rewrite, reset, clean, destructive cleanup, or force push;
- remote Git mutation through MCP.

## Fast resume commands

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
git --no-pager status --short --branch
scripts\riftreader-mcp-server-status.cmd --json
scripts\riftreader-mcp-final.cmd --status --compact-json
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Commit this handoff refresh with explicit docs paths. | Preserves the proof trail in tracked docs. |
| 2 | Push `main` normally after the handoff commit. | Publishes the Stage 21/27 milestone. |
| 3 | Wait for GitHub CI on the pushed head. | Current-head CI is required for release confidence. |
| 4 | Rerun the final MCP gate after CI passes. | Confirms proof, CI, dependency, and tool-surface state together. |
| 5 | Keep the MCP server dependency helper as the first proof gate. | Avoids repeating the missing/stale-server failure mode. |
| 6 | Add an approved-proof recorder helper. | Would turn this manual artifact stitching into repeatable evidence. |
| 7 | Teach final readiness to surface the newest Stage 21/27 handoff. | Reduces stale handoff ambiguity. |
| 8 | Only design push/CI MCP helpers after this commit is green. | Keeps remote mutation behind proven local gates. |
| 9 | Keep the superseded draft as ignored local history only. | It proves conservative review rejected a noisy package. |
| 10 | Do not combine live RIFT proof with MCP workflow proof. | The risk profiles and approval gates are different. |
