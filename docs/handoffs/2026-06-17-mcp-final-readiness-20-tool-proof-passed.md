# 2026-06-17 - MCP final readiness passed with 20-tool actual-client proof

## Current truth

| Item | Current state |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main...origin/main` synced after pushing Control Center + handoff commits. |
| HEAD | `14ec3d058331af12f26f4218e11e63aba9c9d877` / `14ec3d0 Document MCP control center post-commit handoff` |
| Active lane | Non-Codex ChatGPT Web/Desktop Developer Mode MCP workflow. |
| Public MCP URL | `https://mcp.360madden.com/mcp` with `No Authentication`. |
| Local backend | `http://127.0.0.1:8770/mcp`; observed listener is `python.exe tools\riftreader_workflow\riftreader_chatgpt_mcp.py --serve --tool-profile full --host 127.0.0.1 --port 8770 --transport streamable-http --allowed-host mcp.360madden.com --allowed-origin https://chatgpt.com`. |
| Tool surface | Full 20-tool profile, including `commit_reviewed_slice`. |
| Final gate | Passed at `2026-06-17T09:39:21Z`. |
| Worktree | Clean at final gate. |

## What changed since the prior handoff

The prior tracked handoff stopped with final readiness blocked because the latest actual-client proof was still a stale 19-tool proof. This refresh records that the actual connector proof was completed for the current 20-tool surface and the final gate passed.

## Actual-client proof recorded

| Field | Value |
|---|---|
| Proof JSON | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260617-093918Z\proof.json` |
| Proof Markdown | `.riftreader-local\riftreader-chatgpt-mcp\actual-client-proof\20260617-093918Z\proof.md` |
| Proof mode | `final-20-tool` |
| Tool count | `20` |
| New tool covered | `commit_reviewed_slice` |
| Output schemas | Present for all 20 tools. |
| Inert proof inbox/draft id | `20260617T093724Z-de1fa1018558` |
| Apply-without-approval check | Blocked with `APPLY_APPROVAL_MISSING`; `applied=false`. |

## Connector proof sequence

| Step | Result |
|---|---|
| `mcp__riftreader.health` | Passed; returned `toolCount=20` and all expected tool names. |
| `get_package_proposal_template` | Passed. |
| `submit_package_proposal` | Stored inert local-only proposal `20260617T093724Z-de1fa1018558`. |
| `list_inbox` | Saw the proposal. |
| `create_package_draft_from_inbox` | Created inert package draft with the same id. |
| `review_latest_package_draft` | Passed, read-only review ready. |
| `dry_run_latest_package_draft` | Passed; no apply flag, no repo mutation. |
| `apply_latest_package_draft` without approval token | Blocked as expected with `APPLY_APPROVAL_MISSING`; no source/Git mutation. |

## Final readiness gate snapshot

Command:

```cmd
scripts\riftreader-mcp-final.cmd --status --compact-json
```

Observed at `2026-06-17T09:39:21Z`:

| Field | Value |
|---|---|
| `status` / `ok` | `passed` / `true` |
| `currentHead` | `14ec3d058331af12f26f4218e11e63aba9c9d877` |
| `gitDirty` | `false` |
| `upstreamStatus` | `passed` |
| `ciStatus` | `passed` |
| `toolSurfaceStatus` | `passed` |
| `proofReplayStatus` | `passed` |
| `phase2Ready` / `phase2Status` | `true` / `passed` |
| `blockers` | `[]` |

Warnings remain informational only:

- old cloudflare/trial-session artifacts are expected-expired;
- `environment:default-serve-port-busy:8770` because the intended local MCP server is already listening.

## CI state

| Workflow | Result |
|---|---|
| `.NET build and test` | Passed on current HEAD. |
| `RiftReader Policy` | Passed on current HEAD. |

## Safety boundaries observed

No action in this proof sequence performed or approved:

- source apply;
- Git staging/commit/push through MCP;
- remote branch mutation after the already-authorized push of `main`;
- RIFT input/movement, `/reloadui`, screenshot key input;
- Cheat Engine or x64dbg attach;
- provider repo writes;
- Cloudflare or ChatGPT connector mutation.

The proof did write ignored local artifacts under `.riftreader-local` for inbox, draft, dry-run, and actual-client proof evidence.

## Fast resume commands

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
git --no-pager status --short --branch
scripts\riftreader-mcp-final.cmd --status --compact-json
scripts\riftreader-mcp-control-center.cmd --open
```

## Top 10 recommended next actions

| # | Action | Why |
|---:|---|---|
| 1 | Keep the current proof fresh by rerunning the final gate before any release claim. | Final readiness is evidence-based and time-sensitive. |
| 2 | Commit and push this handoff refresh if not already done. | Makes the final-passed state durable for future sessions. |
| 3 | Leave the `8770` server running only if actively using ChatGPT MCP. | It is currently the intended backend, but should not be assumed permanent. |
| 4 | Use the Control Center for future local checks. | It centralizes safe status/readiness/proof actions. |
| 5 | Do not call `apply_latest_package_draft` with approval unless deliberately applying a reviewed package. | The proof only verified the no-approval block. |
| 6 | Do not call `commit_reviewed_slice` without a fresh local commit preflight token. | It is intentionally gated even though visible in the 20-tool surface. |
| 7 | If tools disappear in ChatGPT, refresh the `rift-mcp` app connector and rerun `health`. | Tool visibility is the main actual-client failure mode. |
| 8 | If final gate regresses, inspect the newest actual-client proof artifact before changing code. | Avoids patching around stale evidence. |
| 9 | Keep old 19-tool proof artifacts as history only. | Current product proof is now 20-tool. |
| 10 | Treat RIFT live proof/recovery as a separate gated lane. | No `rift_x64` target was present during this MCP proof work. |
