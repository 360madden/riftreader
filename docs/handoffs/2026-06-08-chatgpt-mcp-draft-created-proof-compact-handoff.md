# Compact handoff — ChatGPT MCP draft-created proof checkpoint

## Current verdict

ChatGPT Web/Desktop `rift-mcp` actual-client proof has advanced through draft
creation and remains **blocked-safe** at the next operator-side tool call:
`review_latest_package_draft`.

| Item | Current truth |
|---|---|
| Public MCP URL | `https://mcp.360madden.com/mcp` |
| Route | Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not active |
| ChatGPT app | `rift-mcp`, Developer Mode, No Authentication |
| Tool profile | `full`, 12 tools |
| Proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json` |
| Confirmed ChatGPT tools | `get_package_proposal_template`, `submit_package_proposal`, `list_inbox`, `create_package_draft_from_inbox` |
| Latest inbox ID | `20260608T034503Z-2828ca695563` |
| Latest draft ID | `20260608T034503Z-2828ca695563` |
| Current first blocker | `review-latest-package-draft-not-confirmed` |
| Branch state before this handoff | `main...origin/main`, clean |

## Captured actual-client evidence

| Tool | Result |
|---|---|
| `get_package_proposal_template` | Passed at `2026-06-08T03:35:46Z`; returned package-proposal template and draft-only safety flags. |
| `submit_package_proposal` | Passed at `2026-06-08T03:45:03Z`; stored `inboxId=20260608T034503Z-2828ca695563`. |
| `list_inbox` | Passed at `2026-06-08T03:48:39Z`; latest item matched `20260608T034503Z-2828ca695563`, `applied=false`, `executed=false`, `duplicate=false`. |
| `create_package_draft_from_inbox` | Passed at `2026-06-08T08:56:33Z`; created `draftId=20260608T034503Z-2828ca695563`, one-file draft, target `docs/workflow/chatgpt-mcp-smoke-preview.txt`, warning `checks-empty`. |

Ignored local evidence:

| Artifact | Path |
|---|---|
| Template observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-033546Z-get-package-proposal-template\observation.json` |
| Submit observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034503Z-submit-package-proposal\observation.json` |
| List-inbox observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034839Z-list-inbox\observation.json` |
| Draft creation observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-085633Z-create-package-draft-from-inbox\observation.json` |
| Local inbox item | `.riftreader-local\artifact-bridge-inbox\20260608T034503Z-2828ca695563` |
| Local draft root | `.riftreader-local\artifact-bridge-package-drafts\20260608T034503Z-2828ca695563` |

## Validation snapshot

| Check | Result |
|---|---|
| `python tools\riftreader_workflow\chatgpt_trial_recorder.py --check-latest-template --json` | Blocked-safe; first blocker is now `review-latest-package-draft-not-confirmed`. |
| Local draft filesystem check | Draft root, package root, and manifest exist. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call review_latest_package_draft --json` | Passed locally and selected the operator draft `20260608T034503Z-2828ca695563`; final proof still requires the same call from ChatGPT. |
| Last pushed commit before this local update | `989ac4d Create ChatGPT MCP list inbox compact handoff`; current-head CI passed before this new local draft-proof update. |

Remaining proof blockers:

```text
review-latest-package-draft-not-confirmed
review-latest-package-draft-read-only-not-confirmed
dry-run-not-confirmed
dry-run-diff-preview-not-confirmed
dry-run-diff-preview-package-intake-not-confirmed
dry-run-diff-preview-bounded-bytes-not-confirmed
dry-run-diff-preview-text-length-invalid:0
apply-latest-package-draft-without-approval-not-blocked
apply-latest-package-draft-without-approval-missing-approval-blocker
```

## Exact next action

In the same ChatGPT `rift-mcp` chat, call:

```text
review_latest_package_draft
```

Paste the output back into Codex. Required facts for the next proof update:
`ok=true`, `status`, `draftId=20260608T034503Z-2828ca695563`, and read-only
safety evidence such as `readOnlyReview=true` or equivalent.

## Boundaries

No package apply, repo target write, Git push, RIFT input, CE/x64dbg attach,
provider write, or proof promotion was performed while collecting this proof
checkpoint.
