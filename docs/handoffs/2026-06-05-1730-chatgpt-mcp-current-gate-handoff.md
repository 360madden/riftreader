# ChatGPT MCP current gate compact handoff — 2026-06-05 17:30 UTC

## Current result

The RiftReader ChatGPT Web/Desktop MCP local hardening lane is cleanly committed
through `8891fe8 Require ChatGPT MCP proof tool identities`. The worktree was
clean at handoff creation and `main` was ahead of `origin/main` by 19 local
commits.

## Current gate state

| Surface | Current state |
|---|---|
| Branch | `main...origin/main [ahead 19]` |
| HEAD | `8891fe889a34f7f5ce0ee0248a410235fea602c9` |
| Final readiness | `blocked` |
| Current-head CI | Missing for `.NET build and test` and `RiftReader Policy` because the branch has not been pushed. |
| Secure Tunnel client dependency | `passed`; `C:\RIFT MODDING\Tools\OpenAI\tunnel-client\tunnel-client.exe` version probe passed. |
| Tool surface | `passed` |
| Fresh local readiness | `blocked`; trial-readiness and proposal-smoke artifacts are stale. |
| Actual ChatGPT proof | `blocked/stale`; latest proof is old and missing the current proof contract fields. |

## Most recent local hardening commits

| Commit | Purpose |
|---|---|
| `8891fe8` | Requires exact actual-client proof tool identities via `toolNames` and `toolOutputSchemaToolNames`. |
| `713bfb9` | Requires actual-client proof that ChatGPT observed per-tool `outputSchema` contracts. |
| `54b7cd2` | Validates runtime MCP tool-result payloads before return/audit. |
| `a2ba4bb` | Adds and verifies per-tool output schemas in the MCP manifest/SDK/transport validation. |
| `3791ad3` | Treats blocked-safe status as expected validation evidence. |

## Current proof contract

Fresh actual ChatGPT Secure Tunnel proof must include:

| Field | Required value |
|---|---|
| `connectionMode` | `openai-secure-mcp-tunnel` |
| `toolCount` | `10` |
| `toolNames` | Exact canonical 10-tool allowlist; no duplicates/missing/unexpected names. |
| `toolOutputSchemasPresent` | `true` |
| `toolOutputSchemaCount` | `10` |
| `toolOutputSchemaToolNames` | Exact canonical 10-tool allowlist proving every observed tool has output schema. |
| Draft/review/dry-run fields | Current package proposal, draft creation, read-only review, bounded dry-run diff-preview confirmations. |
| Health redaction | `repoRoot="."`, `repoName="RiftReader"`, `absoluteRepoRootExposed=false`. |

Canonical tools:

1. `health`
2. `get_repo_status`
3. `get_latest_handoff`
4. `get_package_proposal_template`
5. `submit_package_proposal`
6. `list_inbox`
7. `create_package_draft_from_inbox`
8. `review_latest_package_draft`
9. `dry_run_latest_package_draft`
10. `get_workflow_control_plan`

## Recommended safe resume order

1. Refresh local-only MCP readiness:
   `scripts\riftreader-operator-lite.cmd --mcp-trial-readiness --json`
2. Refresh local proposal transport smoke if still stale:
   `scripts\riftreader-chatgpt-mcp.cmd --proposal-transport-smoke --json`
3. Re-run final compact gate:
   `scripts\riftreader-mcp-final.cmd --status --compact-json`
4. If local readiness is fresh and clean, request explicit approval for the
   gated next steps:
   - push for current-head GitHub CI;
   - actual ChatGPT Secure Tunnel proof recording.

## Safety boundary

No public tunnel, ChatGPT registration, RIFT input, CE/x64dbg attach, provider
writes, proof promotion, push, or remote mutation was performed while creating
this handoff.

## Validation evidence at handoff

| Check | Result |
|---|---|
| Git status | Clean; `main...origin/main [ahead 19]`. |
| Final compact gate | Ran read-only; blocked on stale local readiness/proposal-smoke, stale actual proof, missing current-head CI, and unpushed branch. |
| Safety flags | Final gate reported no input, no movement, no public tunnel, no ChatGPT registration, no provider writes, no CE/x64dbg, no git mutation. |
