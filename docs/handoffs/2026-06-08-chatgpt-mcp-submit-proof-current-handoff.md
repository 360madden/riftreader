# ChatGPT MCP submit-proof current handoff

## Verdict

The ChatGPT Web/Desktop MCP proof has advanced through the first two package
workflow tools:

1. `get_package_proposal_template`
2. `submit_package_proposal`

The lane is still **blocked-safe** until ChatGPT itself calls `list_inbox` and
shows the submitted inbox item.

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
| Latest local commit before this handoff | `ee23100 Record ChatGPT MCP package proposal submit proof` |

## Actual ChatGPT evidence captured so far

| Tool | ChatGPT result | Key proof data |
|---|---|---|
| `get_package_proposal_template` | Passed at `2026-06-08T03:35:46Z` | Returned `templateKind=package-proposal`, draft-only/no-repo-write safety flags. |
| `submit_package_proposal` | Passed at `2026-06-08T03:45:03Z` | Stored `inboxId=20260608T034503Z-2828ca695563`, `duplicate=false`, SHA-256 `2828ca695563bdf02d25732c87d91b8c3d7c336c18cd7c09d1e4fe1224b9b60d`. |

Ignored local evidence:

| Artifact | Path |
|---|---|
| Template observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-033546Z-get-package-proposal-template\observation.json` |
| Submit observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034503Z-submit-package-proposal\observation.json` |
| Local inbox item | `.riftreader-local\artifact-bridge-inbox\20260608T034503Z-2828ca695563` |

## Current validation snapshot

| Check | Result |
|---|---|
| Git status | Clean, `main...origin/main [ahead 19]` before this handoff. |
| Proof input check | Blocked as expected; submit proof is cleared and the first blocker is now `submit-succeeded-but-list-inbox-did-not-see-id`. |
| Domain diagnostics | Passed at `2026-06-08T03:48:37Z`; public smoke HTTP 200, backend PID `48828`. |
| Active route | Cloudflare named Tunnel to `http://127.0.0.1:8770`; Caddy is deprecated and `activeRouteUsesCaddy=false`. |
| Local inbox visibility | Local `list_inbox` sees `20260608T034503Z-2828ca695563`; final proof still requires ChatGPT `list_inbox` to show it. |

Current proof blockers:

```text
submit-succeeded-but-list-inbox-did-not-see-id
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
list_inbox
```

Paste the output back into Codex. The proof needs the returned `items[]` list to
contain:

```text
20260608T034503Z-2828ca695563
```

After `list_inbox` is confirmed, the next ChatGPT call is:

```text
create_package_draft_from_inbox
```

using:

```text
inboxId = 20260608T034503Z-2828ca695563
```

## Boundaries

No repo target package was applied, no Git push occurred, no RIFT input was
sent, and no CE/x64dbg/provider-write/proof-promotion boundary was crossed.
