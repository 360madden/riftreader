# 2026-06-17 - MCP Stage 21 apply + Stage 27 commit proof

Fresh compact handoff:
`docs/handoffs/2026-06-17-mcp-stage21-apply-stage27-commit-proof.md`.

| Item | Current truth |
|---|---|
| Repo | `C:\RIFT MODDING\RiftReader` |
| Branch | `main` with local proof commit `a90c9dd6e9eeb68b7bd11680455f088d020d6604` ahead of `origin/main` until the follow-up handoff/push completes. |
| Server dependency | `scripts\riftreader-mcp-server-status.cmd --json` reported `status=running-current` immediately before approved apply and commit proof calls. |
| Stage 21 | Approved `apply_latest_package_draft` proof passed through the actual MCP connector. |
| Stage 27 | Approved `commit_reviewed_slice` proof passed through the actual MCP connector and created local commit `a90c9dd`. |
| Applied proof file | `docs/workflow/riftreader-chatgpt-mcp-stage21-apply-proof.md`. |
| Stage 21 artifacts | Dry-run `.riftreader-local\package-intake\20260617-101939Z\package-intake-summary.json`; apply `.riftreader-local\package-intake\20260617-102018Z\package-intake-summary.json`. |
| Stage 27 validation | `.riftreader-local\validation-runs\20260617-102132-stage27\summary.json`, digest `48478395f38a3db668667aa9373a858e7006a29c176e18d0ca683a90062b5fa3`. |
| Safety | No RIFT input/movement, `/reloadui`, screenshot key input, CE/x64dbg, provider writes, branch rewrite, reset, clean, destructive cleanup, or broad shell/filesystem MCP endpoint. |

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
| 1 | Commit and push this handoff/doc refresh with explicit paths. | Makes Stage 21/27 proof durable on `origin/main`. |
| 2 | Wait for GitHub CI on the pushed head. | Final readiness depends on current-head CI evidence. |
| 3 | Rerun `scripts\riftreader-mcp-final.cmd --status --compact-json`. | Confirms final gate after the new proof commits. |
| 4 | Keep using `scripts\riftreader-mcp-server-status.cmd --json` before MCP proof. | Prevents confusing a missing/stale server with proof failure. |
| 5 | Treat draft `20260617T101811Z-aab94584f623` as superseded and not applied. | It had broader line-ending churn and was intentionally abandoned. |
| 6 | Keep Stage 21 apply and Stage 27 commit as separate gates. | Preserves the package-apply vs Git-mutation boundary. |
| 7 | Add a first-class proof recorder for approved apply/commit if this pattern repeats. | Reduces manual artifact transcription risk. |
| 8 | Add final-gate awareness of the newest Stage 21/27 handoff. | Avoids stale `releaseHandoffPath` confusion. |
| 9 | Design push/CI automation only after current proof CI is green. | Keeps remote mutation one step behind validated local proof. |
| 10 | Leave live RIFT/proof-promotion lanes separate. | This milestone is MCP workflow proof only, not game-state proof. |
