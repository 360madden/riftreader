# Compact handoff — ChatGPT MCP dry-run proof checkpoint

## Current verdict

ChatGPT Web/Desktop `rift-mcp` actual-client proof has advanced through
`dry_run_latest_package_draft`. The only remaining actual-client proof step is
the final negative safety check:

```text
apply_latest_package_draft without approvalToken
```

It must block and must not apply.

| Item | Current truth |
|---|---|
| Public MCP URL | `https://mcp.360madden.com/mcp` |
| Route | Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not active |
| ChatGPT app | `rift-mcp`, Developer Mode, No Authentication |
| Tool profile | `full`, 12 tools |
| Proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json` |
| Confirmed ChatGPT tools | `get_package_proposal_template`, `submit_package_proposal`, `list_inbox`, `create_package_draft_from_inbox`, `review_latest_package_draft`, `dry_run_latest_package_draft` |
| Latest draft ID | `20260608T034503Z-2828ca695563` |
| Current first blocker | `apply-latest-package-draft-without-approval-not-blocked` |
| Branch state before this handoff | `main...origin/main [ahead 2]`, clean |

## Captured actual-client evidence

| Tool | Result |
|---|---|
| `get_package_proposal_template` | Passed at `2026-06-08T03:35:46Z`; returned package-proposal template and draft-only safety flags. |
| `submit_package_proposal` | Passed at `2026-06-08T03:45:03Z`; stored `inboxId=20260608T034503Z-2828ca695563`. |
| `list_inbox` | Passed at `2026-06-08T03:48:39Z`; latest item matched `20260608T034503Z-2828ca695563`, `applied=false`, `executed=false`, `duplicate=false`. |
| `create_package_draft_from_inbox` | Passed at `2026-06-08T08:56:33Z`; created `draftId=20260608T034503Z-2828ca695563`, one-file draft, target `docs/workflow/chatgpt-mcp-smoke-preview.txt`, warning `checks-empty`. |
| `review_latest_package_draft` | Passed/ready; `operatorOnly=true`, `draftId=20260608T034503Z-2828ca695563`, `readOnlyReview=true`, no blockers, validation warning `checks-empty`. |
| `dry_run_latest_package_draft` | Passed; cached package-intake artifact reused, `draftId=20260608T034503Z-2828ca695563`, `changedFileCount=1`, no blockers/errors, warning `checks-empty`. |

Ignored local evidence:

| Artifact | Path |
|---|---|
| Template observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-033546Z-get-package-proposal-template\observation.json` |
| Submit observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034503Z-submit-package-proposal\observation.json` |
| List-inbox observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034839Z-list-inbox\observation.json` |
| Draft creation observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-085633Z-create-package-draft-from-inbox\observation.json` |
| Review observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-review-latest-package-draft\observation.json` |
| Dry-run observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-dry-run-latest-package-draft\observation.json` |
| Diff artifact | `.riftreader-local\package-intake\20260608-090251Z\package.diff` |

## Diff-preview verification

The ChatGPT dry-run output reused a cached package-intake artifact. Codex
verified the referenced local artifact before filling the required proof fields:

| Required proof field | Verified value |
|---|---|
| Diff preview OK | `true` |
| Diff artifact under package-intake | `true` |
| Bounded bytes | `true` |
| Diff file size | `451` bytes |
| Diff text length | `441` characters |
| Truncated | `false` |
| Changed file | `docs/workflow/chatgpt-mcp-smoke-preview.txt` |

## Validation snapshot

| Check | Result |
|---|---|
| `python tools\riftreader_workflow\chatgpt_trial_recorder.py --check-latest-template --json` | Blocked-safe; only blocked-apply proof remains. |
| Local `apply_latest_package_draft` without approval | Blocked locally with `APPLY_APPROVAL_MISSING`, `applied=false`, `applyFlagSent=false`; final proof still requires the same call from ChatGPT. |
| Safety | No repo target writes, no Git mutation, no RIFT input, no CE, no x64dbg. |

Remaining proof blockers:

```text
apply-latest-package-draft-without-approval-not-blocked
apply-latest-package-draft-without-approval-missing-approval-blocker
```

## Exact next action

In the same ChatGPT `rift-mcp` chat, call:

```text
apply_latest_package_draft
```

Do **not** provide `approvalToken`.

Paste the output back into Codex. Required facts for final proof:

| Required fact | Expected value |
|---|---|
| `ok` | `false` |
| `status` | `blocked` |
| `applied` | `false` |
| Blockers | Includes `APPLY_APPROVAL_MISSING` |
| Safety | `applyFlagSent=false`, `gitMutation=false`, no repo writes, no RIFT input, no CE, no x64dbg |

## Boundaries

No package apply, repo target write, Git push, RIFT input, CE/x64dbg attach,
provider write, or proof promotion was performed while collecting this proof
checkpoint.
