# ChatGPT MCP submit-proof current handoff

## Verdict

The ChatGPT Web/Desktop MCP proof has advanced through the first two package
workflow tools:

1. `get_package_proposal_template`
2. `submit_package_proposal`
3. `list_inbox`

The lane is still **blocked-safe** until ChatGPT itself calls
`create_package_draft_from_inbox` using the submitted inbox item.

| Field | Current value |
|---|---|
| Public MCP URL | `https://mcp.360madden.com/mcp` |
| Connection mode | Cloudflare named Tunnel |
| ChatGPT app | `rift-mcp`, Developer Mode, No Authentication |
| Local backend | `127.0.0.1:8770`, PID `48828` |
| Tool profile | `full` |
| Tool count | 12 |
| Latest proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json` |
| Latest inbox ID | `20260608T034503Z-2828ca695563` |
| Latest list-inbox observation | `2026-06-08T03:48:39Z` |
| Latest local commit before list-inbox ingest | `c65fc63 Create ChatGPT MCP submit proof handoff` |

## Actual ChatGPT evidence captured so far

| Tool | ChatGPT result | Key proof data |
|---|---|---|
| `get_package_proposal_template` | Passed at `2026-06-08T03:35:46Z` | Returned `templateKind=package-proposal`, draft-only/no-repo-write safety flags. |
| `submit_package_proposal` | Passed at `2026-06-08T03:45:03Z` | Stored `inboxId=20260608T034503Z-2828ca695563`, `duplicate=false`, SHA-256 `2828ca695563bdf02d25732c87d91b8c3d7c336c18cd7c09d1e4fe1224b9b60d`. |
| `list_inbox` | Passed at `2026-06-08T03:48:39Z` | Returned `latestItem.inboxId=20260608T034503Z-2828ca695563`, `applied=false`, `executed=false`, `duplicate=false`. |

Ignored local evidence:

| Artifact | Path |
|---|---|
| Template observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-033546Z-get-package-proposal-template\observation.json` |
| Submit observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034503Z-submit-package-proposal\observation.json` |
| List-inbox observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034839Z-list-inbox\observation.json` |
| Local inbox item | `.riftreader-local\artifact-bridge-inbox\20260608T034503Z-2828ca695563` |

## Current validation snapshot

| Check | Result |
|---|---|
| Git status | Clean, `main...origin/main [ahead 20]` before list-inbox ingest. |
| Proof input check | Blocked as expected; list-inbox proof is cleared and the first blocker is now `create-package-draft-not-confirmed`. |
| Domain diagnostics | Passed at `2026-06-08T03:48:37Z`; public smoke HTTP 200, backend PID `48828`. |
| Active route | Cloudflare named Tunnel to `http://127.0.0.1:8770`; Caddy is deprecated and `activeRouteUsesCaddy=false`. |
| ChatGPT inbox visibility | Actual ChatGPT `list_inbox` saw `20260608T034503Z-2828ca695563`. |

Current proof blockers:

```text
create-package-draft-not-confirmed
review-latest-package-draft-not-confirmed
review-latest-package-draft-read-only-not-confirmed
dry-run-not-confirmed
dry-run-diff-preview-not-confirmed
dry-run-diff-preview-package-intake-not-confirmed
dry-run-diff-preview-bounded-bytes-not-confirmed
dry-run-diff-preview-text-length-invalid:0
draft-id-missing
apply-latest-package-draft-without-approval-not-blocked
apply-latest-package-draft-without-approval-missing-approval-blocker
```

## Next actual ChatGPT action

In the same `rift-mcp` ChatGPT chat, call:

```text
create_package_draft_from_inbox
```

using:

```text
inboxId = 20260608T034503Z-2828ca695563
```

Paste the output back into Codex. The proof needs `ok=true` and a non-empty
`draftId`.

After draft creation is confirmed, the next ChatGPT call is:

```text
review_latest_package_draft
```

## Boundaries

No repo target package was applied, no Git push occurred, no RIFT input was
sent, and no CE/x64dbg/provider-write/proof-promotion boundary was crossed.
