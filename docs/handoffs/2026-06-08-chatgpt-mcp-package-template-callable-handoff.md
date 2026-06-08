# ChatGPT MCP package-template callable handoff

## Verdict

The first package-loop proof blocker has cleared in actual ChatGPT Web/Desktop:
`get_package_proposal_template` is callable through the `rift-mcp` tool facade.

Final proof is still blocked until the remaining package-loop tools are called
from ChatGPT and their outputs are checked by the local proof recorder.

| Field | Current value |
|---|---|
| Public MCP URL | `https://mcp.360madden.com/mcp` |
| Connection mode | Cloudflare named Tunnel |
| ChatGPT app | `rift-mcp`, Developer Mode, No Authentication |
| Local backend | `127.0.0.1:8770`, PID `48828` |
| Tool count | 12 |
| First package-loop tool | `get_package_proposal_template` passed in ChatGPT at `2026-06-08T03:35:46Z` |
| Second package-loop tool | `submit_package_proposal` passed in ChatGPT at `2026-06-08T03:45:03Z` |

## New actual-client evidence

The operator pasted the ChatGPT result for `get_package_proposal_template`:

| Fact | Value |
|---|---|
| Tool called | `get_package_proposal_template` |
| `ok` | `true` |
| Status | `passed` |
| Template kind | `package-proposal` |
| Storage root | `.riftreader-local/artifact-bridge-inbox` |
| Safety | draft-only, requires human review, no repo target writes, no command execution, no Git mutation, no RIFT input, no CE/x64dbg |

Ignored evidence was updated locally:

| Artifact | Path |
|---|---|
| Operator observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-033546Z-get-package-proposal-template\observation.json` |
| Submit observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-034503Z-submit-package-proposal\observation.json` |
| Updated proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json` |

The operator then pasted the ChatGPT result for `submit_package_proposal`:

| Fact | Value |
|---|---|
| Tool called | `submit_package_proposal` |
| `ok` | `true` |
| Status | `stored` |
| Inbox ID | `20260608T034503Z-2828ca695563` |
| Duplicate | `false` |
| Stored under | `.riftreader-local/artifact-bridge-inbox/20260608T034503Z-2828ca695563` |
| SHA-256 | `2828ca695563bdf02d25732c87d91b8c3d7c336c18cd7c09d1e4fe1224b9b60d` |

Codex-local verification confirmed the ignored inbox directory exists, and a
local `list_inbox` call sees the new `inboxId`. This is useful route/backend
evidence, but final proof still requires the same `list_inbox` visibility from
actual ChatGPT.

## Refreshed local validation

| Command | Result |
|---|---|
| `python tools\riftreader_workflow\chatgpt_trial_recorder.py --check-latest-template --json` | Blocked as expected, but `template-fetch-not-confirmed`, `submit-package-proposal-not-confirmed`, and `chatgpt-tool-facade-unavailable:*` are no longer current blockers. |
| `scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json` | Passed at `2026-06-08T03:39:57Z`; public smoke HTTP 200, backend PID `48828`, Caddy remains deprecated and is not the active route. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --proposal-transport-smoke --json` | Passed locally; package-loop transport works on loopback and unapproved apply blocks with `APPLY_APPROVAL_MISSING`. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --call list_inbox --json` | Passed locally and includes `20260608T034503Z-2828ca695563`. |

Remaining proof-input blockers after ingesting the first two ChatGPT outputs:

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

In the same `rift-mcp` ChatGPT chat, call `list_inbox`.

Paste the output back into Codex. The proof needs confirmation that the
`items[]` list contains this ID:

```text
20260608T034503Z-2828ca695563
```

After that, the next ChatGPT call is `create_package_draft_from_inbox` using
that exact `inboxId`.

## Boundary

No repo target files were applied, no Git push occurred, no RIFT input was sent,
and no CE/x64dbg/provider write/proof promotion boundary was crossed.
