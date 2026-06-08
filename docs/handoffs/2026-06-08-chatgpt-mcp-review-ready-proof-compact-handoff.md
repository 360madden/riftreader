# Compact handoff — ChatGPT MCP review-ready proof checkpoint

## Current verdict

ChatGPT Web/Desktop `rift-mcp` actual-client proof has advanced through
read-only package draft review and remains **blocked-safe** at the next
operator-side tool call: `dry_run_latest_package_draft`.

| Item | Current truth |
|---|---|
| Public MCP URL | `https://mcp.360madden.com/mcp` |
| Route | Cloudflare named Tunnel to `127.0.0.1:8770`; Caddy is deprecated and not active |
| ChatGPT app | `rift-mcp`, Developer Mode, No Authentication |
| Tool profile | `full`, 12 tools |
| Proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json` |
| Confirmed ChatGPT tools | `get_package_proposal_template`, `submit_package_proposal`, `list_inbox`, `create_package_draft_from_inbox`, `review_latest_package_draft` |
| Latest draft ID | `20260608T034503Z-2828ca695563` |
| Current first blocker | `dry-run-not-confirmed` |
| Branch state before this handoff | `main...origin/main [ahead 1]`, clean |

## Captured actual-client evidence

| Tool | Result |
|---|---|
| `get_package_proposal_template` | Passed at `2026-06-08T03:35:46Z`; returned package-proposal template and draft-only safety flags. |
| `submit_package_proposal` | Passed at `2026-06-08T03:45:03Z`; stored `inboxId=20260608T034503Z-2828ca695563`. |
| `list_inbox` | Passed at `2026-06-08T03:48:39Z`; latest item matched `20260608T034503Z-2828ca695563`, `applied=false`, `executed=false`, `duplicate=false`. |
| `create_package_draft_from_inbox` | Passed at `2026-06-08T08:56:33Z`; created `draftId=20260608T034503Z-2828ca695563`, one-file draft, target `docs/workflow/chatgpt-mcp-smoke-preview.txt`, warning `checks-empty`. |
| `review_latest_package_draft` | Passed/ready; `operatorOnly=true`, `draftId=20260608T034503Z-2828ca695563`, `readOnlyReview=true`, no blockers, validation warning `checks-empty`. |

Ignored local evidence:

| Artifact | Path |
|---|---|
| Template observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-033546Z-get-package-proposal-template\observation.json` |
| Submit observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034503Z-submit-package-proposal\observation.json` |
| List-inbox observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034839Z-list-inbox\observation.json` |
| Draft creation observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-085633Z-create-package-draft-from-inbox\observation.json` |
| Review observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-review-latest-package-draft\observation.json` |
| Local draft root | `.riftreader-local\artifact-bridge-package-drafts\20260608T034503Z-2828ca695563` |

## Validation snapshot

| Check | Result |
|---|---|
| `python tools\riftreader_workflow\chatgpt_trial_recorder.py --check-latest-template --json` | Blocked-safe; first blocker is now `dry-run-not-confirmed`. |
| Local `dry_run_latest_package_draft` smoke | Passed locally; diff preview artifact `.riftreader-local\package-intake\20260608-090251Z\package.diff`, `boundedBytes=true`, `diffArtifactUnderPackageIntake=true`, `truncated=false`, `sizeBytes=451`. |
| Safety | Local dry-run had `applyFlagSent=false`, `gitMutation=false`, `repoSourceMutationExpected=false`, no RIFT input, no CE, no x64dbg. |

Remaining proof blockers:

```text
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
dry_run_latest_package_draft
```

Paste the output back into Codex. Required facts for the next proof update:

| Required fact | Expected shape |
|---|---|
| `ok` / `dryRunSucceeded` | `true` |
| `draftId` | `20260608T034503Z-2828ca695563` |
| Diff preview OK | `true` |
| Diff artifact path | Under `.riftreader-local\package-intake\...` |
| Bounded bytes | `true` |
| Truncated | `false` |
| Diff preview text length | Positive integer / non-empty text |

After that, the final actual-client negative proof is
`apply_latest_package_draft` without `approvalToken`; it must block and not
apply.

## Boundaries

No package apply, repo target write, Git push, RIFT input, CE/x64dbg attach,
provider write, or proof promotion was performed while collecting this proof
checkpoint.
