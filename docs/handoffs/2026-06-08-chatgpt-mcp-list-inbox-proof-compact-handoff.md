# Compact handoff — ChatGPT MCP list-inbox proof checkpoint

## Current verdict

ChatGPT Web/Desktop `rift-mcp` actual-client proof is progressing and remains
**blocked-safe** at the next operator-side tool call.

| Item | Current truth |
|---|---|
| Public MCP URL | `https://mcp.360madden.com/mcp` |
| Route | Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not active |
| ChatGPT app | `rift-mcp`, Developer Mode, No Authentication |
| Tool profile | `full`, 12 tools |
| Proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json` |
| Confirmed ChatGPT tools | `get_package_proposal_template`, `submit_package_proposal`, `list_inbox` |
| Latest inbox ID | `20260608T034503Z-2828ca695563` |
| Current first blocker | `create-package-draft-not-confirmed` |
| Branch state before this handoff | `main...origin/main [ahead 21]` |

## Captured actual-client evidence

| Tool | Result |
|---|---|
| `get_package_proposal_template` | Passed at `2026-06-08T03:35:46Z`; returned package-proposal template and draft-only safety flags. |
| `submit_package_proposal` | Passed at `2026-06-08T03:45:03Z`; stored `inboxId=20260608T034503Z-2828ca695563`. |
| `list_inbox` | Passed at `2026-06-08T03:48:39Z`; latest item matched `20260608T034503Z-2828ca695563`, `applied=false`, `executed=false`, `duplicate=false`. |

Ignored local evidence:

| Artifact | Path |
|---|---|
| Template observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-033546Z-get-package-proposal-template\observation.json` |
| Submit observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034503Z-submit-package-proposal\observation.json` |
| List-inbox observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034839Z-list-inbox\observation.json` |
| Local inbox item | `.riftreader-local\artifact-bridge-inbox\20260608T034503Z-2828ca695563` |

## Validation snapshot

| Check | Result |
|---|---|
| `python tools\riftreader_workflow\chatgpt_trial_recorder.py --check-latest-template --json` | Blocked-safe; first blocker is `create-package-draft-not-confirmed`. |
| Domain diagnostics | Last checked `2026-06-08T03:48:37Z`; public smoke HTTP 200, backend PID `48828`, `activeRouteUsesCaddy=false`. |
| Worktree before this handoff | Clean, branch ahead of origin. |

Remaining proof blockers:

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

## Exact next action

In the same ChatGPT `rift-mcp` chat, call:

```text
create_package_draft_from_inbox
```

with:

```text
inboxId = 20260608T034503Z-2828ca695563
```

Paste the output back into Codex. Required fields for the next proof update:
`ok=true`, `status`, and a non-empty `draftId`.

## Boundaries

No package apply, repo target write, Git push, RIFT input, CE/x64dbg attach,
provider write, or proof promotion was performed while collecting this proof
checkpoint.
